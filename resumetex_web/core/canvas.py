"""Canvas mode: structured data -> LaTeX, with no AI and no network.

This is the "no API key" path. The user fills fields, picks a layout preset from
the gallery, and the renderer writes the document locally. The same presets are
used by the AI path so the look is identical whichever route produced the data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from .latex import display_url, escape_text, escape_url, normalize_url


@dataclass
class LayoutPreset:
    """Everything the renderer needs to lay out a resume."""

    id: str
    name: str
    ats_class: str = "ats"                 # "ats" | "creative"
    best_for: list[str] = field(default_factory=list)
    summary: str = ""
    why: str = ""

    # document
    doc_class: str = "article"
    class_options: str = "11pt"
    geometry: str = "left=0.75in,top=0.6in,right=0.75in,bottom=0.6in"
    font_lines: list[str] = field(default_factory=lambda: ["\\usepackage{lmodern}"])
    extra_packages: list[str] = field(default_factory=lambda: ["xcolor", "titlesec", "enumitem", "microtype"])
    accent: str | None = None               # colour name used for headings/rules
    accent_rgb: str | None = None           # RGB triple, when the accent is new
    section_title: str = "bold-rule"        # smallcaps | bold-rule | bold | upper-rule
    section_sizes: str = ""
    header_style: str = "centered"          # centered | left | two-column
    entry_style: str = "bold-hfill"         # bold-hfill | bold-title | title-meta
    bullet_options: str = "leftmargin=1.15em,itemsep=1.5pt,topsep=2pt,parsep=0pt,partopsep=0pt"
    section_order: list[str] = field(default_factory=lambda: [
        "Professional Summary", "Skills", "Professional Experience", "Projects",
        "Education", "Certifications", "Achievements", "Languages",
    ])
    line_spacing: str = ""
    notes: str = ""

    def as_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "atsClass": self.ats_class,
            "bestFor": self.best_for, "summary": self.summary, "why": self.why,
            "notes": self.notes, "sectionOrder": self.section_order,
            "headerStyle": self.header_style, "entryStyle": self.entry_style,
        }


def _color_lines(preset: LayoutPreset) -> list[str]:
    lines: list[str] = []
    if preset.accent and preset.accent_rgb:
        lines.append(f"\\definecolor{{{preset.accent}}}{{RGB}}{{{preset.accent_rgb}}}")
    return lines


def build_preamble(preset: LayoutPreset) -> str:
    lines = [f"\\documentclass[{preset.class_options}]{{{preset.doc_class}}}"]
    lines.append("\\usepackage[T1]{fontenc}")
    lines.extend(preset.font_lines)
    lines.append(f"\\usepackage[{preset.geometry}]{{geometry}}")
    # hyperref is loaded before titlesec: this is the combination that compiles
    # with stock MiKTeX/TeX Live and keeps titlesec's internals intact.
    lines.append("\\usepackage[hidelinks]{hyperref}")
    for package in preset.extra_packages:
        lines.append(f"\\usepackage{{{package}}}")
    lines.append("\\IfFileExists{glyphtounicode.tex}{\\input{glyphtounicode}}{}")
    lines.append("\\ifdefined\\pdfgentounicode\\pdfgentounicode=1\\fi")
    lines.extend(_color_lines(preset))
    lines.append("\\pagestyle{empty}")
    lines.append("\\raggedbottom")
    lines.append("\\raggedright")
    lines.append("\\urlstyle{same}")
    if preset.line_spacing:
        lines.append(f"\\linespread{{{preset.line_spacing}}}")
    lines.append(_section_format(preset))
    if preset.section_sizes:
        lines.append(preset.section_sizes)
    return "\n".join(lines)


def _section_format(preset: LayoutPreset) -> str:
    accent = preset.accent
    kind = preset.section_title
    if kind == "smallcaps":
        return "\\titleformat{\\section}{\\vspace{-4pt}\\scshape\\raggedright\\large}{}{0em}{}[\\titlerule \\vspace{-5pt}]"
    if kind == "bold":
        return "\\titleformat{\\section}{\\vspace{-3pt}\\raggedright\\large\\bfseries}{}{0em}{}[\\titlerule \\vspace{-4pt}]"
    if kind == "upper-rule":
        # \MakeUppercase inside \titleformat breaks titlesec's internals, so the
        # heading text is uppercased at render time instead.
        return "\\titleformat{\\section}{\\vspace{-3pt}\\raggedright\\large\\bfseries}{}{0em}{}[\\titlerule \\vspace{-4pt}]"
    if kind == "bold-rule" and accent:
        return (f"\\titleformat{{\\section}}{{\\vspace{{-4pt}}\\color{{{accent}}}\\large\\bfseries}}"
                f"{{}}{{0em}}{{}}[\\color{{{accent}}}\\titlerule \\vspace{{-4pt}}]")
    return "\\titleformat{\\section}{\\vspace{-3pt}\\raggedright\\large\\bfseries}{}{0em}{}[\\titlerule \\vspace{-4pt}]"


def _contact_parts(pii) -> tuple[list[str], list[str]]:
    primary: list[str] = []
    links: list[str] = []
    if (pii.location or "").strip():
        primary.append(escape_text(pii.location.strip()))
    if (pii.email or "").strip():
        primary.append("\\href{mailto:" + escape_url(pii.email.strip()) + "}{"
                       + escape_text(pii.email.strip()) + "}")
    if (pii.phone or "").strip():
        primary.append(escape_text(pii.phone.strip()))
    if (pii.linkedin or "").strip():
        links.append("\\href{" + escape_url(normalize_url(pii.linkedin, "linkedin.com/in")) + "}{"
                     + escape_text(display_url(pii.linkedin)) + "}")
    if (pii.github or "").strip():
        links.append("\\href{" + escape_url(normalize_url(pii.github, "github.com")) + "}{"
                     + escape_text(display_url(pii.github)) + "}")
    if (pii.portfolio or "").strip():
        links.append("\\href{" + escape_url(normalize_url(pii.portfolio, "example.com")) + "}{"
                     + escape_text(display_url(pii.portfolio)) + "}")
    return primary, links


def build_header(preset: LayoutPreset, pii) -> str:
    """Build the contact header locally, using the preset's accent colour."""
    name = escape_text((pii.name or "").strip() or "Name")
    accent = preset.accent
    primary, links = _contact_parts(pii)

    if preset.header_style == "left":
        name_cmd = (f"{{\\color{{{accent}}}\\LARGE\\bfseries {name}}}" if accent
                    else f"{{\\LARGE\\bfseries {name}}}")
        parts = primary + links
        lines = ["\\begin{flushleft}", name_cmd + "\\\\[2pt]"]
        if parts:
            lines.append("\\small " + " $|$ ".join(parts))
        lines.append("\\end{flushleft}")
        return "\n".join(lines)

    if preset.header_style == "two-column":
        # Creative only: a tabular header is readable by humans but not by every parser.
        right = primary + links
        row_right = " $|$ ".join(right)
        return ("\\begin{tabular*}{\\textwidth}{l@{\\extracolsep{\\fill}}r}\n"
                f"\\textbf{{\\LARGE {name}}} & {row_right} \\\\\n"
                "\\end{tabular*}")

    # centered
    name_cmd = (f"{{\\color{{{accent}}}\\LARGE\\bfseries {name}}}" if accent
                else f"{{\\LARGE\\bfseries {name}}}")
    separator = " $|$ "
    lines: list[str] = []
    if primary:
        lines.append(separator.join(primary))
    if links:
        lines.append(separator.join(links))
    out = ["\\begin{center}", name_cmd + "\\\\[2pt]"]
    for index, line in enumerate(lines):
        out.append("\\small " + line + ("\\\\" if index < len(lines) - 1 else ""))
    out.append("\\end{center}")
    return "\n".join(out)


# Backwards-compatible alias.
_header = build_header


def _bullets(items: Iterable[str], preset: LayoutPreset) -> list[str]:
    items = [i for i in (items or []) if str(i).strip()]
    if not items:
        return []
    out = [f"\\begin{{itemize}}[{preset.bullet_options}]"]
    out.extend("\\item " + escape_text(str(i).strip()) for i in items)
    out.append("\\end{itemize}")
    out.append("")
    return out


def _entry(entry: dict[str, Any], preset: LayoutPreset) -> list[str]:
    role = str(entry.get("role") or "").strip()
    company = str(entry.get("company") or "").strip()
    location = str(entry.get("location") or "").strip()
    dates = str(entry.get("dates") or "").strip()
    bullets = entry.get("bullets") or []

    headline = ", ".join(p for p in (role, company) if p)
    out: list[str] = []
    if preset.entry_style == "bold-title":
        out.append("\\textbf{" + escape_text(role) + "}\\\\")
        meta = " $|$ ".join(p for p in (company, dates) if p)
        out.append("\\textit{" + escape_text(meta) + "}\\\\")
    elif preset.entry_style == "title-meta":
        out.append("\\textbf{" + escape_text(headline) + "}\\\\")
        meta = " $|$ ".join(p for p in (location, dates) if p)
        out.append("\\textit{" + escape_text(meta) + "}\\\\")
    elif preset.entry_style == "timeline":
        # Date rail next to the entry. Looks good to a human, costs ATS points.
        out.append("\\textbf{" + escape_text(headline) + "}\\\\")
        out.append("\\begin{tabular*}{0.97\\textwidth}{@{}l@{\\extracolsep{\\fill}}r@{}}")
        out.append("\\textit{" + escape_text(location) + "} & " + escape_text(dates) + " \\\\")
        out.append("\\end{tabular*}")
        out.append("")
    else:  # bold-hfill
        out.append("\\textbf{" + escape_text(headline) + "} \\hfill " + escape_text(dates) + "\\\\")
        if location:
            out.append("\\textit{" + escape_text(location) + "}\\\\")
    out.append("")
    out.extend(_bullets(bullets, preset))
    return out


def _section(preset: LayoutPreset, title: str) -> str:
    """Section heading, uppercased for presets that want it."""
    if preset.section_title == "upper-rule":
        return "\\section{\\MakeUppercase{" + title + "}}"
    return "\\section{" + title + "}"


def render_body(data: dict[str, Any], preset: LayoutPreset) -> str:
    """Render structured canvas data into a LaTeX resume body."""
    out: list[str] = []

    for section in preset.section_order:
        key = section.lower()
        if key == "professional summary":
            text = str(data.get("summary") or "").strip()
            if text:
                out.append(_section(preset, "Professional Summary"))
                out.append(escape_text(text))
                out.append("")
        elif key == "skills":
            groups = data.get("skills") or []
            if groups:
                out.append(_section(preset, "Skills"))
                for group in groups:
                    label = str(group.get("label") or "").strip()
                    items = ", ".join(str(i).strip() for i in (group.get("items") or []) if str(i).strip())
                    if not items:
                        continue
                    if label:
                        out.append("\\textbf{" + escape_text(label) + ":} " + escape_text(items) + "\\\\")
                    else:
                        out.append(escape_text(items) + "\\\\")
                out.append("")
        elif key == "professional experience":
            entries = data.get("experience") or []
            if entries:
                out.append(_section(preset, "Professional Experience"))
                for entry in entries:
                    out.extend(_entry(entry, preset))
        elif key == "projects":
            entries = data.get("projects") or []
            if entries:
                out.append(_section(preset, "Projects"))
                for entry in entries:
                    out.extend(_entry(entry, preset))
        elif key == "education":
            entries = data.get("education") or []
            if entries:
                out.append(_section(preset, "Education"))
                for entry in entries:
                    out.extend(_entry(entry, preset))
        elif key == "certifications":
            entries = data.get("certifications") or []
            if entries:
                out.append(_section(preset, "Certifications"))
                for entry in entries:
                    label = str(entry.get("role") or entry.get("label") or "").strip()
                    issuer = str(entry.get("company") or entry.get("issuer") or "").strip()
                    dates = str(entry.get("dates") or "").strip()
                    line = ", ".join(p for p in (label, issuer) if p)
                    out.append("\\textbf{" + escape_text(line) + "} \\hfill " + escape_text(dates) + "\\\\")
                out.append("")
        elif key == "achievements":
            items = data.get("achievements") or []
            if items:
                out.append(_section(preset, "Achievements"))
                out.extend(_bullets(items, preset))
        elif key == "languages":
            items = data.get("languages") or []
            if items:
                out.append(_section(preset, "Languages"))
                out.append(", ".join(str(i).strip() for i in items if str(i).strip()) + "\\\\")
                out.append("")

    return "\n".join(out).strip()


def render_document(data: dict[str, Any], preset: LayoutPreset, pii) -> str:
    """Full document: preamble + local header + rendered body."""
    header = _header(preset, pii)
    body = render_body(data, preset)
    return (build_preamble(preset) + "\n\\begin{document}\n" + header + "\n" + body
            + "\n\\end{document}\n")


def sample_data() -> dict[str, Any]:
    """A complete, placeholder-free sample used to score gallery templates."""
    return {
        "summary": ("Data analyst with 5+ years of experience turning product and operational "
                    "data into decisions. Skilled in SQL, Python and Power BI, with a track "
                    "record of cutting reporting time by 30% and improving forecast accuracy "
                    "by 18%."),
        "skills": [
            {"label": "Languages", "items": ["Python", "SQL", "R"]},
            {"label": "Frameworks", "items": ["Pandas", "scikit-learn", "Airflow"]},
            {"label": "Cloud and Data", "items": ["Power BI", "PostgreSQL", "Azure"]},
            {"label": "Practices", "items": ["Agile", "Code review", "Testing"]},
        ],
        "experience": [
            {"role": "Senior Data Analyst", "company": "Infosys", "location": "Bengaluru, India",
             "dates": "2022 - Present",
             "bullets": [
                 "Built a Power BI revenue dashboard used by 300+ stakeholders, cutting weekly reporting time by 30%.",
                 "Automated 12 monthly reports with Python and SQL, saving 40 analyst hours per month.",
                 "Partnered with product teams on 3 A/B tests that raised conversion by 12%.",
             ]},
            {"role": "Data Analyst", "company": "Persistent Systems", "location": "Pune, India",
             "dates": "2020 - 2022",
             "bullets": [
                 "Designed 25 PostgreSQL models that reduced data preparation time by 45%.",
                 "Delivered weekly KPI reviews to 5 engineering leads and 2 directors.",
             ]},
            {"role": "Data Analyst Intern", "company": "Impetus Technologies", "location": "Indore, India",
             "dates": "2019 - 2020",
             "bullets": [
                 "Cleaned 1M+ event records in Python, improving data quality by 35%.",
                 "Built 6 dashboard views used in the quarterly business review.",
             ]},
        ],
        "projects": [
            {"role": "Demand Forecast Pipeline", "company": "Open source", "location": "",
             "dates": "2023",
             "bullets": [
                 "Built an hourly forecasting pipeline that reduced stock-outs by 18%.",
             ]},
        ],
        "education": [
            {"role": "B.Tech Computer Science", "company": "RGPV University", "location": "Bhopal, India",
             "dates": "2016 - 2020", "bullets": ["CGPA 8.4/10.0"]},
        ],
        "certifications": [
            {"role": "Google Data Analytics Professional Certificate", "company": "Google",
             "dates": "2022"},
        ],
        "achievements": ["Winner, inter-college analytics hackathon (2023)"],
        "languages": ["English (Fluent)", "Hindi (Native)", "Urdu (Fluent)"],
    }


# ---------------------------------------------------------------- parsing
# Turns an AI-generated LaTeX body back into canvas data, so the user can
# edit what the model wrote and re-render it with a template.

def _strip_wrappers(text: str) -> str:
    """Remove the common LaTeX wrappers so plain text remains."""
    out = text
    for _ in range(6):
        previous = out
        out = re.sub(r"\\(textbf|textit|emph|underline|small)\{([^{}]*)\}", r"\2", out)
        if out == previous:
            break
    out = re.sub(r"\\MakeUppercase\{([^{}]*)\}", r"\1", out)
    # A literal backslash and LaTeX line breaks carry no content.
    out = out.replace(r"\textbackslash{}", "")
    out = re.sub(r"\\\\\s*", " ", out)
    out = re.sub(r"\\(hfill|textbar|par)\b", " ", out)
    out = re.sub(r"\\(textit|textbf|emph)\s*", "", out)
    out = out.replace(r"\%", "%").replace(r"\&", "&").replace(r"\#", "#")
    out = out.replace(r"\_", "_").replace(r"\$", "$")
    out = re.sub(r"[{}]", "", out)
    return re.sub(r"\s+", " ", out).strip()


def _split_sections(body: str) -> list[tuple[str, str]]:
    """(heading, content) pairs, brace-aware."""
    sections: list[tuple[str, str]] = []
    matches = list(re.finditer(r"\\section\{", body))
    for index, match in enumerate(matches):
        cursor = match.end()
        depth = 1
        while cursor < len(body) and depth:
            char = body[cursor]
            if char == "{" and body[cursor - 1] != "\\":
                depth += 1
            elif char == "}" and body[cursor - 1] != "\\":
                depth -= 1
            cursor += 1
        heading = _strip_wrappers(body[match.end():cursor - 1]).lower()
        start = cursor
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        sections.append((heading, body[start:end]))
    return sections


def _bullets_from(block: str) -> list[str]:
    bullets: list[str] = []
    for match in re.finditer(r"\\item\s+(.+?)(?=\n\s*\\item|\n\s*\\end\{itemize\}|\Z)", block, re.DOTALL):
        text = _strip_wrappers(match.group(1).strip())
        if text:
            bullets.append(text)
    return bullets


def _entries_from(block: str) -> list[dict[str, Any]]:
    """Entries of the shape \\textbf{Role, Company} \\hfill Dates + bullets."""
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    bullets: list[str] = []
    in_list = False

    def flush() -> None:
        nonlocal current, bullets
        if current is not None:
            current["bullets"] = bullets or current.get("bullets") or []
            entries.append(current)
            current = None
            bullets = []

    for raw_line in block.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("\\begin{itemize}"):
            in_list = True
            bullets = []
            continue
        if line.startswith("\\end{itemize}"):
            in_list = False
            flush()
            continue
        if in_list:
            if line.startswith("\\item"):
                text = _strip_wrappers(line[len("\\item"):].strip())
                if text:
                    bullets.append(text)
            continue
        if "\\hfill" in line:
            flush()
            left, _, right = line.partition("\\hfill")
            title = _strip_wrappers(left)
            dates = _strip_wrappers(right)
            role, _, company = title.partition(",")
            current = {
                "role": role.strip(),
                "company": company.strip(),
                "location": "",
                "dates": dates.strip(),
                "bullets": [],
            }
            continue
        if current is not None and line.startswith("\\textit") and not current["location"]:
            current["location"] = _strip_wrappers(line)
            continue
        if current is not None:
            text = _strip_wrappers(line)
            if text:
                current.setdefault("bullets", []).append(text)
    flush()
    return entries


def _skills_from(block: str) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    loose: list[str] = []
    for raw_line in block.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line or line.startswith("\\begin{itemize}") or line.startswith("\\end{itemize}"):
            continue
        match = re.match(r"\\textbf\{([^}]*)\}\s*:?\s*(.*)$", line)
        if match:
            label = _strip_wrappers(match.group(1)).rstrip(":").strip()
            items = [item.strip() for item in match.group(2).replace(r"\\", "").split(",") if item.strip()]
            if label or items:
                groups.append({"label": label, "items": items})
            continue
        text = _strip_wrappers(line)
        if text:
            loose.append(text)
    if loose:
        items = []
        for chunk in loose:
            items.extend(part.strip() for part in chunk.replace(r"\\", "").split(",") if part.strip())
        groups.append({"label": "", "items": items})
    return groups


def parse_latex_body(body: str) -> dict[str, Any]:
    """Parse an AI-generated LaTeX body into canvas data."""
    data: dict[str, Any] = {
        "summary": "", "skills": [], "experience": [], "projects": [],
        "education": [], "certifications": [], "achievements": [], "languages": [],
    }
    if not body or not body.strip():
        return data

    for heading, content in _split_sections(body):
        if heading in ("professional summary", "summary", "profile", "objective"):
            data["summary"] = _strip_wrappers(re.sub(r"\\small\{(.*)\}", r"\1", content, flags=re.DOTALL))
        elif heading == "skills":
            data["skills"] = _skills_from(content)
        elif heading in ("professional experience", "experience", "work experience"):
            data["experience"] = _entries_from(content)
        elif heading == "projects":
            data["projects"] = _entries_from(content)
        elif heading == "education":
            data["education"] = _entries_from(content)
        elif heading in ("certifications", "certificates"):
            data["certifications"] = _entries_from(content)
        elif heading in ("achievements", "awards"):
            data["achievements"] = _bullets_from(content) or [
                _strip_wrappers(line) for line in content.split("\n") if _strip_wrappers(line)]
        elif heading == "languages":
            text = _strip_wrappers(content).replace(r"\\", "")
            data["languages"] = [item.strip() for item in text.split(",") if item.strip()]
    return data
