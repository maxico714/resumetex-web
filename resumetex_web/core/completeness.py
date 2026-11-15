"""Completeness checks for the details text and generated LaTeX.

Ported from ResumeTex.Core/Generation/ResumeCompleteness.cs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_YEAR_RE = re.compile(r"(19|20)\d{2}|\bpresent\b|\bcurrent\b", re.IGNORECASE)
_ROLE_RE = re.compile(
    r"\b(engineer|developer|analyst|manager|designer|intern|consultant|specialist|trainer|lead|architect|administrator)\b",
    re.IGNORECASE,
)
_EDUCATION_RE = re.compile(
    r"\b(b\.?\s?tech|b\.?\s?e\.?|b\.?\s?sc|m\.?\s?tech|mba|bachelor|master|university|college|degree|diploma)\b",
    re.IGNORECASE,
)
_PLACEHOLDER_RE = re.compile(
    r"\[(Add|Your|Company|Employer|Job|Dates?|Metric|Degree|College|Skills?|Project|Certification|Role)[^\]\r\n]{0,80}\]",
    re.IGNORECASE,
)


@dataclass
class CompletenessReport:
    missing: list[str]
    is_sparse: bool

    def as_dict(self) -> dict:
        return {"missing": self.missing, "isSparse": self.is_sparse}


def analyze(details: str | None) -> CompletenessReport:
    text = (details or "").strip()
    missing: list[str] = []

    if len(text) < 80:
        missing.append("A short professional summary or target role")
    if not _YEAR_RE.search(text):
        missing.append("Job dates (month/year) and at least one role")
    if not _ROLE_RE.search(text):
        missing.append("Your job titles / roles")
    if not _EDUCATION_RE.search(text):
        missing.append("Education: degree, college and year")
    if text.count(",") < 3:
        missing.append("3-5 core skills (comma-separated)")
    if not re.search(r"\d", text):
        missing.append("2-3 quantified achievements (numbers or %)")
    if len(text) < 80 and not missing:
        missing.append("More detail about your experience")

    return CompletenessReport(missing=missing, is_sparse=len(missing) >= 2)


def find_placeholders(latex: str | None) -> list[str]:
    if not latex:
        return []
    seen: list[str] = []
    for match in _PLACEHOLDER_RE.findall(latex):
        value = match.strip()
        if value.lower() not in {s.lower() for s in seen}:
            seen.append(value)
    return seen


def missing_core_sections(body: str | None) -> list[str]:
    if not body or not body.strip():
        return ["All sections"]
    missing: list[str] = []
    for section in ("Professional Summary", "Skills", "Professional Experience", "Education"):
        pattern = re.compile(
            r"\\section\{\s*(?:\\MakeUppercase\{)?\s*" + re.escape(section) + r"\s*\}?\s*\}?",
            re.IGNORECASE)
        if not pattern.search(body):
            missing.append(section)
    return missing
