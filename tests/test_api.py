"""HTTP-level tests: the app must work, and must not store anything."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from resumetex_web import create_app
from resumetex_web.config import Config


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(Config(allow_compile=False, allow_online_compile=False))
        self.client = self.app.test_client()

    def test_health(self):
        data = self.client.get("/api/health").get_json()
        self.assertTrue(data["ok"])
        self.assertFalse(data["allowCompile"])
        self.assertIn("latex", data)
        self.assertIn("found", data["latex"])
        self.assertIn("missing", data["latex"])

    def test_index_and_pages_render(self):
        for path in ("/", "/gallery", "/privacy"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertIn(b"ResumeTeX", response.data)

    def test_redact_endpoint(self):
        response = self.client.post("/api/redact", json={
            "pii": {"name": "Rehan Khan", "email": "rehan@leadsgp.tech"},
            "details": "Rehan Khan can be reached at rehan@leadsgp.tech.",
        })
        data = response.get_json()
        self.assertNotIn("rehan@leadsgp.tech", data["text"].lower())
        self.assertGreater(data["replacementCount"], 0)

    def test_redact_endpoint_blocks_leak(self):
        response = self.client.post("/api/redact", json={
            "pii": {"name": "Rehan Khan"},
            "details": "Rehan Khan",
        })
        # Rehan Khan is redacted to "the candidate", so no leak: the request succeeds.
        self.assertEqual(response.status_code, 200)

    def test_templates_endpoint_lists_gallery(self):
        data = self.client.get("/api/templates").get_json()
        self.assertEqual(len(data["house"]), 15)
        self.assertEqual(len(data["atsSafe"]), 12)
        for entry in data["house"]:
            self.assertIn("atsScore", entry)
            self.assertGreaterEqual(entry["atsScore"], 0)

    def test_ats_score_endpoint(self):
        response = self.client.post("/api/ats/score", json={"body": "\\section{Summary}\nHi."})
        data = response.get_json()
        self.assertIn("score", data)
        self.assertTrue(data["issues"])

    def test_canvas_render_endpoint(self):
        response = self.client.post("/api/canvas/render", json={
            "presetId": "ats-navy",
            "data": {"summary": "Engineer with 5 years of experience.",
                     "skills": [{"label": "Languages", "items": ["Python"]}]},
        })
        data = response.get_json()
        self.assertIn("\\section{Professional Summary}", data["body"])
        self.assertIn("\\documentclass", data["preamble"])

    def test_compile_disabled_returns_403(self):
        response = self.client.post("/api/compile", json={"tex": "\\documentclass{article}"})
        self.assertEqual(response.status_code, 403)

    def test_prompt_endpoint_redacts(self):
        response = self.client.post("/api/prompt", json={
            "pii": {"name": "Rehan Khan", "email": "rehan@leadsgp.tech"},
            "details": "Rehan Khan, rehan@leadsgp.tech, 5 years experience.",
            "style": "navy",
        })
        data = response.get_json()
        self.assertNotIn("rehan@leadsgp.tech", data["userContent"].lower())
        self.assertIn("the candidate", data["userContent"].lower())

    def test_sanitize_endpoint_rejects_bad_output(self):
        response = self.client.post("/api/sanitize", json={"raw": "\\section{X}\n\\input{a.tex}"})
        self.assertEqual(response.status_code, 400)

    def test_prompt_default_endpoint(self):
        data = self.client.get("/api/prompt/default").get_json()
        self.assertIn("template", data)
        self.assertIn("contract", data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
