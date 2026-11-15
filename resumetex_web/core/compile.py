"""PDF compilation.

Local mode runs the user's own pdflatex (MiKTeX / TeX Live) exactly like the
desktop app: the document never leaves the machine. Online mode is opt-in and
warns, because it uploads the whole document including contact details.

Ported from ResumeTex.Core/Compilation/*.cs
"""

from __future__ import annotations

import os
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


def _first_error(output: str) -> str:
    for line in (output or "").splitlines():
        trimmed = line.strip()
        if trimmed.startswith("!") or "error:" in trimmed.lower():
            return trimmed[:300]
    compact = (output or "").strip().replace("\r", "")
    return (compact[:300] if compact else "pdflatex reported an error.")


def _page_count(log: str) -> int:
    import re
    # MiKTeX wraps the line, e.g. "Output written on ...pdf (\n1 page, ...)"
    flat = re.sub(r"\s+", " ", log or "")
    match = re.search(r"Output written on .*?\((\d+)\s+pages?", flat)
    return int(match.group(1)) if match else 0


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
        output = (completed.stdout or "") + (completed.stderr or "")
        # MiKTeX often writes the summary to the log file, not to stdout.
        log_path = directory / "resume.log"
        if log_path.exists():
            try:
                output += "\n" + log_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
        if completed.returncode != 0:
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
