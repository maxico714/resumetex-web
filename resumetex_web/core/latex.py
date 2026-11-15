"""LaTeX primitives: escaping, sanitising AI output, the local header, composition.

Ported from ResumeTex.Core/Latex/*.cs. The contact header is always built here,
locally, so PII never travels through an AI request.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .pii import PiiFields, normalize_typography

# ---------------------------------------------------------------- escaping

_TEXT_ESCAPES = {
    "\\": r"\textbackslash{}",
    "{": r"\{",
    "}": r"\}",
    "$": r"\$",
    "&": r"\&",
    "#": r"\#",
    "_": r"\_",
    "%": r"\%",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def escape_text(value: str | None) -> str:
    """Escape user text for LaTeX text mode (single pass)."""
    if not value:
        return ""
    source = normalize_typography(value).replace("\r\n", "\n").replace("\r", "\n")
    out = []
    for ch in source:
        out.append(_TEXT_ESCAPES.get(ch, ch))
    return "".join(out)


def escape_url(value: str | None) -> str:
    """Escape a URL for \\url{} or the first argument of \\href{}{}."""
    if not value:
        return ""
    s = value.strip().replace("\\", "/")
    s = (s.replace("{", "%7B").replace("}", "%7D").replace("$", "%24")
          .replace("^", "%5E").replace("~", "%7E").replace(" ", "%20"))
    s = (s.replace("%", r"\%").replace("#", r"\#").replace("&", r"\&")
          .replace("_", r"\_"))
    return s


def display_url(value: str | None) -> str:
    if not value or not value.strip():
        return ""
    s = value.strip()
    for prefix in ("https://", "http://"):
        if s.lower().startswith(prefix):
            s = s[len(prefix):]
            break
    return s.rstrip("/")


def normalize_url(value: str | None, fallback_host: str) -> str:
    if not value or not value.strip():
        return ""
    s = value.strip()
    if s.lower().startswith(("http://", "https://")):
        return s
    if "." in s and " " not in s:
        return "https://" + s.lstrip("/")
    return "https://" + fallback_host + "/" + s.lstrip("/")


# ------------------------------------------------------------- sanitising

_FENCE_RE = re.compile(r"```(?:latex|tex)?\s*([\s\S]*?)```", re.IGNORECASE)
_LEADING_CENTER_RE = re.compile(r"^\s*\\begin\{center\}[\s\S]*?\\end\{center\}", re.IGNORECASE)
_ANY_CENTER_RE = re.compile(r"\\begin\{center\}[\s\S]*?\\end\{center\}", re.IGNORECASE)
_BLOCKED_COMMAND_RE = re.compile(
    r"\\(input|include|includegraphics|openin|openout|write|read|special|directlua|catcode"
    r"|def|newcommand|renewcommand|providecommand|usepackage|documentclass|csname|immediate"
    r"|RequirePackage|graphicspath|bibliography|addbibresource)(?![A-Za-z])",
    re.IGNORECASE,
)
_PREAMBLE_LINE_RE = re.compile(
    r"^\s*\\(usepackage|documentclass|begin\{document\}|end\{document\}|maketitle|pagestyle|thispagestyle)\b",
    re.IGNORECASE,
)


class LaTeXRejected(Exception):
    """Raised when model output cannot be safely reduced to a resume body."""


def sanitize_ai_output(raw: str) -> str:
    """Reduce untrusted model output to a safe LaTeX section body."""
    if not raw or not raw.strip():
        raise LaTeXRejected("The AI returned an empty response.")

    text = normalize_typography(raw.strip())

    fence = _FENCE_RE.search(text)
    if fence:
        text = fence.group(1).strip()

    # Drop comment lines before looking for an invented contact block.
    text = "\n".join(
        line for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if not line.lstrip().startswith("%")
    )

    begin = text.find(r"\begin{document}")
    if begin >= 0:
        end = text.find(r"\end{document}", begin)
        start = begin + len(r"\begin{document}")
        text = (text[start:end] if end > start else text[start:]).strip()

    text = _LEADING_CENTER_RE.sub("", text).strip()
    text = _ANY_CENTER_RE.sub("", text).strip()

    first_section = text.find(r"\section")
    if first_section > 0:
        text = text[first_section:]

    lines = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if _PREAMBLE_LINE_RE.match(line):
            continue
        if "mailto:" in line.lower():
            continue
        lines.append(line)
    text = "\n".join(lines).strip()

    if not text:
        raise LaTeXRejected("The AI returned no usable resume sections. Try again.")

    blocked = _BLOCKED_COMMAND_RE.search(text)
    if blocked:
        raise LaTeXRejected(
            f"The AI response contained a blocked LaTeX command ({blocked.group(0)}). Generation was stopped."
        )

    if r"\section" not in text:
        text = r"\section{Details}" + "\n" + text
    return text


# ----------------------------------------------------------------- header

@dataclass(frozen=True)
class HeaderStyle:
    name_command: str
    separator: str


def build_header(style: str, pii: PiiFields) -> str:
    """Build the contact header locally so PII never travels through the AI."""
    name = (pii.name or "").strip() or "Name"
    if style == "navy":
        name_line = r"{\color{navyblue}\LARGE\bfseries " + escape_text(name) + "}"
    elif style == "times":
        name_line = r"{\color{linkcolour}\Large\bfseries " + escape_text(name) + "}"
    elif style == "compact":
        name_line = r"{\Large\bfseries " + escape_text(name) + "}"
    else:
        name_line = r"{\LARGE\bfseries " + escape_text(name) + "}"

    primary: list[str] = []
    links: list[str] = []

    if (pii.location or "").strip():
        primary.append(escape_text(pii.location.strip()))
    if (pii.email or "").strip():
        primary.append(_link("mailto:" + pii.email.strip(), pii.email.strip()))
    if (pii.phone or "").strip():
        primary.append(escape_text(pii.phone.strip()))
    if (pii.linkedin or "").strip():
        links.append(_link(normalize_url(pii.linkedin, "linkedin.com/in"), display_url(pii.linkedin)))
    if (pii.github or "").strip():
        links.append(_link(normalize_url(pii.github, "github.com"), display_url(pii.github)))
    if (pii.portfolio or "").strip():
        links.append(_link(normalize_url(pii.portfolio, "example.com"), display_url(pii.portfolio)))

    separator = r" \,\(\cdot\)\, " if style == "times" else r" $|$ "
    lines: list[str] = []
    if primary:
        lines.append(separator.join(primary))
    if links:
        lines.append(separator.join(links))

    body = ["\\begin{center}"]
    body.append(f"{name_line}\\\\[2pt]")
    for index, line in enumerate(lines):
        body.append("\\small " + line + ("\\\\" if index < len(lines) - 1 else ""))
    body.append("\\end{center}")
    return "\n".join(body)


def _link(url: str, display: str) -> str:
    return "\\href{" + escape_url(url) + "}{\\underline{" + escape_text(display) + "}}"


# --------------------------------------------------------------- templates

NAVY_SHELL = r"""% ResumeTeX template: navy. Single column, ATS-friendly, pdflatex.
\documentclass[11pt]{article}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage[left=0.75in,top=0.6in,right=0.75in,bottom=0.6in]{geometry}
\usepackage{xcolor}
\usepackage{titlesec}
\usepackage{enumitem}
\usepackage{microtype}
\usepackage[hidelinks]{hyperref}
\IfFileExists{glyphtounicode.tex}{\input{glyphtounicode}}{}
\ifdefined\pdfgentounicode\pdfgentounicode=1\fi
\definecolor{navyblue}{RGB}{0,54,123}
\pagestyle{empty}
\raggedbottom
\raggedright
\urlstyle{same}
\titleformat{\section}{\color{navyblue}\large\bfseries}{}{0em}{}[\color{navyblue}\titlerule \vspace{-4pt}]
\begin{document}
%%HEADER%%
%%BODY%%
\end{document}
"""

MINIMAL_SHELL = r"""% ResumeTeX template: minimal. No tables, fully linear, maximum ATS parseability.
\documentclass[letterpaper,11pt]{article}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage[left=0.7in,right=0.7in,top=0.55in,bottom=0.55in]{geometry}
\usepackage{titlesec}
\usepackage{enumitem}
\usepackage{xcolor}
\usepackage{microtype}
\usepackage[hidelinks]{hyperref}
\IfFileExists{glyphtounicode.tex}{\input{glyphtounicode}}{}
\ifdefined\pdfgentounicode\pdfgentounicode=1\fi
\definecolor{softgray}{HTML}{6B7280}
\pagestyle{empty}
\raggedbottom
\raggedright
\urlstyle{same}
\titleformat{\section}{\vspace{-2pt}\large\bfseries}{}{0em}{}[\color{softgray}\titlerule \vspace{-4pt}]
\begin{document}
%%HEADER%%
%%BODY%%
\end{document}
"""

COMPACT_SHELL = r"""% ResumeTeX template: compact. Dense 10pt layout for students and freshers.
\documentclass[10pt]{article}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage[margin=0.5in]{geometry}
\usepackage{titlesec}
\usepackage{enumitem}
\usepackage{xcolor}
\usepackage{microtype}
\usepackage[hidelinks]{hyperref}
\IfFileExists{glyphtounicode.tex}{\input{glyphtounicode}}{}
\ifdefined\pdfgentounicode\pdfgentounicode=1\fi
\pagestyle{empty}
\raggedbottom
\raggedright
\urlstyle{same}
\titleformat{\section}{\raggedright\normalsize\bfseries}{}{0em}{}[\titlerule]
\begin{document}
%%HEADER%%
%%BODY%%
\end{document}
"""

PROJECTS_SHELL = r"""% ResumeTeX template: projects. Wide margins with a large Projects section.
\documentclass[10pt]{article}
\usepackage[T1]{fontenc}
\usepackage{helvet}
\renewcommand{\familydefault}{\sfdefault}
\usepackage[left=0.7in,right=0.7in,top=0.55in,bottom=0.55in]{geometry}
\usepackage{titlesec}
\usepackage{enumitem}
\usepackage{xcolor}
\usepackage{microtype}
\usepackage[hidelinks]{hyperref}
\IfFileExists{glyphtounicode.tex}{\input{glyphtounicode}}{}
\ifdefined\pdfgentounicode\pdfgentounicode=1\fi
\pagestyle{empty}
\raggedbottom
\raggedright
\urlstyle{same}
\titleformat{\section}{\raggedright\normalsize\bfseries}{}{0em}{}[\titlerule]
\begin{document}
%%HEADER%%
%%BODY%%
\end{document}
"""

TIMES_SHELL = r"""% ResumeTeX template: times. Serif academic look with ruled sections.
\documentclass[a4paper,11pt]{article}
\usepackage[T1]{fontenc}
\IfFileExists{newtxtext.sty}{\usepackage{newtxmath,newtxtext}}{\usepackage{lmodern}}
\usepackage[left=0.8in,right=0.8in,top=0.55in,bottom=0.55in]{geometry}
\usepackage{parskip}
\usepackage{titlesec}
\usepackage{enumitem}
\usepackage{xcolor}
\usepackage{microtype}
\usepackage[hidelinks]{hyperref}
\IfFileExists{glyphtounicode.tex}{\input{glyphtounicode}}{}
\ifdefined\pdfgentounicode\pdfgentounicode=1\fi
\definecolor{linkcolour}{RGB}{0,51,153}
\pagestyle{empty}
\raggedright
\urlstyle{same}
\titleformat{\section}{\color{black}\large\bfseries}{}{0em}{}[\color{linkcolour}\titlerule]
\titlespacing{\section}{0pt}{3pt}{3pt}
\parindent=0pt
\begin{document}
%%HEADER%%
%%BODY%%
\end{document}
"""

HOUSE_SHELLS: dict[str, str] = {
    "navy": NAVY_SHELL,
    "minimal": MINIMAL_SHELL,
    "compact": COMPACT_SHELL,
    "projects": PROJECTS_SHELL,
    "times": TIMES_SHELL,
}

STYLE_LABELS = {
    "auto": "Auto",
    "navy": "Navy",
    "minimal": "Minimal",
    "compact": "Compact",
    "projects": "Projects",
    "times": "Times",
}

STYLE_DESCRIPTIONS = {
    "auto": "Picks a suitable house style from your details.",
    "navy": "Formal navy headings, centered contact line. General professional use.",
    "minimal": "Fully linear, no tables, maximum ATS parseability.",
    "compact": "Dense 10pt layout for students and freshers.",
    "projects": "Wide margins with a large Projects section for developers.",
    "times": "Serif academic look with ruled sections.",
}


def get_shell(style: str) -> str:
    return HOUSE_SHELLS.get(style, NAVY_SHELL)


def resolve_style(requested: str, details: str) -> str:
    """Deterministic auto-selection so the same input always yields the same style."""
    if requested and requested != "auto":
        return requested
    text = details or ""
    if "project" in text.lower() and text.lower().index("project") < len(text) / 2:
        return "projects"
    if len(text) < 700:
        return "compact"
    return "navy"


def compose(style: str, pii: PiiFields, body: str) -> str:
    """Join a local shell + local PII header + generated body into one document."""
    if not body or not body.strip():
        raise ValueError("Resume body is empty.")
    shell = get_shell(style)
    header = build_header(style, pii)
    doc = shell.replace("%%HEADER%%", header).replace("%%BODY%%", body.strip())
    if "%%HEADER%%" in doc or "%%BODY%%" in doc:
        raise LaTeXRejected("Template placeholders were not resolved.")
    return doc.rstrip() + "\n"


# ------------------------------------------------------- plain text bridge

def body_to_plain_text(body: str) -> str:
    """Convert a LaTeX resume body to editable plain text (for the page editor)."""
    if not body or not body.strip():
        return ""
    text = body.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\\section\{([^}]*)\}", lambda m: "\n" + m.group(1).strip() + "\n", text)
    text = re.sub(r"\\begin\{itemize\}(\[[^\]]*\])?", "", text)
    text = re.sub(r"\\end\{itemize\}", "", text)
    text = re.sub(r"\\item\s*", "- ", text)
    text = text.replace(r"\hfill", " | ")
    text = re.sub(r"[ \t]*\|[ \t]*", " | ", text)
    for command in ("textbf", "textit", "emph", "underline", "small"):
        text = re.sub(r"\\" + command + r"\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\href\{[^}]*\}\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\url\{([^}]*)\}", r"\1", text)
    text = text.replace(r"\textbar{}", "|")
    text = (text.replace(r"\%", "%").replace(r"\&", "&").replace(r"\#", "#")
                .replace(r"\_", "_").replace(r"\$", "$").replace(r"\{", "{").replace(r"\}", "}"))
    text = text.replace("\\\\", "\n")
    text = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", "", text)
    text = text.replace("{", "").replace("}", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
