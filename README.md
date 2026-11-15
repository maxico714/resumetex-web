# ResumeTeX Web

A private, local-first resume builder. It is the web sibling of
[ResumeTeX](https://github.com/resumetex/resumetex) (the Windows desktop app) and
keeps the same promise: **your name, email, phone number, address and profile
links are never sent to an AI model.**

Read the [privacy write-up](docs/blog/never-send-pii-to-ai.md) — it explains the
architecture, and it tells you how to verify the claims yourself.

## What it does

- **Contact fields + one details box** → a complete, ATS-safe LaTeX resume.
- **Two ways to build:**
  - **AI (optional)** — any OpenAI-compatible provider: OpenRouter, OpenAI, Groq,
    Together AI, DeepSeek, Mistral, or a local Ollama / LM Studio server.
    **You bring your own key.** The key stays in your browser and is sent only to
    the provider host you pick.
  - **Canvas (no key)** — a structured editor with 15 scored templates. Works
    completely offline, with no account and no network.
- **Real PDF** — compiled with your local MiKTeX / TeX Live (`pdflatex`). The
  document never leaves your machine.
- **ATS score** — a local analyser scores the result out of 100 and lists the
  exact issues to fix (structure, bullet quality, date format, length, keyword
  coverage against a pasted job description).
- **Template gallery** — 12 ATS-safe layouts and 3 creative ones, each with a
  *measured* ATS score and the reason behind it.
- **Network log** — every request the page made, so you can see what left.

## Install and run

```bash
git clone https://github.com/resumetex/resumetex-web
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

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `RESUMETEX_HOST` | `127.0.0.1` | Bind address. Change it only if you understand the exposure. |
| `RESUMETEX_PORT` | `5000` | Port |
| `RESUMETEX_ALLOW_COMPILE` | `1` | Server-side `pdflatex`. Set to `0` for an instance that never sees a document. |
| `RESUMETEX_ALLOW_ONLINE_COMPILE` | `0` | Third-party compile. Off by default: it uploads the document *including* contact details. |
| `RESUMETEX_ONLINE_COMPILE_URL` | `https://latex.ytotech.com/builds/sync` | Online compiler endpoint |
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
