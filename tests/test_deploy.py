"""Deployment regression tests.

These files decide whether the hosted instance can compile a PDF at all, and a
missing LaTeX package there is invisible to the unit tests on a developer
machine (which has MiKTeX installed). Keep them honest.
"""

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from resumetex_web.core.compile import REQUIRED_PACKAGES, _missing_package


def _read(name: str) -> str:
    with open(os.path.join(ROOT, name), encoding="utf-8") as handle:
        return handle.read()


class DockerfileTests(unittest.TestCase):
    def setUp(self):
        self.dockerfile = _read("Dockerfile")
        # Only the apt package list, never comments.
        self.installed = re.findall(r"^\s+(lmodern|texlive-[a-z-]+)\s*\\\s*$", self.dockerfile, re.M)

    def test_latex_extra_is_installed(self):
        # titlesec.sty and enumitem.sty live in texlive-latex-extra. Without it
        # every Render compile fails with "File `titlesec.sty' not found".
        self.assertIn("texlive-latex-extra", self.installed)

    def test_lmodern_sty_is_installed(self):
        # The default font line is \usepackage{lmodern}; the .sty ships in the
        # separate `lmodern` package (texlive-latex-base only pulls the fonts).
        self.assertIn("lmodern", self.installed)

    def test_runtime_package_check_matches_the_image(self):
        # The health endpoint checks these; the image must provide all of them.
        from resumetex_web.core.compile import REQUIRED_PACKAGES
        provided = {"titlesec.sty": "texlive-latex-extra",
                    "enumitem.sty": "texlive-latex-extra",
                    "microtype.sty": "texlive-latex-recommended",
                    "xcolor.sty": "texlive-latex-recommended",
                    "lmodern.sty": "lmodern",
                    "mathptmx.sty": "texlive-latex-base"}
        for package in REQUIRED_PACKAGES:
            self.assertIn(provided[package], self.installed, package)

    def test_required_latex_packages_are_covered(self):
        for package in ("titlesec.sty", "enumitem.sty"):
            self.assertIn(package[:-4], self.dockerfile)

    def test_image_verifies_latex_at_build_time(self):
        self.assertIn("smoke test", self.dockerfile.lower())
        self.assertIn("pdflatex", self.dockerfile)

    def test_optional_fonts_are_not_required(self):
        # newtx lives in texlive-fonts-extra (~2 GB); templates must fall back.
        self.assertNotIn("texlive-fonts-extra", self.installed)


class RenderConfigTests(unittest.TestCase):
    def test_blueprint_uses_docker_and_allows_compile(self):
        render = _read("render.yaml")
        self.assertIn("runtime: docker", render)
        self.assertRegex(render, r"RESUMETEX_ALLOW_COMPILE\s*\n\s*value:\s*\"1\"")
        self.assertIn("dockerfilePath", render)


class TemplateFallbackTests(unittest.TestCase):
    def test_templates_do_not_hard_require_newtx(self):
        for name in ("resumetex_web/core/latex.py", "resumetex_web/core/gallery.py"):
            source = _read(name)
            for line in source.splitlines():
                if "newtxtext" in line:
                    self.assertIn("IfFileExists", line, f"{name}: {line.strip()}")

    def test_missing_package_is_reported(self):
        log = "! LaTeX Error: File `titlesec.sty' not found.\n"
        self.assertEqual(_missing_package(log), "titlesec.sty")
        self.assertIsNone(_missing_package("! Undefined control sequence."))

    def test_required_packages_are_documented(self):
        self.assertEqual(REQUIRED_PACKAGES[:2], ("titlesec.sty", "enumitem.sty"))
        self.assertIn("lmodern.sty", REQUIRED_PACKAGES)


if __name__ == "__main__":
    unittest.main(verbosity=2)
