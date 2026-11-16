"""Core logic of the ResumeTeX web app (pure Python, no Flask imports)."""

from .ats import AtsReport, analyze, grade_label
from .canvas import (LayoutPreset, parse_latex_body, render_body, render_document, sample_data)
from .completeness import CompletenessReport, analyze as analyze_completeness
from .completeness import find_placeholders, missing_core_sections
from .compile import (CompileError, CompileResult, compile_local, compile_online,
                      is_available, latex_status, missing_packages)
from .gallery import GALLERY, ats_safe, creative, gallery, preset
from .latex import (STYLE_DESCRIPTIONS, STYLE_LABELS, body_to_plain_text, build_header,
                    compose, escape_text, escape_url, get_shell, normalize_url,
                    resolve_style, sanitize_ai_output, LaTeXRejected)
from .offline import generate_body
from .pii import PiiFields, PiiLeakError, PiiRedactor, RedactionResult, contains_non_latin
from .prompt import (ResumeOptions, build_system_prompt, build_user_content,
                     is_compatible_custom_prompt, DEFAULT_PROMPT_TEMPLATE)

__all__ = [
    "AtsReport", "analyze", "grade_label", "LayoutPreset", "render_body", "render_document",
    "sample_data", "parse_latex_body", "CompletenessReport", "analyze_completeness", "find_placeholders",
    "missing_core_sections", "CompileError", "CompileResult", "compile_local",
    "compile_online", "is_available", "latex_status", "missing_packages", "GALLERY", "ats_safe", "creative", "gallery", "preset",
    "STYLE_DESCRIPTIONS", "STYLE_LABELS", "body_to_plain_text", "build_header", "compose",
    "escape_text", "escape_url", "get_shell", "normalize_url", "resolve_style",
    "sanitize_ai_output", "LaTeXRejected", "generate_body", "PiiFields", "PiiLeakError",
    "PiiRedactor", "RedactionResult", "contains_non_latin", "ResumeOptions",
    "build_system_prompt", "build_user_content", "is_compatible_custom_prompt",
    "DEFAULT_PROMPT_TEMPLATE",
]
