import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.auth import create_admin_jwt
from app.content_store import (
    RevisionConflictError,
    build_profile_rows,
    build_visual_settings_row,
    require_link_kind,
    validate_collection,
)
from app.env_loader import load_env_file
from app.main import (
    reset_login_attempts,
    resolve_admin_login,
    resolve_admin_route,
    resolve_route,
    with_value_errors,
)

ADMIN_ENV = {
    "FERLUNA_ADMIN_PASSWORD": "secret",
    "FERLUNA_JWT_SECRET": "test-signing-secret",
    "FERLUNA_JWT_TTL_SECONDS": "300",
}


class ApiRouteTests(unittest.TestCase):
    def test_site_payload_is_fully_dynamic(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            status, payload = resolve_route("/api/site")

        self.assertEqual(status, 200)
        self.assertIn("profile", payload)
        self.assertIn("visualSettings", payload)
        self.assertIn("sections", payload)
        self.assertIn("sectionItems", payload)
        self.assertIn("momentaryTabs", payload)
        self.assertIn("momentaryItems", payload)
        # The legacy top-level blocks no longer exist; everything is sections/items.
        for legacy_key in ("cv", "projects", "posts", "docs"):
            self.assertNotIn(legacy_key, payload)

    def test_site_sections_do_not_expose_legacy_orbit_slot(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            status, payload = resolve_route("/api/site")

        self.assertEqual(status, 200)
        for section in payload["sections"]:
            self.assertNotIn("orbit", section)

    def test_admin_route_requires_token(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            status, payload = resolve_admin_route("/api/admin/site", "GET", {})

        self.assertEqual(status, 503)
        self.assertEqual(payload["error"], "admin_disabled")

    def test_admin_login_requires_config(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            status, payload = resolve_admin_route(
                "/api/admin/login",
                "POST",
                {},
                {"password": "secret"},
            )

        self.assertEqual(status, 503)
        self.assertEqual(payload["error"], "admin_disabled")

    def test_admin_login_issues_jwt_and_allows_admin_route(self) -> None:
        with patch.dict("os.environ", ADMIN_ENV, clear=True):
            status, payload = resolve_admin_route(
                "/api/admin/login",
                "POST",
                {},
                {"password": "secret"},
            )

            self.assertEqual(status, 200)
            self.assertIn("accessToken", payload)
            self.assertIn("expiresAt", payload)

            status, payload = resolve_admin_route(
                "/api/admin/site",
                "GET",
                {"Authorization": f"Bearer {payload['accessToken']}"},
            )

            self.assertEqual(status, 200)
            self.assertIn("sections", payload)
            self.assertIn("revision", payload)

    def test_admin_put_rejects_invalid_expected_revision(self) -> None:
        with patch.dict("os.environ", ADMIN_ENV, clear=True):
            token = create_admin_jwt()["accessToken"]
            status, payload = resolve_admin_route(
                "/api/admin/site",
                "PUT",
                {"Authorization": f"Bearer {token}"},
                {"expectedRevision": "not-an-int"},
            )

        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "invalid_payload")

    def test_unknown_route_returns_404(self) -> None:
        status, payload = resolve_route("/api/unknown")

        self.assertEqual(status, 404)
        self.assertEqual(payload["error"], "not_found")

    def test_removed_legacy_routes_return_404(self) -> None:
        for route in ("/api/profile", "/api/cv", "/api/projects", "/api/posts", "/api/docs"):
            status, _ = resolve_route(route)
            self.assertEqual(status, 404, route)


class AdminLoginRateLimitTests(unittest.TestCase):
    def test_login_rate_limit_returns_429(self) -> None:
        env = {**ADMIN_ENV, "FERLUNA_LOGIN_RATE_LIMIT": "2", "FERLUNA_LOGIN_RATE_WINDOW": "300"}
        client = "10.0.0.1"
        with patch.dict("os.environ", env, clear=True):
            reset_login_attempts(client)
            first, _ = resolve_admin_login({"password": "wrong"}, client)
            second, _ = resolve_admin_login({"password": "wrong"}, client)
            third, payload = resolve_admin_login({"password": "wrong"}, client)
            reset_login_attempts(client)

        self.assertEqual(first, 401)
        self.assertEqual(second, 401)
        self.assertEqual(third, 429)
        self.assertEqual(payload["error"], "too_many_requests")

    def test_successful_login_resets_attempts(self) -> None:
        env = {**ADMIN_ENV, "FERLUNA_LOGIN_RATE_LIMIT": "3"}
        client = "10.0.0.2"
        with patch.dict("os.environ", env, clear=True):
            reset_login_attempts(client)
            resolve_admin_login({"password": "wrong"}, client)
            ok, _ = resolve_admin_login({"password": "secret"}, client)
            # A correct login clears the counter, so further attempts are allowed.
            again, _ = resolve_admin_login({"password": "wrong"}, client)
            reset_login_attempts(client)

        self.assertEqual(ok, 200)
        self.assertEqual(again, 401)


class EnvLoaderTests(unittest.TestCase):
    def test_load_env_file_sets_missing_values_without_overriding_existing_env(self) -> None:
        with TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "FERLUNA_DATABASE_URL=postgresql://file:file@localhost:5432/ferluna",
                        "FERLUNA_API_HOST=0.0.0.0",
                        "FERLUNA_ADMIN_PASSWORD='quoted-secret'",
                        "# ignored comment",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict("os.environ", {"FERLUNA_API_HOST": "127.0.0.1"}, clear=True):
                load_env_file(env_path)

                self.assertEqual(
                    "postgresql://file:file@localhost:5432/ferluna",
                    os.environ["FERLUNA_DATABASE_URL"],
                )
                self.assertEqual("127.0.0.1", os.environ["FERLUNA_API_HOST"])
                self.assertEqual("quoted-secret", os.environ["FERLUNA_ADMIN_PASSWORD"])


class ContentValidationTests(unittest.TestCase):
    def test_revision_conflict_maps_to_409(self) -> None:
        def boom() -> dict[str, object]:
            raise RevisionConflictError("stale")

        status, payload = with_value_errors(boom)

        self.assertEqual(status, 409)
        self.assertEqual(payload["error"], "revision_conflict")

    def test_value_error_maps_to_400(self) -> None:
        def boom() -> dict[str, object]:
            raise ValueError("bad field")

        status, payload = with_value_errors(boom)

        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "invalid_payload")

    def test_require_link_kind_rejects_unknown(self) -> None:
        with self.assertRaises(ValueError):
            require_link_kind({"kind": "twitter"})

    def test_build_profile_rows_requires_fields(self) -> None:
        with self.assertRaises(ValueError):
            build_profile_rows({"name": "Only name"})

    def test_build_profile_rows_returns_link_rows(self) -> None:
        profile_row, link_rows = build_profile_rows(
            {
                "name": "Fernando",
                "role": "Dev",
                "tagline": "Tag",
                "location": "ES",
                "email": "a@b.c",
                "avatarAlt": "Alt",
                "highlights": ["one", "two"],
                "links": [{"label": "GitHub", "href": "https://x", "kind": "github"}],
            }
        )

        self.assertEqual(profile_row[0], "Fernando")
        self.assertEqual(profile_row[6], ["one", "two"])
        self.assertEqual(len(link_rows), 1)
        self.assertEqual(link_rows[0][3], "github")

    def test_validate_collection_rejects_non_list(self) -> None:
        with self.assertRaises(ValueError):
            validate_collection({"not": "a list"}, "sections")

    def test_build_visual_settings_row_requires_positive_durations(self) -> None:
        self.assertEqual(
            build_visual_settings_row(
                {
                    "sectionOrbitDurationSeconds": 12,
                    "momentaryOrbitDurationSeconds": 6.5,
                }
            ),
            (12.0, 6.5),
        )
        with self.assertRaises(ValueError):
            build_visual_settings_row(
                {
                    "sectionOrbitDurationSeconds": 0,
                    "momentaryOrbitDurationSeconds": 6.5,
                }
            )


if __name__ == "__main__":
    unittest.main()
