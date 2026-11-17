"""Template gallery: layout presets with measured ATS scores.

The score of every gallery entry is computed by the local analyser on a complete
sample CV rendered with that preset, so the ranking is measured, not claimed.
"""

from __future__ import annotations

from .ats import analyze, grade_label
from .canvas import LayoutPreset, render_body, render_document, sample_data
from .pii import PiiFields

_SAMPLE_PII = PiiFields(
    name="John Doe",
    email="john.doe@example.com",
    phone="+1 555 010 0100",
    location="Redmond, WA",
    linkedin="linkedin.com/in/johndoe",
    github="github.com/johndoe",
)

_PRESETS: list[LayoutPreset] = [
    # ---------------------------------------------------------- ATS safe (12)
    LayoutPreset(
        id="ats-navy", name="Navy Formal", ats_class="ats",
        best_for=["Analyst", "Consultant", "Manager", "Operations"],
        summary="Navy section headings with a thin rule, centred contact line.",
        why="Single column, standard headings, no tables or icons: everything an ATS parser needs.",
        geometry="left=0.75in,top=0.6in,right=0.75in,bottom=0.6in",
        accent="navyblue", accent_rgb="0,54,123", section_title="bold-rule",
        header_style="centered", entry_style="bold-hfill",
        notes="Safest default for corporate and mid-senior roles.",
    ),
    LayoutPreset(
        id="ats-classic", name="Classic Serif", ats_class="ats",
        best_for=["Consultant", "Legal", "Finance", "Public sector"],
        summary="Traditional serif look with small-caps sections and a black rule.",
        why="Textbook layout: black text, one column, standard section names.",
        font_lines=["\\IfFileExists{newtxtext.sty}{\\usepackage{newtxtext}\\usepackage{newtxmath}}{\\usepackage{mathptmx}}"],
        geometry="left=0.8in,top=0.6in,right=0.8in,bottom=0.6in",
        accent=None, section_title="smallcaps", header_style="centered",
        entry_style="bold-hfill",
        notes="Timeless and conservative.",
    ),
    LayoutPreset(
        id="ats-minimal", name="Minimal ATS", ats_class="ats",
        best_for=["Any role", "Strict ATS filters"],
        summary="Fully linear, no rules under headings, maximum parseability.",
        why="Nothing to confuse a parser: one column, plain headings, no graphics.",
        geometry="left=0.7in,right=0.7in,top=0.55in,bottom=0.55in",
        accent="softgray", accent_rgb="107,114,128", section_title="bold",
        header_style="centered", entry_style="bold-hfill",
        notes="Use when a keyword filter rejected a fancier CV before.",
    ),
    LayoutPreset(
        id="ats-compact", name="Compact Fresh", ats_class="ats",
        best_for=["Students", "Freshers", "Interns"],
        summary="Dense 10pt layout that fits a lot of early-career content on one page.",
        why="More content per page without columns, tables or images.",
        class_options="10pt", geometry="margin=0.5in",
        accent=None, section_title="bold", header_style="centered",
        bullet_options="leftmargin=1.1em,itemsep=1pt,topsep=1.5pt,parsep=0pt,partopsep=0pt",
        notes="Education and projects stay visible, which is what freshers need.",
    ),
    LayoutPreset(
        id="ats-projects", name="Projects First", ats_class="ats",
        best_for=["Developers", "Data engineers", "ML engineers"],
        summary="Sans-serif developer layout with a large Projects section.",
        why="Linear structure with the projects the role cares about placed first.",
        font_lines=["\\usepackage{helvet}", "\\renewcommand{\\familydefault}{\\sfdefault}"],
        class_options="10pt", geometry="left=0.7in,right=0.7in,top=0.55in,bottom=0.55in",
        accent=None, section_title="bold", header_style="centered",
        section_order=["Professional Summary", "Skills", "Projects", "Professional Experience",
                       "Education", "Certifications", "Achievements", "Languages"],
        notes="Projects before Experience for technical screens.",
    ),
    LayoutPreset(
        id="ats-academic", name="Academic Serif", ats_class="ats",
        best_for=["Research", "PhD applicants", "Academia"],
        summary="Serif academic look with blue ruled sections and tight leading.",
        why="Formal and readable, still one column and standard headings.",
        font_lines=["\\IfFileExists{newtxtext.sty}{\\usepackage{newtxtext}\\usepackage{newtxmath}}{\\usepackage{mathptmx}}"],
        geometry="left=0.8in,right=0.8in,top=0.55in,bottom=0.55in",
        accent="linkcolour", accent_rgb="0,51,153", section_title="bold-rule",
        header_style="centered", entry_style="bold-hfill", line_spacing="1.05",
        notes="Good for publications and research statements.",
    ),
    LayoutPreset(
        id="ats-modern", name="Modern Left", ats_class="ats",
        best_for=["Product", "Tech", "Startups"],
        summary="Left-aligned name block, navy headings, roomier spacing.",
        why="Contemporary without breaking the single-column rule.",
        geometry="left=0.75in,top=0.65in,right=0.75in,bottom=0.65in",
        accent="navyblue", accent_rgb="0,54,123", section_title="bold-rule",
        header_style="left", entry_style="bold-hfill",
        notes="Feels modern but stays parser-friendly.",
    ),
    LayoutPreset(
        id="ats-exec", name="Executive Navy", ats_class="ats",
        best_for=["Heads of department", "Senior leadership"],
        summary="Airy margins with a strong navy heading and bold role lines.",
        why="Room to breathe; the extra whitespace costs no ATS points.",
        geometry="left=0.9in,top=0.75in,right=0.9in,bottom=0.75in",
        accent="navyblue", accent_rgb="0,54,123", section_title="bold-rule",
        header_style="centered", entry_style="bold-title",
        bullet_options="leftmargin=1.2em,itemsep=2pt,topsep=3pt,parsep=0pt,partopsep=0pt",
        notes="Use for director and above profiles.",
    ),
    LayoutPreset(
        id="ats-teal", name="Technical Teal", ats_class="ats",
        best_for=["Data analysts", "QA", "Test engineers"],
        summary="Deep teal accents on a clean white page.",
        why="Colour is the only decoration; the structure stays ATS-safe.",
        accent="tealaccent", accent_rgb="0,106,113", section_title="bold-rule",
        header_style="centered", entry_style="bold-hfill",
        notes="Subtle colour, zero structural risk.",
    ),
    LayoutPreset(
        id="ats-burgundy", name="Burgundy Formal", ats_class="ats",
        best_for=["Law", "Consulting", "Executive assistants"],
        summary="Burgundy headings with a black rule underneath.",
        why="A conservative alternative to navy that still parses cleanly.",
        accent="burgundy", accent_rgb="128,0,32", section_title="bold-rule",
        header_style="centered", entry_style="bold-hfill",
        notes="Prints well on monochrome copiers.",
    ),
    LayoutPreset(
        id="ats-slate", name="Slate Clean", ats_class="ats",
        best_for=["Operations", "Supply chain", "Admin"],
        summary="Grey headings, generous line spacing, no rules.",
        why="Extremely simple structure with nothing to trip a parser.",
        accent="slateaccent", accent_rgb="71,85,105", section_title="bold",
        header_style="centered", entry_style="bold-hfill", line_spacing="1.08",
        notes="Plain, calm and very safe.",
    ),
    LayoutPreset(
        id="ats-green", name="Forest Clean", ats_class="ats",
        best_for=["Healthcare", "Education", "NGO"],
        summary="Forest-green headings with standard section names.",
        why="One column, standard headings, no graphics.",
        accent="forest", accent_rgb="21,94,57", section_title="bold-rule",
        header_style="centered", entry_style="bold-hfill",
        notes="Calm colour for care-sector CVs.",
    ),
    # ---------------------------------------------------------- Starter packs (3)
    # The layouts from the bundled resumes.zip. Contact details are intentionally
    # absent from the default content: users fill them in locally in the canvas.
    LayoutPreset(
        id="starter-classic", name="Starter Classic", ats_class="ats", starter=True,
        best_for=["Software", "Engineering", "Any professional"],
        summary="The clean one-column classic: Times, uppercase headings and a thin rule.",
        why="Maximum ATS safety: no colour, no table, no side column, standard headings.",
        class_options="10pt,a4paper",
        geometry="margin=0.65in,top=0.5in,bottom=0.5in",
        font_lines=["\\usepackage{mathptmx}"],
        accent=None, section_title="upper-rule", header_style="centered",
        entry_style="bold-hfill",
        bullet_options="leftmargin=1.15em,itemsep=1.5pt,topsep=2pt,parsep=0pt,partopsep=0pt",
        notes="Comes with editable sample content in the canvas.",
    ),
    LayoutPreset(
        id="starter-navy", name="Starter Modern Navy", ats_class="ats", starter=True,
        best_for=["Software", "Product", "Data"],
        summary="Sans-serif name block with a deep navy rule and uppercase section headings.",
        why="Colour and spacing only, still single column and parser-friendly.",
        class_options="10pt,a4paper",
        geometry="margin=0.7in,top=0.5in,bottom=0.5in",
        font_lines=["\\usepackage[scaled=0.92]{helvet}",
                    "\\renewcommand{\\familydefault}{\\sfdefault}"],
        accent="starternavy", accent_rgb="31,58,95", section_title="upper-rule",
        header_style="left", entry_style="bold-hfill",
        bullet_options="leftmargin=1.1em,itemsep=1.5pt,topsep=2pt,parsep=0pt,partopsep=0pt",
        notes="Modern look without a sidebar or table.",
    ),
    LayoutPreset(
        id="starter-executive", name="Starter Executive", ats_class="ats", starter=True,
        best_for=["Senior roles", "Leadership", "Consulting"],
        summary="Palatino serif, burgundy small-caps headings and a double-rule header.",
        why="Formal and calm; the two rules are decorative but the text stays linear.",
        class_options="10pt,a4paper",
        geometry="margin=0.62in,top=0.45in,bottom=0.45in",
        font_lines=["\\usepackage{mathpazo}"],
        accent="starterburgundy", accent_rgb="122,31,43",
        section_title="smallcaps", header_style="executive",
        entry_style="company-first", line_spacing="1.0",
        bullet_options="leftmargin=1.2em,itemsep=1pt,topsep=1.5pt,parsep=0pt,partopsep=0pt",
        notes="Summary-first layout for experienced candidates.",
    ),
    # ---------------------------------------------------------- Creative (3)
    LayoutPreset(
        id="cr-sidebar", name="Sidebar Skills", ats_class="creative",
        best_for=["Design-heavy roles", "Portfolio CVs"],
        summary="Skills in a side column, main column with the story.",
        why="A side column splits the text stream, so parsers can reorder it. Fine for humans, risky for filters.",
        geometry="left=0.6in,top=0.55in,right=0.6in,bottom=0.55in",
        accent="navyblue", accent_rgb="0,54,123", section_title="bold-rule",
        header_style="two-column", entry_style="bold-hfill",
        notes="Send only when a human reads it first.",
    ),
    LayoutPreset(
        id="cr-timeline", name="Timeline Rails", ats_class="creative",
        best_for=["Long careers", "Design studies"],
        summary="Date rail beside each role with vertical rules.",
        why="The date rail is a table, and tables are the number one cause of scrambled ATS reads.",
        geometry="left=0.7in,top=0.6in,right=0.7in,bottom=0.6in",
        accent="slateaccent", accent_rgb="71,85,105", section_title="bold-rule",
        header_style="centered", entry_style="timeline",
        notes="Visually strong, measurably lower ATS score.",
    ),
    LayoutPreset(
        id="cr-capsule", name="Capsule Header", ats_class="creative",
        best_for=["Portfolio roles", "Agency CVs"],
        summary="A boxed contact header with uppercase role lines.",
        why="Uppercase and boxes survive most parsers but reduce keyword readability.",
        geometry="left=0.8in,top=0.7in,right=0.8in,bottom=0.7in",
        accent="burgundy", accent_rgb="128,0,32", section_title="upper-rule",
        header_style="two-column", entry_style="title-meta",
        notes="Use with a human reviewer in the loop.",
    ),
]

GALLERY: dict[str, LayoutPreset] = {p.id: p for p in _PRESETS}


def _score_preset(preset: LayoutPreset) -> dict:
    # Score the complete document (preamble + header + body), because ATS risk
    # lives in the layout too — a tabular header or a column breaks parsing.
    # Every preset is scored with the same sample content so the number reflects
    # the layout, not the length of a particular starter pack.
    document = render_document(sample_data(), preset, _SAMPLE_PII)
    report = analyze(document)
    return {
        **preset.as_dict(),
        "atsScore": report.score,
        "atsGrade": report.grade,
        "atsLabel": grade_label(report.grade),
        "atsIssues": [i.as_dict() for i in report.issues if i.severity in ("critical", "warning")][:4],
        "stats": report.stats,
    }


_GALLERY_CACHE: list[dict] | None = None


def gallery() -> list[dict]:
    """The gallery, scored once at import time."""
    global _GALLERY_CACHE
    if _GALLERY_CACHE is None:
        _GALLERY_CACHE = sorted(
            (_score_preset(p) for p in _PRESETS),
            key=lambda entry: (-entry["atsScore"], entry["name"]),
        )
    return _GALLERY_CACHE


def ats_safe() -> list[dict]:
    return [g for g in gallery() if g["atsClass"] == "ats"]


def creative() -> list[dict]:
    return [g for g in gallery() if g["atsClass"] == "creative"]


def preset(preset_id: str) -> LayoutPreset | None:
    return GALLERY.get(preset_id)
