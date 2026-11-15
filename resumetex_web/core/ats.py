"""Local ATS analyser.

Scores a LaTeX resume body (and optionally a job description) from 0-100 and
returns concrete, actionable issues. Runs entirely server-side on text that has
already been redacted, so no personal data is involved.

The same rules drive the template gallery scores, so "best ATS scored CVs" is a
measured claim, not a marketing one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

CORE_SECTIONS = ("Professional Summary", "Skills", "Professional Experience", "Education")
OPTIONAL_SECTIONS = ("Projects", "Certifications", "Achievements", "Languages")

_FORBIDDEN = (
    ("\\begin{tabular", "Uses a table — many ATS parsers scramble table cells."),
    ("\\begin{multicol", "Uses columns — reading order is not guaranteed."),
    ("\\begin{minipage", "Uses a text box — parsers can drop the content."),
    ("\\includegraphics", "Contains a graphic — graphic text is invisible to parsers."),
    ("\\faIcon", "Uses an icon glyph — it becomes a box or a question mark in the PDF."),
    ("\\fontawesome", "Uses an icon font — same problem as icons."),
    ("\\begin{wrapfigure", "Uses a wrapped figure — breaks linear reading."),
    ("\\put", "Uses picture placement — breaks linear reading."),
)

_ACTION_VERBS = {
    "achieved", "accelerated", "architected", "automated", "built", "collaborated",
    "consolidated", "created", "cut", "decreased", "delivered", "designed", "developed",
    "drove", "eliminated", "engineered", "established", "executed", "expanded", "generated",
    "grew", "implemented", "improved", "increased", "integrated", "introduced", "launched",
    "led", "maintained", "managed", "migrated", "optimized", "orchestrated", "owned",
    "planned", "reduced", "refactored", "resolved", "reviewed", "scaled", "shipped",
    "spearheaded", "standardized", "streamlined", "supported", "trained", "transformed",
    "upgraded", "wrote",
}

_STOPWORDS = {
    "the", "and", "for", "with", "you", "your", "our", "are", "was", "were", "that",
    "this", "from", "have", "has", "had", "not", "but", "all", "can", "will", "would",
    "should", "could", "about", "into", "over", "than", "then", "them", "they", "their",
    "a", "an", "of", "to", "in", "on", "at", "by", "as", "is", "it", "be", "or",
}

_DATE_RE = re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}\b|\b(19|20)\d{2}\b|\bPresent\b|\bCurrent\b", re.IGNORECASE)
_YEAR_ONLY_RE = re.compile(r"\b(19|20)\d{2}\b")
_NUMBER_RE = re.compile(r"\d|%|percent", re.IGNORECASE)
_SECTION_RE = re.compile(r"\\section\{([^}]*)\}")
# \section{\MakeUppercase{Professional Summary}} — the wrapper must not hide the heading.
_SECTION_NAME_RE = re.compile(r"\\MakeUppercase\{([^}]*)\}|\\MakeLowercase\{([^}]*)\}")
_ITEM_RE = re.compile(r"\\item\s+(.+?)(?=\n\s*\\item|\n\s*\\end\{itemize\}|\Z)", re.DOTALL)
_HREF_RE = re.compile(r"\\href\{[^}]*\}\{([^}]*)\}")
_TAG_RE = re.compile(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?")


@dataclass
class Issue:
    severity: str          # "critical" | "warning" | "info"
    message: str
    fix: str
    points: int = 0

    def as_dict(self) -> dict:
        return {"severity": self.severity, "message": self.message, "fix": self.fix, "points": self.points}


@dataclass
class AtsReport:
    score: int
    grade: str
    issues: list[Issue] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "score": self.score,
            "grade": self.grade,
            "issues": [i.as_dict() for i in self.issues],
            "stats": self.stats,
        }


def _strip_latex(text: str) -> str:
    text = re.sub(r"\\begin\{itemize\}(\[[^\]]*\])?", " ", text)
    text = re.sub(r"\\end\{itemize\}", " ", text)
    text = re.sub(r"\\item\s*", " ", text)
    text = re.sub(r"\\section\{([^}]*)\}", r" \1 ", text)
    text = re.sub(r"\\textbf\{([^{}]*)\}", r" \1 ", text)
    text = re.sub(r"\\textit\{([^{}]*)\}", r" \1 ", text)
    text = re.sub(r"\\emph\{([^{}]*)\}", r" \1 ", text)
    text = re.sub(r"\\small\{([^{}]*)\}", r" \1 ", text)
    text = re.sub(r"\\underline\{([^{}]*)\}", r" \1 ", text)
    text = _HREF_RE.sub(r" \1 ", text)
    text = re.sub(r"\\url\{([^}]*)\}", r" \1 ", text)
    text = re.sub(r"\\textbar\{\}", " | ", text)
    text = text.replace(r"\%", "%").replace(r"\&", " ").replace(r"\#", "#")
    text = text.replace(r"\_", "_").replace(r"\$", " ").replace(r"\{", " ").replace(r"\}", " ")
    text = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _keywords(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9+#./-]{1,24}", (text or "").lower())
    out: list[str] = []
    seen: set[str] = set()
    for word in words:
        if word in _STOPWORDS or len(word) < 3:
            continue
        if word not in seen:
            seen.add(word)
            out.append(word)
    return out


def _jd_keywords(jd: str) -> list[str]:
    return [k for k in _keywords(jd) if len(k) > 3][:60]


def _extract_sections(body: str) -> list[str]:
    """Section titles, brace-aware (so \\section{\\MakeUppercase{Profile}} works)."""
    titles: list[str] = []
    index = 0
    marker = "\\section{"
    while True:
        start = body.find(marker, index)
        if start < 0:
            break
        cursor = start + len(marker)
        depth = 1
        while cursor < len(body) and depth:
            char = body[cursor]
            if char == "{" and (cursor == 0 or body[cursor - 1] != "\\"):
                depth += 1
            elif char == "}" and body[cursor - 1] != "\\":
                depth -= 1
            cursor += 1
        titles.append(body[start + len(marker):cursor - 1].strip())
        index = cursor
    return titles


def _section_names(body: str) -> list[str]:
    names: list[str] = []
    for raw in _extract_sections(body):
        inner = _SECTION_NAME_RE.search(raw)
        if inner:
            names.append((inner.group(1) or inner.group(2) or "").strip())
        else:
            names.append(raw.strip())
    return names


def analyze(latex_body: str, job_description: str | None = None) -> AtsReport:
    """Score a LaTeX resume body from 0-100 with concrete issues."""
    body = latex_body or ""
    issues: list[Issue] = []
    score = 0

    sections = _section_names(body)
    section_names = [s.lower() for s in sections]

    # 1. core sections (20)
    found = [s for s in CORE_SECTIONS if s.lower() in section_names]
    score += int(20 * len(found) / len(CORE_SECTIONS))
    for missing in CORE_SECTIONS:
        if missing.lower() not in section_names:
            issues.append(Issue("critical", f"Missing the “{missing}” section.",
                                f"Add a \\section{{{missing}}} block.", 0))

    # 2. forbidden constructs (15)
    penalty = 0
    for needle, message in _FORBIDDEN:
        if needle in body:
            penalty += 5
            issues.append(Issue("critical", message,
                                "Replace it with a plain, linear layout.", 5))
    score += max(0, 15 - penalty)

    # 3. bullet quality (25)
    bullets = [re.sub(r"\s+", " ", m).strip() for m in _ITEM_RE.findall(body)]
    bullets = [b for b in bullets if b]
    quantified = [b for b in bullets if _NUMBER_RE.search(b)]
    share = (len(quantified) / len(bullets)) if bullets else 0.0
    if 6 <= len(bullets) <= 14:
        score += 10
    else:
        issues.append(Issue("warning", f"{len(bullets)} bullets — ATS readers prefer 6-14.",
                            "Keep 2-3 bullets per role, 3 roles maximum.", 4 if bullets else 6))
        score += 4 if bullets else 0
    score += int(10 * share)
    if share < 0.6 and bullets:
        issues.append(Issue("warning", f"Only {int(share*100)}% of bullets contain a number.",
                            "Add a metric, percentage or volume to each bullet.", 4))
    verb_hits = sum(1 for b in bullets
                     if (b.split()[:1] and b.split()[0].lower().strip(",.") in _ACTION_VERBS))
    if bullets:
        verb_ratio = verb_hits / len(bullets)
        score += int(5 * verb_ratio)
        if verb_ratio < 0.7:
            issues.append(Issue("info", "Many bullets do not start with a strong action verb.",
                                "Start each bullet with Built, Led, Reduced, Implemented…", 2))

    # 4. dates (10)
    dates = _DATE_RE.findall(body)
    flat_dates = [d if isinstance(d, str) else d[0] for d in dates]
    if flat_dates:
        score += 5
    else:
        issues.append(Issue("critical", "No dates found in the experience section.",
                            "Add “Mon YYYY - Present” ranges to every role.", 5))
    if re.search(r"\bPresent\b|\bCurrent\b", body, re.IGNORECASE):
        score += 2
    years = [int(y) for y in _YEAR_ONLY_RE.findall(body)]
    if len(years) >= 2:
        ordered = years == sorted(years, reverse=True)
        if ordered:
            score += 3
        else:
            issues.append(Issue("warning", "Roles are not in reverse-chronological order.",
                                "Put the current role first.", 3))

    # 5. length (10)
    plain = _strip_latex(body)
    words = len(plain.split())
    if words <= 700:
        score += 10
    elif words <= 900:
        score += 6
        issues.append(Issue("warning", f"{words} words — a one-page CV should stay under 700.",
                            "Cut the oldest bullets, then optional sections.", 4))
    else:
        score += 2
        issues.append(Issue("critical", f"{words} words — this will not fit one page.",
                            "Cut the oldest bullets, then optional sections.", 8))

    # 6. skills block (10)
    if "skills" in section_names:
        score += 5
        skill_lines = 0
        for name in sections:
            if name.lower() == "skills":
                block = body.split("\\section{" + name, 1)[-1]
                block = block.split("\\section{", 1)[0]
                skill_lines = len([ln for ln in block.split("\n") if ln.strip()])
        if skill_lines >= 4:
            score += 5
        else:
            issues.append(Issue("info", "Skills are not grouped into named lines.",
                                "Use 4 lines: Languages, Frameworks, Cloud and Data, Practices.", 3))
    else:
        issues.append(Issue("critical", "No Skills section.", "Add a Skills section.", 5))

    # 7. optional sections (5)
    score += min(5, 2 * len([s for s in OPTIONAL_SECTIONS if s.lower() in section_names]))

    # 8. JD keyword coverage (15, only when a JD is supplied)
    coverage = None
    if job_description and job_description.strip():
        wanted = _jd_keywords(job_description)
        if wanted:
            haystack = plain.lower()
            hits = [k for k in wanted if k in haystack]
            coverage = round(len(hits) / len(wanted) * 100)
            score += int(15 * len(hits) / len(wanted))
            if coverage < 60:
                issues.append(Issue("warning", f"Only {coverage}% of the job's keywords appear in the CV.",
                                    "Mirror the JD's exact wording for the skills it lists.", 5))

    score = max(0, min(100, score))
    grade = ("A" if score >= 90 else "B" if score >= 80 else "C" if score >= 70
             else "D" if score >= 60 else "E")
    stats = {
        "sections": sections,
        "bullets": len(bullets),
        "quantifiedBullets": len(quantified),
        "quantifiedShare": round(share, 2),
        "words": words,
        "dates": len(flat_dates),
        "keywordCoverage": coverage,
    }
    return AtsReport(score=score, grade=grade, issues=issues, stats=stats)


def grade_label(grade: str) -> str:
    return {
        "A": "Excellent — beats most submitted CVs",
        "B": "Strong — a small number of fixes would make it excellent",
        "C": "Average — fix the flagged issues before sending",
        "D": "Below average — rework structure and bullets",
        "E": "Poor — rebuild from the template gallery",
    }.get(grade, "")
