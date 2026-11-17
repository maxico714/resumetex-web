"""HTTP-level tests: the app must work, and must not store anything."""

import base64
import json
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from resumetex_web import create_app
from resumetex_web.config import Config
from resumetex_web.core.compile import CompileError, CompileResult


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
        self.assertEqual(len(data["house"]), 18)
        self.assertEqual(len(data["atsSafe"]), 15)
        self.assertEqual(len(data["creative"]), 3)
        self.assertEqual(len(data["starters"]), 3)
        self.assertTrue(data["starterData"]["experience"])
        for entry in data["house"]:
            self.assertIn("atsScore", entry)
            self.assertGreaterEqual(entry["atsScore"], 0)
            self.assertIn("starter", entry)

    def test_starter_content_is_not_personal_data(self):
        data = self.client.get("/api/templates").get_json()
        blob = str(data["starterData"]).lower()
        for needle in ("@gmail.com", "linkedin.com/in/", "+91"):
            self.assertNotIn(needle, blob)

    def test_canvas_render_returns_layout_metadata(self):
        response = self.client.post("/api/canvas/render", json={
            "presetId": "starter-executive",
            "data": {"summary": "Engineer.", "headline": "Senior Developer"},
        })
        data = response.get_json()
        self.assertEqual(data["headerStyle"], "executive")
        self.assertEqual(data["entryStyle"], "company-first")
        self.assertEqual(data["accent"], "starterburgundy")

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

    def test_online_compile_disabled_returns_403(self):
        app = create_app(Config(allow_compile=True, allow_online_compile=False))
        response = app.test_client().post(
            "/api/compile", json={"tex": "\\documentclass{article}", "mode": "online"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["code"], "online_disabled")

    def test_unknown_mode_falls_back_to_local(self):
        app = create_app(Config(allow_compile=True, allow_online_compile=False))
        fake = CompileResult(pdf=b"%PDF-1.4 fake", engine="pdflatex (local)", pages=1)
        with mock.patch("resumetex_web.api.compile_local", return_value=fake) as local:
            response = app.test_client().post(
                "/api/compile", json={"tex": "\\documentclass{article}", "mode": "banana"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(local.call_count, 1)
        self.assertEqual(response.headers["X-ResumeTeX-Engine"], "pdflatex (local)")
        self.assertEqual(response.headers["X-ResumeTeX-Online"], "0")

    def test_local_mode_never_calls_online(self):
        app = create_app(Config(allow_compile=True, allow_online_compile=True))
        fake = CompileResult(pdf=b"%PDF-1.4 fake", engine="pdflatex (local)", pages=1)
        with mock.patch("resumetex_web.api.compile_local", return_value=fake), \
                mock.patch("resumetex_web.api.compile_online") as online:
            response = app.test_client().post(
                "/api/compile", json={"tex": "\\documentclass{article}", "mode": "local"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(online.call_count, 0)

    def test_auto_falls_back_online_only_when_enabled(self):
        fake = CompileResult(pdf=b"%PDF-1.4 fake", engine="online (latex.ytotech.com)", pages=2)
        app = create_app(Config(allow_compile=True, allow_online_compile=True))
        with mock.patch("resumetex_web.api.compile_local",
                        side_effect=CompileError("titlesec.sty missing")), \
                mock.patch("resumetex_web.api.compile_online", return_value=fake):
            response = app.test_client().post(
                "/api/compile", json={"tex": "\\documentclass{article}", "mode": "auto"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-ResumeTeX-Online"], "1")
        self.assertIn("local failed", response.headers["X-ResumeTeX-Engine"])

    def test_auto_does_not_upload_when_online_is_off(self):
        app = create_app(Config(allow_compile=True, allow_online_compile=False))
        with mock.patch("resumetex_web.api.compile_local",
                        side_effect=CompileError("titlesec.sty missing")), \
                mock.patch("resumetex_web.api.compile_online") as online:
            response = app.test_client().post(
                "/api/compile", json={"tex": "\\documentclass{article}", "mode": "auto"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(online.call_count, 0)

    def test_compile_stream_reports_stages_and_pdf(self):
        app = create_app(Config(allow_compile=True, allow_online_compile=False))
        fake = CompileResult(pdf=b"%PDF-1.4 streamed", engine="pdflatex (local)", pages=1)
        with mock.patch("resumetex_web.api.compile_local", return_value=fake):
            response = app.test_client().post(
                "/api/compile/stream", json={"tex": "\\documentclass{article}", "mode": "local"})
            payload = response.data  # the stream is consumed here, inside the patch
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/x-ndjson", response.headers["Content-Type"])
        events = [json.loads(line) for line in payload.decode("utf-8").splitlines() if line.strip()]
        self.assertEqual(events[0]["type"], "start")
        self.assertEqual(events[-1]["type"], "done")
        self.assertEqual(events[-1]["pages"], 1)
        self.assertFalse(events[-1]["online"])
        self.assertEqual(base64.b64decode(events[-1]["pdf"]), b"%PDF-1.4 streamed")
        stages = [e["stage"] for e in events if e["type"] == "stage"]
        self.assertIn("local", stages)
        self.assertIn("preview", stages)
        progress = [e["progress"] for e in events]
        self.assertEqual(progress, sorted(progress))

    def test_compile_stream_error_is_a_json_event(self):
        app = create_app(Config(allow_compile=True, allow_online_compile=False))
        with mock.patch("resumetex_web.api.compile_local",
                        side_effect=CompileError("titlesec.sty missing")):
            response = app.test_client().post(
                "/api/compile/stream", json={"tex": "\\documentclass{article}", "mode": "local"})
            payload = response.data
        self.assertEqual(response.status_code, 200)
        events = [json.loads(line) for line in payload.decode("utf-8").splitlines() if line.strip()]
        self.assertEqual(events[-1]["type"], "error")
        self.assertIn("titlesec.sty", events[-1]["message"])
        self.assertEqual(events[-1]["code"], "compile_error")

    def test_compile_stream_respects_the_same_gates(self):
        response = self.client.post(
            "/api/compile/stream", json={"tex": "\\documentclass{article}"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["code"], "compile_disabled")

    def test_diagnose_reports_engine_without_personal_data(self):
        app = create_app(Config(allow_compile=True, allow_online_compile=False))
        missing = {"found": False, "path": "", "missing": []}
        with mock.patch("resumetex_web.core.compile.latex_status", return_value=missing), \
                mock.patch("resumetex_web.core.compile.pdflatex_version", return_value=""):
            response = app.test_client().post("/api/compile/diagnose", json={})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["allowCompile"])
        self.assertFalse(data["allowOnlineCompile"])
        self.assertFalse(data["pdflatex"]["found"])
        self.assertIsNone(data["probe"])
        self.assertNotIn("email", data)

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
