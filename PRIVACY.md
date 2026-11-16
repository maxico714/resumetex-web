# Privacy notes — ResumeTeX Web

ResumeTeX handles personal data by design: contact details are the point of a
resume. This document states exactly what happens to each kind of data.

The full write-up for readers is in
[`docs/blog/never-send-pii-to-ai.md`](docs/blog/never-send-pii-to-ai.md).

## 1. Contact fields (PII)

Name, email, phone, location, LinkedIn, GitHub and portfolio are typed into the
page and held in the browser tab.

- They are escaped and inserted into the LaTeX header **locally**, in the browser,
  by the code in `static/js/latex.js`.
- They are **not** part of any AI request. The system prompt contains no contact
  block, and the user message contains only the details text after redaction.
- They are **not** sent to the online compiler unless the user explicitly picks
  `online` (or `auto` after a local failure) and the operator enabled it. In the
  default `local` mode the document travels from the browser to the app server
  that runs `pdflatex`, and to no third party.
- They are not written to the settings file, to any log, to telemetry, or to the
  registry — there is none.
- They are written to disk only when the user downloads the `.tex` or the `.pdf`,
  because that is what a resume is.

## 2. Resume details text

The free-text box is expected to contain no PII. The app does not trust that.

Before an AI request (`static/js/redact.js`, mirrored in `core/pii.py`):

1. Every filled contact value is replaced with a neutral phrase
   (`the candidate`, `the candidate's email`, `the candidate's phone number`,
   `the candidate's location`, `the candidate's LinkedIn profile`, and so on).
2. Name parts, link handles and phone digits are also matched.
3. Any remaining email address is replaced.
4. Any remaining phone-like number (8–15 digits, not a year range or decimal) is
   replaced.
5. A **gate** re-scans the result. If any known value still appears, generation
   is blocked and no request is made.

The UI reports how many values were redacted, offers **Show AI payload**, and
keeps a **network log** of every request the page made.

## 3. AI request

The request goes to the base URL you configured, using the standard OpenAI
chat-completions shape. Only:

- the system prompt (built-in, or your custom prompt with known contact values
  redacted),
- the redacted details text,
- the API key in the `Authorization` header, only when the host matches the one
  the key was entered for,

leave the browser. The response is treated as untrusted: it is reduced to a
LaTeX body, must start at `\section`, and any invented contact/header block is
discarded.

## 4. API key

The key lives in the browser.

- It is only sent to that exact host.
- Switching providers does not send an old key to a new provider — the key field
  is cleared by the operator.
- Local endpoints (Ollama / LM Studio) never receive an `Authorization` header.
- Remote providers must use HTTPS.
- "Remember key on this device" is **off** by default. When off, the key is not
  written to `localStorage` at all and disappears when the tab closes.

## 5. PDF

- **Local (default):** `pdflatex` runs as a child process in a per-compile temp
  folder that is deleted in a `finally` block. The document never leaves the server.
- **Automatic (opt-in):** local first. The third-party compiler is contacted only
  if the local compile fails, and only when online compiling is enabled.
- **Online (opt-in):** a third-party compiler receives the complete `.tex` —
  including the contact header. It is **off by default**, and enabling it shows a
  warning. Set `RESUMETEX_ALLOW_ONLINE_COMPILE=1` to allow it.
- **Disabled:** `RESUMETEX_ALLOW_COMPILE=0` (or `resumetex-web --no-compile`)
  makes the server refuse to compile anything, so it never sees a document.

## 6. Server state

There is none.

- No database, no resume files, no upload directory, no telemetry, no analytics.
- The API is stateless. `POST /api/redact` reads a string and returns a string.
- Responses are sent with `Cache-Control: no-store`.

## What is never collected

- No telemetry, analytics, crash reporting, or usage metrics.
- No accounts.
- No background service, tray icon, updater, or scheduled task.
- No resume or contact data in any file the server writes.

## AI output safety

The model's response is untrusted. Before it becomes a document the app:

- reduces it to a section body (strips preamble, comments and every `center`
  block),
- rejects file, macro and shell commands (`\input`, `\include`,
  `\includegraphics`, `\write`, `\def`, `\newcommand`, `\catcode`, `\special`,
  `\directlua`, and similar),
- re-checks the body with the PII gate before it reaches the document.

`pdflatex` runs with `-no-shell-escape`.

## Residual risks

- If the user pastes PII into the details box in a form the redactor does not
  recognise, it may reach the AI. The redactor covers the contact fields,
  generic emails and phone-like numbers, but names without a matching contact
  field are not detectable in general.
- Online compiling is a third-party service; its handling of uploaded data is
  outside this app's control.
- MiKTeX may contact package repositories if a required LaTeX package is missing
  during compilation. The templates use only standard packages.
- A key saved in a browser is only as safe as the browser and the device.
  Malware running as the same user can still read it.
- If you expose the server beyond loopback, whoever can reach it can use it to
  compile documents. Run it locally, or put authentication in front of it.

## Verification

- `tests/test_core.py` includes a parity test that runs the browser redactor and
  the server redactor over the same corpus and asserts byte-identical output,
  plus tests for the leak gate, the LaTeX escaper, the output sanitiser, the ATS
  analyser and the gallery scores.
- The app itself shows the exact AI payload and a network log, so the claims can
  be checked from the browser without reading any code.
