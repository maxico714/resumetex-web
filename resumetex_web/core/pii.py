"""PII redaction and the leak gate.

Ported from ResumeTex.Core/Privacy/PiiRedactor.cs so the web app and the
desktop app behave identically. The browser runs the same rules (static/js/redact.js);
tests/test_parity.py asserts both implementations agree.

Rule: contact details are personal data. They are inserted into the LaTeX header
locally and must never travel to an AI provider.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, Iterator, Sequence

REDACT_NAME = "the candidate"
REDACT_EMAIL = "the candidate's email"
REDACT_PHONE = "the candidate's phone number"
REDACT_LOCATION = "the candidate's location"
REDACT_LINKEDIN = "the candidate's LinkedIn profile"
REDACT_GITHUB = "the candidate's GitHub profile"
REDACT_PORTFOLIO = "the candidate's portfolio link"
REDACT_PROFILE = "the candidate's profile"

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# 8-15 digits, allowing spaces, dots, dashes and parentheses.
_PHONE_RE = re.compile(r"(?<![\d])\+?\d[\d\s().\-]{6,}\d(?![\d])")
_YEAR_RANGE_RE = re.compile(r"^\s*\+?\s*(19|20)\d{2}\s*[-–—]{1,2}\s*(19|20)\d{2}\s*$")
_DECIMAL_RE = re.compile(r"^\d+(\.\d+)+$")


class PiiLeakError(Exception):
    """Raised when a known personal value survived redaction."""


@dataclass(frozen=True)
class PiiFields:
    """The personal fields the user types in. Local use only."""

    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""

    def filled(self) -> Iterator[tuple[str, str]]:
        for label, value in (
            ("name", self.name),
            ("email", self.email),
            ("phone", self.phone),
            ("location", self.location),
            ("LinkedIn", self.linkedin),
            ("GitHub", self.github),
            ("portfolio", self.portfolio),
        ):
            value = (value or "").strip()
            if value:
                yield label, value

    @property
    def has_any_contact(self) -> bool:
        return any(
            (self.email or self.phone or self.location or self.linkedin
             or self.github or self.portfolio).strip()
            for _ in (0,)
        )


@dataclass
class RedactionResult:
    text: str
    replacement_count: int = 0
    details: list[str] = field(default_factory=list)


def _word_pattern(value: str) -> str:
    """Word-boundary pattern that works for non-ASCII letters and digits."""
    escaped = re.escape(value)
    return rf"(?<![^\W_]){escaped}(?![^\W_])"


def _has_word(text: str, term: str) -> bool:
    return bool(re.search(_word_pattern(term), text, re.IGNORECASE | re.UNICODE))


def _split_terms(value: str) -> list[str]:
    """Split a field into words on any non-letter/non-digit boundary."""
    parts = re.split(r"[^\w]+", value, flags=re.UNICODE)
    seen: set[str] = set()
    out: list[str] = []
    for part in parts:
        if len(part) < 2:
            continue
        key = part.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(part)
    return out


def _link_handles(value: str) -> list[str]:
    """Return the handle of a profile URL (path only, never query or fragment)."""
    raw = (value or "").strip()
    if not raw:
        return []

    path = raw
    scheme = raw.find("://")
    if scheme >= 0:
        after = raw[scheme + 3:]
        slash = after.find("/")
        path = after[slash:] if slash >= 0 else ""

    cut = len(path)
    for ch in ("?", "#"):
        idx = path.find(ch)
        if idx >= 0:
            cut = min(cut, idx)
    path = path[:cut]

    parts = [p for p in path.split("/") if p]
    if not parts:
        return []
    last = parts[-1].lstrip("@")
    if len(last) < 2:
        return []
    if last.lower() == raw.lower():
        return []
    return [last]


def _digits_only(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def _count_digits(value: str) -> int:
    return sum(1 for ch in value if ch.isdigit())


class PiiRedactor:
    """Removes every known personal value from free text before it is sent."""

    def __init__(self, pii: PiiFields):
        self.pii = pii

    # -- replacements -------------------------------------------------

    def _replacements(self) -> list[tuple[str, str, str]]:
        """(value, pattern, replacement) triples; longest value wins."""
        out: list[tuple[str, str, str]] = []
        for label, value in self.pii.filled():
            if label == "name":
                if len(value) >= 2:
                    out.append((value, _word_pattern(value), REDACT_NAME))
                for part in _split_terms(value):
                    out.append((part, _word_pattern(part), REDACT_NAME))
            elif label == "email":
                out.append((value, re.escape(value), REDACT_EMAIL))
            elif label == "phone":
                out.append((value, re.escape(value), REDACT_PHONE))
            elif label == "location":
                if len(value) >= 2:
                    out.append((value, _word_pattern(value), REDACT_LOCATION))
                for part in _split_terms(value):
                    out.append((part, _word_pattern(part), REDACT_LOCATION))
            elif label == "LinkedIn":
                out.append((value, re.escape(value), REDACT_LINKEDIN))
            elif label == "GitHub":
                out.append((value, re.escape(value), REDACT_GITHUB))
            elif label == "portfolio":
                out.append((value, re.escape(value), REDACT_PORTFOLIO))

            for handle in _link_handles(value):
                out.append((handle, re.escape(handle), REDACT_PROFILE))
        return out

    def redact(self, text: str) -> RedactionResult:
        result = text or ""
        count = 0
        details: list[str] = []

        # Longest values first so a full URL wins over its handle.
        for value, pattern, replacement in sorted(self._replacements(), key=lambda r: -len(r[0])):
            regex = re.compile(pattern, re.IGNORECASE | re.UNICODE)
            found = len(regex.findall(result))
            if found:
                count += found
                details.append(f"{value} -> {replacement} ({found}x)")
            result = regex.sub(replacement.replace("\\", "\\\\"), result)

        # Safety net: any other email address.
        emails = _EMAIL_RE.findall(result)
        if emails:
            count += len(emails)
            details.append(f"{len(emails)} email(s) -> {REDACT_EMAIL}")
        result = _EMAIL_RE.sub(REDACT_EMAIL, result)

        # Safety net: any other phone-like number.
        def _phone_sub(match: re.Match[str]) -> str:
            nonlocal count
            value = match.group(0)
            digits = _count_digits(value)
            if digits < 8 or digits > 15:
                return value
            if _YEAR_RANGE_RE.match(value):
                return value
            if _DECIMAL_RE.match(value):
                return value
            count += 1
            return REDACT_PHONE

        result = _PHONE_RE.sub(_phone_sub, result)

        self.verify_no_pii(result)
        return RedactionResult(text=result, replacement_count=count, details=details)

    # -- gate ---------------------------------------------------------

    def verify_no_pii(self, text: str) -> None:
        """Raise PiiLeakError when any known personal value is still present."""
        for label, value in self.pii.filled():
            if label in ("email", "LinkedIn", "GitHub", "portfolio"):
                if len(value) >= 2 and value.lower() in text.lower():
                    raise PiiLeakError(f"The {label} value is still present after redaction.")
                for handle in _link_handles(value):
                    if handle.lower() in text.lower():
                        raise PiiLeakError(f"The {label} handle is still present after redaction.")
            elif label == "phone":
                digits = _digits_only(value)
                if len(digits) >= 7 and digits in _digits_only(text):
                    raise PiiLeakError("The phone number is still present after redaction.")
            else:
                if len(value) < 2:
                    continue
                if _has_word(text, value):
                    raise PiiLeakError(f"The {label} value is still present after redaction.")
                for term in _split_terms(value):
                    if _has_word(text, term):
                        raise PiiLeakError(f"The {label} value is still present after redaction.")

        if _EMAIL_RE.search(text):
            raise PiiLeakError("An email address is still present after redaction.")


def normalize_typography(value: str) -> str:
    """Normalise smart punctuation that stock pdflatex rejects."""
    if not value:
        return ""
    return (
        value.replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201C", '"')
        .replace("\u201D", '"')
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2026", ".")
        .replace("\u00A0", " ")
        .replace("\u200B", "")
    )


def contains_non_latin(value: str) -> bool:
    """True when the text contains characters the Latin templates cannot render."""
    return any(ch > "\u024f" and not ch.isspace() for ch in (value or ""))
