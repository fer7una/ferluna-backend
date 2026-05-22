import unittest

from app.main import resolve_route


class ApiRouteTests(unittest.TestCase):
    def test_site_payload_includes_public_sections(self) -> None:
        status, payload = resolve_route("/api/site")

        self.assertEqual(status, 200)
        self.assertIn("profile", payload)
        self.assertIn("cv", payload)
        self.assertIn("projects", payload)
        self.assertIn("posts", payload)
        self.assertIn("docs", payload)

    def test_unknown_route_returns_404(self) -> None:
        status, payload = resolve_route("/api/unknown")

        self.assertEqual(status, 404)
        self.assertEqual(payload["error"], "not_found")


if __name__ == "__main__":
    unittest.main()
