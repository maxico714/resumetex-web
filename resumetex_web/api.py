"""HTTP API.

Everything here is stateless: no resume text, no contact details and no API key
is written to disk. The browser holds the personal data and the provider key.
"""

from __future__ import annotations

import base64
import json
import queue
import threading
import time

from flask import (Blueprint, Response, current_app, jsonify, request, send_file,
                   stream_with_context)

from .core import (LaTeXRejected, PiiFields, PiiLeakError, PiiRedactor, ResumeOptions,
                   analyze, build_system_prompt, build_user_content, compose, compile_local,
                   compile_online, find_placeholders, gallery, generate_body, is_available,
                   missing_core_sections, preset, render_body, sample_data, starter_data,
                   sanitize_ai_output, is_compatible_custom_prompt)
from .core.compile import CompileError

api = Blueprint("api", __name__, url_prefix="/api")


def _payload() -> dict:
    return request.get_json(silent=True) or {}


def _pii_from(payload: dict) -> PiiFields:
    fields = payload.get("pii") or {}
    return PiiFields(
        name=str(fields.get("name") or ""),
        email=str(fields.get("email") or ""),
        phone=str(fields.get("phone") or ""),
        location=str(fields.get("location") or ""),
        linkedin=str(fields.get("linkedin") or ""),
        github=str(fields.get("github") or ""),
        portfolio=str(fields.get("portfolio") or ""),
    )


def _options_from(payload: dict) -> ResumeOptions:
    options = payload.get("options") or {}
    return ResumeOptions(
        page_target=int(options.get("pageTarget") or 1),
        tone=str(options.get("tone") or "Professional"),
        emphasis=str(options.get("emphasis") or "Balanced"),
        include_projects=bool(options.get("includeProjects", True)),
        include_certifications=bool(options.get("includeCertifications", True)),
        include_achievements=bool(options.get("includeAchievements", True)),
        include_languages=bool(options.get("includeLanguages", True)),
        custom_instructions=str(options.get("customInstructions") or ""),
    )


@api.get("/health")
def health():
    from .core.compile import latex_status
    latex = latex_status()
    return jsonify({
        "ok": True,
        "app": "ResumeTeX Web",
        "pdflatex": is_available(),
        "latex": latex,
        "allowCompile": current_app.config["ALLOW_COMPILE"],
        "allowOnlineCompile": current_app.config["ALLOW_ONLINE_COMPILE"],
    })


@api.get("/templates")
def templates():
    entries = gallery()
    return jsonify({
        "house": entries,
        "atsSafe": [g for g in entries if g["atsClass"] == "ats"],
        "creative": [g for g in entries if g["atsClass"] == "creative"],
        "starters": [g for g in entries if g.get("starter")],
        "starterData": starter_data() if any(g.get("starter") for g in entries) else {},
    })


@api.get("/sample")
def sample():
    return jsonify(sample_data())


@api.get("/prompt/default")
def prompt_default():
    """The default system prompt template (no personal data involved)."""
    from .core import DEFAULT_PROMPT_TEMPLATE
    from .core.prompt import APP_CONTRACT
    return jsonify({"template": DEFAULT_PROMPT_TEMPLATE, "contract": APP_CONTRACT})


@api.get("/shell/<style>")
def shell(style: str):
    """The LaTeX shell for a house style (the browser fills header and body)."""
    from .core import get_shell
    return jsonify({"style": style, "shell": get_shell(style)})


@api.post("/redact")
def redact():
    """Redact personal values from free text. The server never stores the input."""
    payload = _payload()
    details = str(payload.get("details") or "")
    pii = _pii_from(payload)
    try:
        result = PiiRedactor(pii).redact(details)
    except PiiLeakError as exc:
        return jsonify({"error": str(exc), "code": "pii_leak"}), 400
    return jsonify({
        "text": result.text,
        "replacementCount": result.replacement_count,
        "details": result.details,
    })


@api.post("/ats/score")
def ats_score():
    """Score a resume body locally (no personal data involved)."""
    payload = _payload()
    body = str(payload.get("body") or "")
    jd = str(payload.get("jobDescription") or "")
    report = analyze(body, jd or None)
    data = report.as_dict()
    data["missingSections"] = missing_core_sections(body)
    data["placeholders"] = find_placeholders(body)
    return jsonify(data)


@api.post("/generate/offline")
def generate_offline():
    """Deterministic, fully local body generation (no AI)."""
    payload = _payload()
    details = str(payload.get("details") or "")
    style = str(payload.get("style") or "auto")
    try:
        body = generate_body(details)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"body": body, "style": style})


@api.post("/parse-body")
def parse_body():
    """Parse an AI-generated LaTeX body into canvas data so it can be edited."""
    payload = _payload()
    body = str(payload.get("body") or "")
    from .core import parse_latex_body
    return jsonify({"data": parse_latex_body(body)})


@api.post("/header")
def header_only():
    """The contact header block alone (the browser composes the document)."""
    payload = _payload()
    style = str(payload.get("style") or "navy")
    pii = _pii_from(payload)
    accent = payload.get("accent") or None
    header_style = str(payload.get("headerStyle") or "") or None

    if accent or header_style:
        from .core.canvas import LayoutPreset
        from .core.canvas import build_header as build_preset_header
        layout = LayoutPreset(
            id="custom", name="Custom", accent=accent, header_style=header_style or "centered")
        return jsonify({"header": build_preset_header(layout, pii)})

    from .core import build_header
    return jsonify({"header": build_header(style, pii)})


@api.post("/compose")
def compose_document():
    """Join shell + local PII header + body into a complete document."""
    payload = _payload()
    style = str(payload.get("style") or "navy")
    body = str(payload.get("body") or "")
    pii = _pii_from(payload)
    try:
        tex = compose(style, pii, body)
    except (ValueError, LaTeXRejected) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"tex": tex})


@api.post("/canvas/render")
def canvas_render():
    """Render structured canvas data with a gallery preset."""
    payload = _payload()
    data = payload.get("data") or {}
    layout = preset(str(payload.get("presetId") or "ats-navy"))
    if layout is None:
        return jsonify({"error": "Unknown template."}), 400
    body = render_body(data, layout)
    report = analyze(body, str(payload.get("jobDescription") or "") or None)
    from .core.canvas import build_preamble
    return jsonify({"body": body, "preamble": build_preamble(layout),
                    "accent": layout.accent, "headerStyle": layout.header_style,
                    "entryStyle": layout.entry_style, "ats": report.as_dict()})


@api.post("/sanitize")
def sanitize():
    """Reduce untrusted model output to a safe LaTeX body."""
    payload = _payload()
    try:
        body = sanitize_ai_output(str(payload.get("raw") or ""))
    except LaTeXRejected as exc:
        return jsonify({"error": str(exc), "code": "rejected"}), 400
    return jsonify({"body": body})


@api.post("/prompt")
def prompt():
    """Build the system prompt and the redacted user content (server-side helper)."""
    payload = _payload()
    style = str(payload.get("style") or "navy")
    options = _options_from(payload)
    custom = str(payload.get("systemPrompt") or "")
    if custom and not is_compatible_custom_prompt(custom):
        return jsonify({
            "error": "A custom prompt must ask for the resume body only. "
                     "The app owns the preamble and the contact header.",
            "code": "incompatible_prompt",
        }), 400
    pii = _pii_from(payload)
    redactor = PiiRedactor(pii)
    details = redactor.redact(str(payload.get("details") or ""))
    prompt_text = custom
    total = details.replacement_count
    if custom:
        prompt_redaction = redactor.redact(custom)
        prompt_text = prompt_redaction.text
        total += prompt_redaction.replacement_count
    return jsonify({
        "systemPrompt": build_system_prompt(style, options, prompt_text or None),
        "userContent": build_user_content(details.text),
        "redactionCount": total,
        "redactionDetails": details.details,
    })


def _compile_mode(payload: dict) -> str:
    mode = str(payload.get("mode") or "local").lower()
    return mode if mode in ("local", "auto", "online") else "local"


def _compile_guard(mode: str, config):
    """The same privacy gates for the buffered and streaming endpoints."""
    if mode in ("local", "auto") and not config["ALLOW_COMPILE"]:
        return jsonify({
            "error": "Server-side compiling is disabled on this instance. "
                     "Download the .tex file and compile it locally, or choose "
                     "the online compiler if it is enabled.",
            "code": "compile_disabled",
        }), 403
    if mode == "online" and not config["ALLOW_ONLINE_COMPILE"]:
        return jsonify({
            "error": "Online compiling is disabled on this server. It uploads "
                     "the document, including your contact details, to a "
                     "third-party service. Set RESUMETEX_ALLOW_ONLINE_COMPILE=1 "
                     "to enable it.",
            "code": "online_disabled",
        }), 403
    return None


def _run_compile(tex: str, mode: str, config, on_stage=None):
    """Run one compile and report real stage transitions to the caller."""
    def notify(stage: str, progress: int, message: str) -> None:
        if on_stage:
            on_stage(stage, progress, message)

    used_online = False
    if mode == "online":
        notify("online", 30, "Uploading the document to the online compiler.")
        result = compile_online(tex, config["ONLINE_COMPILE_URL"],
                                config["COMPILE_TIMEOUT"])
        used_online = True
    elif mode == "auto":
        notify("local", 28, "Trying the private server compiler first.")
        try:
            result = compile_local(tex, config["COMPILE_TIMEOUT"])
        except CompileError as local_error:
            if not config["ALLOW_ONLINE_COMPILE"]:
                raise CompileError(
                    str(local_error) + " The online fallback is disabled on "
                    "this server (RESUMETEX_ALLOW_ONLINE_COMPILE=0)."
                )
            notify("online", 55, "Local compile failed. Uploading to the online compiler as a fallback.")
            result = compile_online(tex, config["ONLINE_COMPILE_URL"],
                                    config["COMPILE_TIMEOUT"])
            result.engine += f" (local failed: {local_error})"
            used_online = True
    else:
        notify("local", 28, "Running pdflatex on this server. Nothing is uploaded.")
        result = compile_local(tex, config["COMPILE_TIMEOUT"])
    notify("preview", 90, "PDF generated. Preparing the preview.")
    return result, used_online


@api.post("/compile")
def compile_tex():
    """Compile LaTeX to PDF.

    mode=local   server pdflatex (private, default)
    mode=auto    try local first, then the online service if it is enabled
    mode=online  third-party service (uploads the full document)
    """
    config = current_app.config
    payload = _payload()
    tex = str(payload.get("tex") or "")
    mode = _compile_mode(payload)

    guard = _compile_guard(mode, config)
    if guard:
        return guard

    try:
        result, used_online = _run_compile(tex, mode, config)
    except CompileError as exc:
        return jsonify({"error": str(exc), "code": "compile_error"}), 400
    response = send_file(
        __import__("io").BytesIO(result.pdf),
        mimetype="application/pdf",
        as_attachment=False,
        download_name="resume.pdf",
    )
    response.headers["X-ResumeTeX-Engine"] = result.engine
    response.headers["X-ResumeTeX-Pages"] = str(result.pages)
    response.headers["X-ResumeTeX-Online"] = "1" if used_online else "0"
    return response


@api.post("/compile/stream")
def compile_stream():
    """Compile and stream progress as newline-delimited JSON.

    The browser gets a real event when the request is accepted, when pdflatex
    starts, when the PDF is ready, and heartbeats with elapsed time while a
    slow (or cold) instance is still working. The final event carries the PDF
    as base64 so no temporary file or public URL is needed.
    """
    config = current_app.config
    payload = _payload()
    tex = str(payload.get("tex") or "")
    mode = _compile_mode(payload)

    guard = _compile_guard(mode, config)
    if guard:
        return guard

    def ndjson(event: dict) -> str:
        return json.dumps(event, separators=(",", ":")) + "\n"

    def generate():
        started = time.monotonic()
        logger = current_app.logger
        yield ndjson({
            "type": "start", "mode": mode, "progress": 5, "elapsed": 0.0,
            "message": "Request received. Preparing the document.",
        })

        events: queue.Queue = queue.Queue()

        def notify(stage: str, progress: int, message: str) -> None:
            events.put({
                "type": "stage", "stage": stage, "progress": progress,
                "message": message,
                "elapsed": round(time.monotonic() - started, 1),
            })

        def worker() -> None:
            try:
                result, used_online = _run_compile(tex, mode, config, notify)
                events.put({
                    "type": "done", "progress": 100,
                    "message": "PDF ready.",
                    "engine": result.engine, "pages": result.pages,
                    "online": used_online, "bytes": len(result.pdf),
                    "pdf": base64.b64encode(result.pdf).decode("ascii"),
                    "elapsed": round(time.monotonic() - started, 1),
                })
            except CompileError as exc:
                events.put({
                    "type": "error", "code": "compile_error",
                    "progress": 100, "message": str(exc),
                    "elapsed": round(time.monotonic() - started, 1),
                })
            except Exception:  # noqa: BLE001 - never leave the browser hanging
                logger.exception("Unexpected error while streaming a compile")
                events.put({
                    "type": "error", "code": "compile_error", "progress": 100,
                    "message": "The server could not finish the compile.",
                    "elapsed": round(time.monotonic() - started, 1),
                })

        thread = threading.Thread(target=worker, name="resumetex-compile", daemon=True)
        thread.start()

        finished = False
        while True:
            try:
                event = events.get(timeout=1.5)
            except queue.Empty:
                if not thread.is_alive():
                    break
                elapsed = time.monotonic() - started
                progress = min(85, 35 + int(elapsed * 2))
                if mode == "online":
                    message = "Waiting for the online compiler to return the PDF."
                elif elapsed < 8:
                    message = "pdflatex is rendering the document."
                elif elapsed < 25:
                    message = "Still compiling. This can take a little longer on a free instance."
                else:
                    message = "Still compiling. A sleeping free instance can take up to a minute to wake."
                yield ndjson({
                    "type": "heartbeat", "progress": progress,
                    "message": message, "elapsed": round(elapsed, 1),
                })
                continue

            finished = True
            yield ndjson(event)
            if event["type"] in ("done", "error"):
                break

        if not finished:
            yield ndjson({
                "type": "error", "code": "compile_error", "progress": 100,
                "message": "The compiler stopped without returning a result.",
                "elapsed": round(time.monotonic() - started, 1),
            })

    response = Response(stream_with_context(generate()),
                        mimetype="application/x-ndjson")
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Accel-Buffering"] = "no"
    return response


@api.post("/compile/diagnose")
def compile_diagnose():
    """Check the server LaTeX environment without any personal data."""
    config = current_app.config
    from .core.compile import latex_status, pdflatex_version, probe_local

    status = latex_status()
    data = {
        "allowCompile": config["ALLOW_COMPILE"],
        "allowOnlineCompile": config["ALLOW_ONLINE_COMPILE"],
        "onlineUrl": config["ONLINE_COMPILE_URL"] if config["ALLOW_ONLINE_COMPILE"] else "",
        "pdflatex": status,
        "version": pdflatex_version(),
        "probe": None,
    }
    if status["found"]:
        data["probe"] = probe_local(timeout=45)
    return jsonify(data)
