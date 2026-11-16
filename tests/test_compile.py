"""Real compile tests.

If pdflatex (MiKTeX / TeX Live) is installed, every house shell and every
gallery preset is compiled for real. This is the safety net that catches
malformed LaTeX (a broken \\titleformat argument list, a missing package, an
unescaped character) before a user ever sees it.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from resumetex_web.core import compose, get_shell, render_document, sample_data
from resumetex_web.core.canvas import build_preamble
from resumetex_web.core.compile import CompileError, compile_local
from resumetex_web.core.gallery import GALLERY, preset
from resumetex_web.core.latex import HOUSE_SHELLS
from resumetex_web.core.pii import PiiFields

PDFLATEX = shutil.which("pdflatex")
if not PDFLATEX and os.name == "nt":
    candidate = os.path.expandvars(
        r"%LOCALAPPDATA%\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe")
    PDFLATEX = candidate if os.path.exists(candidate) else None

PII = PiiFields(name="Rehan Khan", email="rehan@leadsgp.tech",
                phone="+91 98765 43210", location="Indore, India")


def compile_tex(tex: str) -> tuple[int, str]:
    with tempfile.TemporaryDirectory(prefix="resumetex-test-") as directory:
        path = os.path.join(directory, "resume.tex")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(tex)
        try:
            completed = subprocess.run(
                [PDFLATEX, "-interaction=nonstopmode", "-halt-on-error", "-no-shell-escape", "resume.tex"],
                cwd=directory, capture_output=True, text=True, timeout=120, errors="replace")
        except subprocess.TimeoutExpired:
            return 1, "compile timed out"
        output = (completed.stdout or "") + (completed.stderr or "")
        first_error = ""
        for line in output.splitlines():
            if line.strip().startswith("!"):
                first_error = line.strip()[:200]
                break
        return completed.returncode, first_error


@unittest.skipUnless(PDFLATEX, "pdflatex is not installed")
class CompileTests(unittest.TestCase):
    def test_every_house_shell_compiles(self):
        body = ("\\section{Professional Summary}\n"
                "Data analyst with 5+ years of experience in Python and SQL.\n"
                "\\section{Skills}\n"
                "\\textbf{Languages:} Python, SQL\\\\\n"
                "\\section{Professional Experience}\n"
                "\\textbf{Data Analyst, Infosys} \\hfill 2022 - Present\\\\\n"
                "\\begin{itemize}[leftmargin=1.15em,itemsep=1.5pt,topsep=2pt,parsep=0pt,partopsep=0pt]\n"
                "\\item Built a Power BI dashboard used by 300 people, cutting reporting time by 30\\%.\n"
                "\\end{itemize}\n"
                "\\section{Education}\n"
                "B.Tech Computer Science, RGPV University \\\\ 2016 - 2020")
        for style in HOUSE_SHELLS:
            tex = compose(style, PII, body)
            code, error = compile_tex(tex)
            self.assertEqual(code, 0, f"{style}: {error}")

    def test_every_gallery_preset_compiles(self):
        for preset_id, preset in GALLERY.items():
            tex = render_document(sample_data(), preset, PII)
            code, error = compile_tex(tex)
            self.assertEqual(code, 0, f"{preset_id}: {error}")

    def test_titleformat_has_five_groups(self):
        """titlesec needs {cmd}{format}{label}{sep}{before}[after]."""
        for style, shell in HOUSE_SHELLS.items():
            self.assertIn("{}{0em}{}[", shell, f"{style} titleformat is malformed")
        for preset_id, preset in GALLERY.items():
            preamble = build_preamble(preset)
            self.assertIn("{}{0em}{}[", preamble, f"{preset_id} titleformat is malformed")

    def test_serif_fallback_compiles_without_newtx(self):
        """Render's image skips texlive-fonts-extra; mathptmx must take over."""
        tex = render_document(sample_data(), preset("ats-classic"), PII)
        self.assertIn("newtxtext", tex)
        fallback = "\n".join(
            "\\usepackage{mathptmx}" if "newtxtext" in line else line
            for line in tex.splitlines())
        code, error = compile_tex(fallback)
        self.assertEqual(code, 0, error)

    def test_missing_package_error_is_actionable(self):
        """A hosted instance with an incomplete TeX install must say what is wrong."""
        tex = ("\\documentclass{article}\\usepackage{doesnotexist}"
               "\\begin{document}x\\end{document}")
        with self.assertRaises(CompileError) as caught:
            compile_local(tex)
        self.assertIn("missing the LaTeX package 'doesnotexist.sty'", str(caught.exception))
        self.assertIn("Dockerfile", str(caught.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
