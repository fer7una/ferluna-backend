import unittest
from unittest.mock import patch

from app.main import resolve_admin_route, resolve_route


class ApiRouteTests(unittest.TestCase):
    def test_site_payload_includes_public_sections(self) -> None:
        status, payload = resolve_route("/api/site")

        self.assertEqual(status, 200)
        self.assertIn("profile", payload)
        self.assertIn("cv", payload)
        self.assertIn("projects", payload)
        self.assertIn("posts", payload)
        self.assertIn("docs", payload)
        self.assertIn("sections", payload)
        self.assertIn("sectionItems", payload)
        self.assertIn("momentaryTabs", payload)

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
        env = {
            "FERLUNA_ADMIN_PASSWORD": "secret",
            "FERLUNA_JWT_SECRET": "test-signing-secret",
            "FERLUNA_JWT_TTL_SECONDS": "300",
        }
        with patch.dict("os.environ", env, clear=False):
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

    def test_unknown_route_returns_404(self) -> None:
        status, payload = resolve_route("/api/unknown")

        self.assertEqual(status, 404)
        self.assertEqual(payload["error"], "not_found")


if __name__ == "__main__":
    unittest.main()
