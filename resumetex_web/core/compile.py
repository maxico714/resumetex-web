"""PDF compilation.

Local mode runs pdflatex (MiKTeX / TeX Live) on the app server: the document
never leaves that server and no third party sees it. Online mode is opt-in and
warns, because it uploads the whole document including contact details.

Ported from ResumeTex.Core/Compilation/*.cs
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ONLINE_URL = "https://latex.ytotech.com/builds/sync"
LATEXONLINE_URL = "https://latexonline.cc/compile"

_WINDOWS_PDFLATEX_CANDIDATES = (
    Path.home() / "AppData/Local/Programs/MiKTeX/miktex/bin/x64/pdflatex.exe",
    Path("C:/Program Files/MiKTeX/miktex/bin/x64/pdflatex.exe"),
    Path("C:/Program Files (x86)/MiKTeX/miktex/bin/x64/pdflatex.exe"),
)


class CompileError(Exception):
    """Raised when the document could not be compiled."""


@dataclass
class CompileResult:
    pdf: bytes
    engine: str
    pages: int = 0
    log: str = ""


def find_pdflatex() -> str | None:
    """Locate a pdflatex binary."""
    found = shutil.which("pdflatex")
    if found:
        return found
    if os.name == "nt":
        for candidate in _WINDOWS_PDFLATEX_CANDIDATES:
            if candidate.exists():
                return str(candidate)
    for candidate in ("/usr/bin/pdflatex", "/usr/local/bin/pdflatex",
                      "/Library/TeX/texbin/pdflatex", "/opt/texlive/bin/pdflatex"):
        if Path(candidate).exists():
            return candidate
    return None


def is_available() -> bool:
    return find_pdflatex() is not None


# Packages the house templates and every gallery preset rely on. `newtx*` is
# deliberately absent: it lives in the multi-gigabyte texlive-fonts-extra, and
# the templates fall back to mathptmx/lmodern when it is not installed.
REQUIRED_PACKAGES = ("titlesec.sty", "enumitem.sty", "microtype.sty",
                    "xcolor.sty", "lmodern.sty", "mathptmx.sty")

# A small document that exercises every package the real templates use. The
# /api/compile/diagnose endpoint and the Docker build compile it for real.
PROBE_TEX = r"""\documentclass[11pt]{article}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage[left=0.75in,top=0.6in,right=0.75in,bottom=0.6in]{geometry}
\usepackage[hidelinks]{hyperref}
\usepackage{xcolor}
\usepackage{titlesec}
\usepackage{enumitem}
\usepackage{microtype}
\usepackage{mathptmx}
\definecolor{probenavy}{RGB}{0,54,123}
\pagestyle{empty}
\titleformat{\section}{\color{probenavy}\large\bfseries}{}{0em}{}[\color{probenavy}\titlerule]
\begin{document}
\section{Compiler probe}
This document only proves that the LaTeX installation works.
\begin{itemize}[leftmargin=1.15em,itemsep=1.5pt,topsep=2pt,parsep=0pt,partopsep=0pt]
\item titlesec, enumitem, lmodern, mathptmx, xcolor, microtype and hyperref all loaded.
\end{itemize}
\href{https://example.com}{https://example.com}
\end{document}
"""


def find_kpsewhich() -> str | None:
    """Locate kpsewhich, which tells us whether a .sty file is installed."""
    found = shutil.which("kpsewhich")
    if found:
        return found
    exe = find_pdflatex()
    if exe:
        candidate = Path(exe).with_name("kpsewhich" + (".exe" if os.name == "nt" else ""))
        if candidate.exists():
            return str(candidate)
    return None


def missing_packages() -> list[str]:
    """LaTeX packages that are needed but absent on this machine.

    An empty list means either everything is present or we cannot tell
    (kpsewhich unavailable) — callers should treat it as best-effort.
    """
    kpsewhich = find_kpsewhich()
    if not kpsewhich:
        return []
    missing: list[str] = []
    for package in REQUIRED_PACKAGES:
        try:
            completed = subprocess.run(
                [kpsewhich, package], capture_output=True, text=True, timeout=15,
                errors="replace",
            )
        except (OSError, subprocess.SubprocessError):
            return []
        if completed.returncode != 0 or not (completed.stdout or "").strip():
            missing.append(package[:-4])
    return missing


_STATUS_CACHE: dict | None = None


def latex_status() -> dict:
    """Diagnostics for /api/health and the compile card in the UI.

    Cached for the lifetime of the process: kpsewhich startup is slow on some
    distributions, and an engine/package change requires a restart anyway.
    """
    global _STATUS_CACHE
    if _STATUS_CACHE is None:
        exe = find_pdflatex()
        _STATUS_CACHE = {
            "found": exe is not None,
            "path": exe or "",
            "missing": missing_packages() if exe else [],
        }
    return dict(_STATUS_CACHE)


def pdflatex_version() -> str:
    """First line of `pdflatex --version`, or an empty string."""
    exe = find_pdflatex()
    if not exe:
        return ""
    try:
        completed = subprocess.run(
            [exe, "--version"], capture_output=True, text=True, timeout=20,
            errors="replace",
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"error: {exc}"
    lines = (completed.stdout or "").strip().splitlines()
    return lines[0] if lines else ""


def probe_local(timeout: int = 45) -> dict:
    """Compile PROBE_TEX with the local engine; never raises."""
    try:
        result = compile_local(PROBE_TEX, timeout=timeout)
    except CompileError as exc:
        return {"ok": False, "error": str(exc), "pages": 0, "bytes": 0,
                "engine": ""}
    return {"ok": True, "error": "", "pages": result.pages,
            "bytes": len(result.pdf), "engine": result.engine}


def _first_error(output: str) -> str:
    for line in (output or "").splitlines():
        trimmed = line.strip()
        if trimmed.startswith("!") or "error:" in trimmed.lower():
            return trimmed[:300]
    compact = (output or "").strip().replace("\r", "")
    return (compact[:300] if compact else "pdflatex reported an error.")


def _page_count(log: str) -> int:
    # MiKTeX wraps the line, e.g. "Output written on ...pdf (\n1 page, ...)"
    flat = re.sub(r"\s+", " ", log or "")
    match = re.search(r"Output written on .*?\((\d+)\s+pages?", flat)
    return int(match.group(1)) if match else 0


def _missing_package(output: str) -> str | None:
    """The .sty file LaTeX complained about, e.g. 'titlesec.sty'."""
    match = re.search(r"File [`']([^'`]+\.sty)' not found", output or "")
    return match.group(1) if match else None


def compile_local(tex: str, timeout: int = 75) -> CompileResult:
    """Compile with the local pdflatex. Nothing is uploaded."""
    exe = find_pdflatex()
    if not exe:
        raise CompileError(
            "pdflatex was not found. Install MiKTeX or TeX Live, or use an online compiler."
        )
    if not tex or not tex.strip():
        raise CompileError("LaTeX source is empty.")

    directory = Path(tempfile.mkdtemp(prefix="resumetex-"))
    try:
        tex_path = directory / "resume.tex"
        tex_path.write_text(tex, encoding="utf-8", newline="\n")
        args = [
            exe, "-interaction=nonstopmode", "-no-shell-escape", "-halt-on-error",
            "-file-line-error", f"-output-directory={directory}", str(tex_path),
        ]
        try:
            completed = subprocess.run(
                args, cwd=str(directory), capture_output=True, text=True,
                timeout=timeout, errors="replace",
            )
        except subprocess.TimeoutExpired:
            raise CompileError(f"PDF compile timed out after {timeout} seconds.")
        except OSError as exc:
            raise CompileError(f"Could not run pdflatex ({exe}): {exc}")
        output = (completed.stdout or "") + (completed.stderr or "")
        # MiKTeX often writes the summary to the log file, not to stdout.
        log_path = directory / "resume.log"
        if log_path.exists():
            try:
                output += "\n" + log_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
        if completed.returncode != 0:
            missing = _missing_package(output)
            if missing:
                raise CompileError(
                    f"This server is missing the LaTeX package '{missing}'. "
                    "The bundled Dockerfile installs texlive-latex-extra; redeploy "
                    "with it, or download the .tex file and compile it locally."
                )
            raise CompileError("LaTeX compile failed. " + _first_error(output))
        pdf_path = directory / "resume.pdf"
        if not pdf_path.exists():
            raise CompileError("pdflatex finished but produced no PDF.")
        pdf = pdf_path.read_bytes()
        return CompileResult(pdf=pdf, engine="local-pdflatex",
                             pages=_page_count(output), log=output[-4000:])
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def _ensure_pdf(data: bytes) -> bytes:
    if len(data) < 5 or data[:4] != b"%PDF":
        raise CompileError("The online compiler did not return a PDF.")
    return data


def compile_online(tex: str, endpoint: str = DEFAULT_ONLINE_URL, timeout: int = 120) -> CompileResult:
    """Compile through a third-party service. Uploads the full document (PII included)."""
    if not tex or not tex.strip():
        raise CompileError("LaTeX source is empty.")
    endpoint = (endpoint or DEFAULT_ONLINE_URL).strip()

    if "ytotech" in endpoint.lower():
        return _compile_ytotech(tex, timeout)
    if "latexonline" in endpoint.lower():
        try:
            return _compile_get(tex, endpoint, timeout)
        except CompileError:
            return _compile_ytotech(tex, timeout)
    try:
        return _compile_get(tex, endpoint, timeout)
    except CompileError:
        return _compile_ytotech(tex, timeout)


def _compile_get(tex: str, endpoint: str, timeout: int) -> CompileResult:
    separator = "&" if "?" in endpoint else "?"
    url = endpoint + separator + "command=pdflatex&text=" + urllib.parse.quote(tex, safe="")
    if len(url) > 120_000:
        raise CompileError("The resume is too long for the URL-based online compiler.")
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            data = response.read()
    except Exception as exc:  # noqa: BLE001 - surfaced to the UI
        raise CompileError(f"Online compiler failed: {exc}")
    return CompileResult(pdf=_ensure_pdf(data), engine="online")


def _compile_ytotech(tex: str, timeout: int) -> CompileResult:
    import json

    payload = json.dumps({
        "compiler": "pdflatex",
        "resources": [{"main": True, "content": tex}],
    }).encode("utf-8")
    request = urllib.request.Request(
        DEFAULT_ONLINE_URL, data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/pdf"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read()
    except Exception as exc:  # noqa: BLE001
        raise CompileError(f"Fallback compiler failed: {exc}")
    return CompileResult(pdf=_ensure_pdf(data), engine="online-ytotech")
