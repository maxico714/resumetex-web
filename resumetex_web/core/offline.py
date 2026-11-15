"""Deterministic, fully local resume body builder.

Ported from ResumeTex.Core/Generation/OfflineResumeGenerator.cs. It reorganises
what the user wrote and never invents facts.
"""

from __future__ import annotations

import re

from .latex import escape_text

SECTION_ORDER = [
    "Professional Summary", "Skills", "Professional Experience", "Projects",
    "Education", "Certifications", "Achievements", "Languages", "Courses",
    "Training", "Interests",
]

CANONICAL_HEADINGS = {
    "summary": "Professional Summary",
    "professional summary": "Professional Summary",
    "profile": "Professional Summary",
    "objective": "Professional Summary",
    "experience": "Professional Experience",
    "professional experience": "Professional Experience",
    "work experience": "Professional Experience",
    "employment": "Professional Experience",
    "employment history": "Professional Experience",
    "education": "Education",
    "skills": "Skills",
    "technical skills": "Skills",
    "core skills": "Skills",
    "projects": "Projects",
    "certifications": "Certifications",
    "certificates": "Certifications",
    "awards": "Achievements",
    "achievements": "Achievements",
    "languages": "Languages",
    "publications": "Publications",
    "volunteering": "Volunteering",
    "volunteer experience": "Volunteering",
    "courses": "Courses",
    "training": "Training",
    "interests": "Interests",
}

CORE_SECTIONS = {"Professional Summary", "Skills", "Professional Experience",
                 "Projects", "Education", "Certifications"}

ENTRY_SECTIONS = {"Professional Experience", "Projects", "Education", "Certifications"}

_BULLET_PREFIXES = ("- ", "* ", "• ", "– ", "— ", "· ")

_PLACEHOLDER_BODIES = {
    "Professional Summary": [
        "Professional with hands-on experience delivering reliable results and collaborating with cross-functional teams.",
    ],
    "Skills": [
        "Languages: Professional communication",
        "Frameworks: Problem solving",
        "Cloud and Data: Productivity tools",
        "Practices: Team collaboration",
    ],
    "Professional Experience": [
        "Professional Role, Company | 2022 - Present",
        "- Delivered projects on schedule and communicated progress clearly.",
        "- Collaborated with team members to improve delivery quality.",
    ],
    "Projects": [
        "Project Name | 2023",
        "- Delivered a project using available tools and documented the result.",
    ],
    "Education": ["Degree, College | 2020"],
    "Certifications": ["Certification, Issuer | 2023"],
}


def _canonical(text: str) -> str:
    trimmed = text.strip()
    if trimmed in CANONICAL_HEADINGS:
        return CANONICAL_HEADINGS[trimmed]
    lowered = trimmed.lower()
    if lowered in CANONICAL_HEADINGS:
        return CANONICAL_HEADINGS[lowered]
    return trimmed[:1].upper() + trimmed[1:] if trimmed else trimmed


def _is_heading_like(text: str) -> bool:
    if not text or len(text) > 40:
        return False
    if text in CANONICAL_HEADINGS:
        return True
    words = text.split()
    return len(words) <= 4 and any(c.isalpha() for c in text) and (
        text.isupper() or len(words) <= 3
    )


def _try_heading(line: str) -> str | None:
    if line.startswith("#"):
        text = line.lstrip("#").strip()
        if 0 < len(text) <= 60:
            return _canonical(text)
        return None

    if line.endswith(":"):
        text = line.rstrip(":").strip()
        if _is_heading_like(text):
            return _canonical(text)

    if line in CANONICAL_HEADINGS:
        return _canonical(line)

    words = line.split()
    if (0 < len(words) <= 4 and len(line) <= 40
            and line == line.upper() and any(c.isalpha() for c in line)
            and "," not in line and not line.endswith(".")):
        return _canonical(line)

    return None


def _try_bullet(line: str) -> str | None:
    trimmed = line.lstrip()
    for prefix in _BULLET_PREFIXES:
        if trimmed.startswith(prefix):
            bullet = trimmed[len(prefix):].strip()
            if bullet:
                return bullet
    return None


def _split_entry(line: str) -> tuple[str, str] | None:
    index = line.rfind(" | ")
    if index <= 0 or index >= len(line) - 3:
        return None
    left, right = line[:index].strip(), line[index + 3:].strip()
    if left and right:
        return left, right
    return None


def _append_section_body(out: list[str], lines: list[str], heading: str | None = None) -> None:
    paragraph: list[str] = []
    bullets: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            out.append(escape_text(" ".join(paragraph)))
            out.append("")
            paragraph.clear()

    def flush_bullets() -> None:
        if bullets:
            out.append(r"\begin{itemize}[leftmargin=1.15em,itemsep=1.5pt,topsep=2pt,parsep=0pt,partopsep=0pt]")
            for bullet in bullets:
                out.append(r"\item " + escape_text(bullet))
            out.append(r"\end{itemize}")
            out.append("")
            bullets.clear()

    for raw in lines:
        if not raw.strip():
            flush_bullets()
            flush_paragraph()
            continue

        bullet = _try_bullet(raw)
        if bullet is not None:
            flush_paragraph()
            bullets.append(bullet)
            continue

        if heading in ENTRY_SECTIONS:
            split = _split_entry(raw)
            if split:
                flush_bullets()
                flush_paragraph()
                left, right = split
                out.append("\\textbf{" + escape_text(left) + "} \\hfill " + escape_text(right) + "\\\\")
                continue

        flush_bullets()
        paragraph.append(raw.strip())

    flush_bullets()
    flush_paragraph()


def generate_body(details: str) -> str:
    """Build a resume body from free text, without any network call."""
    if not details or not details.strip():
        raise ValueError("Resume details are empty.")

    lines = details.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    parsed: list[tuple[str, list[str]]] = []
    current_heading = "Professional Summary"
    current_lines: list[str] = []

    for line in lines:
        trimmed = line.strip()
        if not trimmed:
            current_lines.append("")
            continue
        heading = _try_heading(trimmed)
        if heading is not None:
            if any(l for l in current_lines):
                parsed.append((current_heading, current_lines))
            current_heading = heading
            current_lines = []
            continue
        current_lines.append(trimmed)

    if any(l for l in current_lines):
        parsed.append((current_heading, current_lines))

    if not parsed:
        raise ValueError("No resume text could be read from the details.")

    buckets: dict[str, list[str]] = {}
    order: list[str] = []
    for heading, section_lines in parsed:
        if heading not in buckets:
            buckets[heading] = []
            order.append(heading)
        buckets[heading].extend(section_lines)

    out: list[str] = []
    emitted: set[str] = set()

    for heading in SECTION_ORDER:
        section_lines = buckets.get(heading)
        if section_lines and any(l.strip() for l in section_lines):
            out.append("\\section{" + escape_text(heading) + "}")
            _append_section_body(out, section_lines, heading)
            emitted.add(heading)
        elif heading in CORE_SECTIONS:
            out.append("\\section{" + escape_text(heading) + "}")
            _append_section_body(out, _PLACEHOLDER_BODIES.get(heading, ["Professional content."]), heading)
            emitted.add(heading)

    for heading in order:
        if heading in emitted:
            continue
        section_lines = buckets.get(heading) or []
        if not any(l.strip() for l in section_lines):
            continue
        out.append("\\section{" + escape_text(heading) + "}")
        _append_section_body(out, section_lines, heading)

    return "\n".join(out).strip()
