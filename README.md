# ResumeTeX Web

A private, local-first resume builder. It is the web sibling of
[ResumeTeX](https://github.com/resumetex/resumetex) (the Windows desktop app) and
keeps the same promise: **your name, email, phone number, address and profile
links are never sent to an AI model.**

Read the [privacy write-up](docs/blog/never-send-pii-to-ai.md) — it explains the
architecture, and it tells you how to verify the claims yourself.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/maxico714/resumetex-web)

For the full from-scratch runbook — Blueprint flow, manual Docker setup,
verification commands, free-tier limits and troubleshooting — see
[DEPLOY_FROM_SCRATCH.md](DEPLOY_FROM_SCRATCH.md).

## What it does

- **Contact fields + one details box** → a complete, ATS-safe LaTeX resume.
- **Two ways to build:**
  - **AI (optional)** — any OpenAI-compatible provider: OpenRouter, OpenAI, Groq,
    Together AI, DeepSeek, Mistral, or a local Ollama / LM Studio server.
    **You bring your own key.** The key stays in your browser and is sent only to
    the provider host you pick.
  - **Canvas (no key)** — a structured editor with 15 scored templates. Works
    completely offline, with no account and no network.
- **Real PDF** — compiled with `pdflatex` on the app server (or your own
  MiKTeX / TeX Live when self-hosted), never sent to a third party.
- **ATS score** — a local analyser scores the result out of 100 and lists the
  exact issues to fix (structure, bullet quality, date format, length, keyword
  coverage against a pasted job description).
- **Template gallery** — 12 ATS-safe layouts and 3 creative ones, each with a
  *measured* ATS score and the reason behind it.
- **Network log** — every request the page made, so you can see what left.

## Install and run

```bash
git clone https://github.com/maxico714/resumetex-web
cd resumetex-web
pip install -e .
resumetex-web serve
```

Open <http://127.0.0.1:5000>. It binds to loopback by default and stores nothing.

For development:

```bash
pip install -e ".[dev]"
python -m flask --app "resumetex_web:create_app()" run --debug
python -m unittest discover -s tests -v
```

### Requirements

- Python 3.10+
- Flask (installed by `pip install -e .`)
- For local PDF only: MiKTeX or TeX Live (`pdflatex` on PATH, or the default
  MiKTeX install path). Without it you can still export `.tex` and compile
  elsewhere.
- For AI only: your own API key (optional; local model servers usually need none).

## Deploy on Render (Docker)

The repo ships a `Dockerfile` that installs the LaTeX engine itself, so the
build never touches Render's read-only apt lists. The build then compiles all
15 gallery templates to a real PDF; if any template fails, **the build fails**
instead of deploying a broken Compile PDF button.

| Setting | Value |
|---|---|
| Runtime | **Docker** (`Dockerfile` in the repo root) |
| Instance type | Free |
| Build command | *ignored* — comes from the Dockerfile |
| Start command | *ignored* — `gunicorn wsgi:app --bind 0.0.0.0:$PORT` |
| Health check | `/healthz` |
| Env: `RESUMETEX_ALLOW_COMPILE` | `1` (server may run pdflatex) |
| Env: `RESUMETEX_ALLOW_ONLINE_COMPILE` | `0` (no document ever uploaded) |
| Env: `RESUMETEX_HOST` | `0.0.0.0` |

**One-click Blueprint:**
<https://render.com/deploy?repo=https://github.com/maxico714/resumetex-web> —
`render.yaml` creates the Docker service with the settings above. The complete
click-by-click runbook is in [DEPLOY_FROM_SCRATCH.md](DEPLOY_FROM_SCRATCH.md).

The image installs `lmodern`, `texlive-latex-base`, `texlive-latex-recommended`,
`texlive-latex-extra` (this one provides `titlesec` and `enumitem`) and
`texlive-fonts-recommended`. It deliberately skips `texlive-fonts-extra`
(~2 GB): the two serif presets fall back from `newtx` to `mathptmx`.

After a deploy, check the engine in one request:

```bash
curl -s https://YOUR-SERVICE.onrender.com/api/health
```

A healthy instance reports:

```json
{"pdflatex": true, "latex": {"found": true, "missing": []}, "allowCompile": true}
```

The Output card also has **Test LaTeX setup**, which compiles a harmless test
document and shows the engine version, path and any missing package. Use
**Copy diagnostics** when reporting a problem.

### Compiler methods

The Output card lets the user pick how the PDF is produced:

| Method | Where the CV goes |
|---|---|
| **Server pdflatex** (default) | Compiled on your server. Nothing is uploaded. |
| **Automatic** | Server first; only if that fails, the full CV is uploaded to the third-party compiler. |
| **Online compiler** | The full CV (including name, phone, email) is uploaded. A confirmation dialog warns before every upload. |

`auto` and `online` only appear when `RESUMETEX_ALLOW_ONLINE_COMPILE=1`. The
default is `0`, so the private path is the only one available.

### If Compile PDF still fails on Render

1. Open the Render Dashboard → your service → **Settings → Build & Deploy → Source →
   Edit**. Set **Runtime → Docker** (Render does let you change an existing
   service's runtime), clear the build/start commands, and save. If the service
   is managed by the Blueprint, syncing `render.yaml` also applies the runtime.
2. Trigger **Manual Deploy → Deploy latest commit** and watch the build log for
   `OK: all 15 gallery templates compiled to PDF.` A red build means a TeX
   package is missing; the log names it.
3. Open `/api/health` — `"found": true` and `"missing": []` are required.
4. Open the app → Output → **Test LaTeX setup**. Copy the diagnostics if the
   probe fails.
5. Free instances sleep after ~15 minutes. The first compile after a wake-up
   can take a minute; the UI waits up to 150 seconds.

To run without the engine at all, set `RESUMETEX_ALLOW_COMPILE=0`: the server
then never sees a document (AI + canvas + `.tex` export only).

Manual (non-Docker) alternative, for a host where apt works. This does **not**
work on Render's native Python runtime, whose apt lists are read-only; use the
Dockerfile there:

```
build: apt-get update && apt-get install -y lmodern texlive-latex-base texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended && pip install -r requirements.txt
start: gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120
```

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `RESUMETEX_HOST` | `127.0.0.1` | Bind address. Change it only if you understand the exposure. |
| `RESUMETEX_PORT` | `5000` | Port |
| `RESUMETEX_ALLOW_COMPILE` | `1` | Server-side `pdflatex`. Set to `0` for an instance that never sees a document. |
| `RESUMETEX_ALLOW_ONLINE_COMPILE` | `0` | Third-party compile. Off by default: it uploads the document *including* contact details. |
| `RESUMETEX_ONLINE_URL` | `https://latex.ytotech.com/builds/sync` | Online compiler endpoint |
| `RESUMETEX_COMPILE_TIMEOUT` | `75` | Seconds per compile |
| `RESUMETEX_DEBUG` | `0` | Flask debug mode |

## Privacy model

| Data | Where it goes |
|---|---|
| Name, email, phone, location, LinkedIn, GitHub, portfolio | Held in the browser. Never part of an AI request. |
| Resume details text | Redacted locally (known values + any other email/phone-like string), then sent. |
| Leak gate | Before a request is built, the text is re-scanned. If a known value survived, generation is blocked. |
| API key | In the browser. Sent only to the provider host it was entered for. "Remember key" is off by default. |
| Generated LaTeX / PDF | In the browser; written to disk only when you download it. |
| Server state | **None.** No database, no resume files, no logs with content, no telemetry. |

The browser redactor and the server redactor are separate implementations of the
same rules, and `tests/test_core.py` asserts they produce identical output.

## Templates and ATS scoring

The gallery has 15 layouts. Each is rendered with a complete sample CV and scored
by the local analyser:

- **12 ATS-safe** (score 93) — single column, no tables, standard section names.
- **3 creative** (score 88) — a sidebar, a date rail or a boxed header. They read
  better to a human but measurably lower the ATS score, and the gallery says so.

Scoring rules (100 points): core sections 20, no forbidden constructs 15, bullet
quality 25, dates 10, length 10, skills grouping 10, optional sections 5, and
job-description keyword coverage 15 when a JD is supplied.

## Project layout

```
resumetex_web/
  core/        pure logic: pii, latex, prompt, offline, canvas, ats, gallery, compile
  api.py       the JSON API
  templates/   Jinja pages: builder, gallery, privacy write-up
  static/      CSS, the browser-side privacy layer, vendored pdf.js
tests/         unittest suite (no third-party dependencies)
docs/blog/     the privacy write-up
```

## License

MIT. See [LICENSE](LICENSE).
