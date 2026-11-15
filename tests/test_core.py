"""Test suite for the ResumeTeX web app. No third-party dependencies."""

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from resumetex_web.core import (LaTeXRejected, PiiFields, PiiLeakError, PiiRedactor,
                                analyze, build_header, compose, escape_text, generate_body,
                                gallery, missing_core_sections, render_body, sample_data,
                                sanitize_ai_output)
from resumetex_web.core.gallery import preset

PII = PiiFields(
    name="Rehan Khan",
    email="rehan@leadsgp.tech",
    phone="+91 98765 43210",
    location="Indore, Madhya Pradesh",
    linkedin="https://linkedin.com/in/rehankhan?trk=public",
    github="github.com/rehankhan",
    portfolio="rehan.dev",
)


class RedactionTests(unittest.TestCase):
    def test_removes_every_contact_value(self):
        result = PiiRedactor(PII).redact(
            "Rehan Khan lives in Indore, Madhya Pradesh. Mail rehan@leadsgp.tech or call "
            "+91 98765 43210. LinkedIn: https://linkedin.com/in/rehankhan?trk=public and "
            "github.com/rehankhan, site rehan.dev."
        )
        text = result.text.lower()
        for secret in ("rehan khan", "rehan@leadsgp.tech", "98765 43210", "indore",
                       "rehankhan", "rehan.dev"):
            self.assertNotIn(secret, text, secret)
        self.assertIn("the candidate", text)
        self.assertGreater(result.replacement_count, 0)

    def test_generic_email_and_phone_are_caught(self):
        result = PiiRedactor(PiiFields()).redact(
            "Write to stranger@example.org or call 9876543210 during the sprint."
        )
        self.assertNotIn("stranger@example.org", result.text)
        self.assertNotIn("9876543210", result.text)

    def test_year_ranges_and_decimals_survive(self):
        result = PiiRedactor(PiiFields()).redact("Worked 2019 - 2023, improved throughput by 12.5%.")
        self.assertIn("2019 - 2023", result.text)
        self.assertIn("12.5%", result.text)

    def test_gate_blocks_leaked_value(self):
        redactor = PiiRedactor(PII)
        with self.assertRaises(PiiLeakError):
            redactor.verify_no_pii("Contact rehan@leadsgp.tech for details.")

    def test_name_parts_are_matched(self):
        result = PiiRedactor(PiiFields(name="Rehan Khan")).redact("Rehan led the project.")
        self.assertNotIn("Rehan", result.text)

    def test_link_handle_from_query_is_removed(self):
        result = PiiRedactor(PII).redact("See linkedin.com/in/rehankhan?trk=public")
        self.assertNotIn("rehankhan", result.text.lower())


class LatexTests(unittest.TestCase):
    def test_escape_text(self):
        self.assertEqual(escape_text("50% & #1 _x {y}"), r"50\% \& \#1 \_x \{y\}")

    def test_sanitize_drops_preamble_and_contact(self):
        body = sanitize_ai_output(
            "\\documentclass{article}\n\\begin{document}\n"
            "\\begin{center}\\textbf{Jane Doe}\\end{center}\n"
            "\\section{Summary}\nGood engineer.\n\\end{document}"
        )
        self.assertIn("\\section{Summary}", body)
        self.assertNotIn("\\documentclass", body)
        self.assertNotIn("Jane Doe", body)

    def test_sanitize_rejects_blocked_commands(self):
        with self.assertRaises(LaTeXRejected):
            sanitize_ai_output("\\section{X}\n\\input{secret.tex}")

    def test_header_contains_contact_locally(self):
        header = build_header("navy", PII)
        self.assertIn("Rehan Khan", header)
        self.assertIn("rehan@leadsgp.tech", header)
        self.assertIn("navyblue", header)

    def test_compose_resolves_placeholders(self):
        doc = compose("navy", PII, "\\section{Summary}\nText.")
        self.assertNotIn("%%HEADER%%", doc)
        self.assertNotIn("%%BODY%%", doc)
        self.assertIn("Rehan Khan", doc)
        self.assertIn("\\end{document}", doc)

    def test_offline_generator_detects_sections(self):
        body = generate_body(
            "SUMMARY\nData analyst with 4 years of experience.\n\n"
            "SKILLS\nPython, SQL, Power BI\n\n"
            "EXPERIENCE\nData Analyst, Infosys | 2022 - Present\n- Built dashboards.\n"
        )
        self.assertIn("\\section{Professional Summary}", body)
        self.assertIn("\\section{Skills}", body)
        self.assertIn("\\section{Professional Experience}", body)


class AtsTests(unittest.TestCase):
    def test_good_body_scores_well(self):
        body = render_body(sample_data(), preset("ats-navy"))
        report = analyze(body)
        self.assertGreaterEqual(report.score, 85, report.as_dict())
        self.assertIn(report.grade, ("A", "B"))

    def test_forbidden_constructs_are_penalised(self):
        body = "\\section{Summary}\nX\n\\begin{tabular}{c}a\\\\b\\end{tabular}"
        report = analyze(body)
        self.assertTrue(any("table" in issue.message.lower() for issue in report.issues))

    def test_missing_sections_are_flagged(self):
        report = analyze("\\section{Summary}\nSomething.")
        self.assertTrue(any("Skills" in issue.message for issue in report.issues))
        self.assertIn("Skills", missing_core_sections("\\section{Summary}\nSomething."))

    def test_jd_coverage_is_reported(self):
        body = render_body(sample_data(), preset("ats-navy"))
        report = analyze(body, "Python SQL Power BI dashboards reporting")
        self.assertIsNotNone(report.stats["keywordCoverage"])


class GalleryTests(unittest.TestCase):
    def test_gallery_has_fifteen_templates(self):
        items = gallery()
        self.assertEqual(len(items), 15)
        self.assertEqual(len([g for g in items if g["atsClass"] == "ats"]), 12)
        self.assertEqual(len([g for g in items if g["atsClass"] == "creative"]), 3)

    def test_creative_templates_score_lower(self):
        items = gallery()
        best_creative = max(g["atsScore"] for g in items if g["atsClass"] == "creative")
        worst_safe = min(g["atsScore"] for g in items if g["atsClass"] == "ats")
        self.assertLess(best_creative, worst_safe)


class ParityTests(unittest.TestCase):
    """The browser redactor and the server redactor must agree exactly."""

    CORPUS = [
        ("Rehan Khan from Indore, Madhya Pradesh, mail rehan@leadsgp.tech, call +91 98765 43210.", PII),
        ("Worked at Persistent Systems 2019 - 2023, improved p95 latency by 40%.", PII),
        ("Reach stranger@example.org about the role; also 9876543210.", PiiFields()),
        ("github.com/rehankhan and linkedin.com/in/rehankhan?trk=public", PII),
        ("Deployed 3.2% of traffic to the new region in 12 days.", PiiFields()),
    ]

    def test_browser_and_server_redaction_match(self):
        script = os.path.join(ROOT, "tests", "parity_runner.mjs")
        if not (os.path.exists(script) and shutil_which("node")):
            self.skipTest("node is not available")
        corpus = [
            {"text": text, "pii": {
                "name": pii.name, "email": pii.email, "phone": pii.phone,
                "location": pii.location, "linkedin": pii.linkedin,
                "github": pii.github, "portfolio": pii.portfolio,
            }} for text, pii in self.CORPUS
        ]
        result = subprocess.run(
            [shutil_which("node"), script],
            input=json.dumps(corpus), capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[:400])
        browser = json.loads(result.stdout)
        for index, (text, pii) in enumerate(self.CORPUS):
            server = PiiRedactor(pii).redact(text)
            self.assertEqual(server.text, browser[index]["text"], f"case {index}")
            self.assertEqual(server.replacement_count, browser[index]["replacementCount"], f"case {index}")


def shutil_which(binary: str):
    from shutil import which
    return which(binary)


if __name__ == "__main__":
    unittest.main(verbosity=2)
