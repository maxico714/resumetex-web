# We never send your name, email, or phone number to an AI model

**How ResumeTeX builds ATS-ready LaTeX resumes with AI — while your personally
identifiable information stays on your own machine.**

> If you want a CV written for you, the hard part is never the writing. It is
> that you do not want to hand your name, address, phone number and email
> address to a model that keeps a log of every request. So most tools make you
> choose: send everything and get a better first draft, or protect your data and
> write every line yourself.
>
> ResumeTeX does not make you choose. The personal details never travel to the AI
> provider. They never travel to the model. They are not in the system prompt,
> and they are not in your message. What the provider receives is the part of
> your CV that is not about identifying you.

## The problem this solves

A blank form does not help you judge a CV. You cannot tell whether a template
suits you until you see it filled with content that looks like a real person.
The usual workaround — paste your whole resume into a chat box — sends exactly
the data you wanted to keep private.

So we split the CV in two:

| Data | Where it is processed | Does it leave your device? |
|---|---|---|
| Name, email, phone, location, LinkedIn, GitHub, portfolio | In your browser, in memory | **No** |
| Resume text (skills, roles, education, projects) | Redacted locally, then sent | Yes — without the personal values |
| Your API key | In your browser | Only to the provider host you chose |
| The finished PDF | Compiled by pdflatex on your machine | No |

## How it works, step by step

1. **You type your contact details.** They live in the page. They are never
   uploaded, never logged, and never stored on the server.
2. **You write or paste your resume text.** Skills, roles, education — the
   content that makes a CV worth reading.
3. **Local redaction.** Every contact value you typed is replaced with neutral
   phrases (*the candidate*, *the candidate's email*, …). Any stray email
   address or phone-like number is caught too, even if you never typed it into a
   field.
4. **A leak gate.** The redacted text is scanned again. If a single known
   personal value survived, the request is blocked and nothing is sent.
5. **The request goes out.** Only the redacted text, plus a system prompt that
   contains no personal data at all.
6. **The model answers.** Its reply is treated as untrusted input: reduced to a
   resume body, stripped of any invented contact block, and checked for blocked
   LaTeX commands.
7. **The header is written locally.** Your name and contact details are inserted
   into the LaTeX in your browser, from the values that never left it.
8. **Local compile.** `pdflatex` on your machine turns the document into a PDF.

## What the provider actually receives

This is the whole user message for a real request. There is no name, no email,
no phone, no city, no profile link:

```text
[DETAILS]
the candidate is an AI trainer and linguist with 4 years of experience.
the candidate's email
the candidate's phone number
the candidate's location
Skills: Python, SQL, JavaScript, prompt engineering
Experience: AI Trainer & Linguist | Freelance | 2022 - Present
- Annotated 40,000+ samples across Hindi, English and Urdu.
```

You can read the exact request before it is sent: the builder has a **Show AI
payload** button, and a **Network log** panel that lists every request the page
made.

## How the redaction works

Redaction is not a single find-and-replace. It is a pipeline, and it fails
closed:

- Every filled contact value is replaced, longest first, so a full profile URL
  wins over the handle inside it.
- Names are matched on word boundaries, and their parts are matched too — a first
  name typed alone still gets caught.
- Profile handles are taken from the URL path only, never from a query string,
  so `github.com/user?tab=repositories` still removes `user`.
- Any remaining email address is replaced.
- Any remaining 8–15 digit number is replaced, unless it is a year range or a
  decimal.
- The result is scanned again. If any known value survives, generation is
  stopped.

The same implementation exists in the browser and in the server, and the test
suite asserts that both produce byte-identical output for the same input. A
privacy rule that only one side enforces is not a rule.

## Verify it yourself

1. Open your browser's developer tools, go to **Network**, and press
   **Generate**. You will see one request to your provider. Open its payload.
2. Search the payload for your name, your email address and your phone number.
   They are not there — the model never received them.
3. Use the **Show AI payload** button to read the request before it leaves.
4. Run the app with `RESUMETEX_ALLOW_COMPILE=0` and the server refuses to
   compile anything, so the only machine that ever sees your document is yours.

## Where the PDF is compiled

By default, on your own machine, with your own MiKTeX or TeX Live installation —
the document never leaves the computer. The web app exposes the same choice the
desktop app has:

- **Local** (default) — `pdflatex` runs as a child process in a temporary folder
  that is deleted afterwards. Nothing is uploaded.
- **Online** — opt-in, off by default, and it uploads the entire document
  *including* your contact details. The UI says so before you enable it.

## Honest limitations

Privacy claims are only as good as their edges, so here are the edges:

- If you paste personal data into the resume text in a form the redactor does
  not recognise (a name that never appeared in a contact field, for example), it
  can reach the provider. The contact fields, generic emails and phone-like
  numbers are covered; arbitrary names are not detectable in general.
- Online compiling is a third-party service. Its handling of uploaded data is
  outside this project's control, which is why it is off by default.
- MiKTeX may contact package repositories if a LaTeX package is missing. The
  templates use only standard packages.
- The AI provider still sees your *non-personal* resume content, and its own
  privacy policy applies to that.
- An API key saved in a browser is only as safe as the browser and the device.
  The desktop app protects it with Windows DPAPI; in the browser, "remember
  key" is off by default.

## Why we wrote this down

A resume is the most personal document a working person owns. Building one with
AI should not require publishing it first. The whole design of this project
follows from one sentence: the model may help you write, but it never needs to
know who you are.

## Run it yourself

```bash
git clone <this repository>
cd resumetex-web
pip install -e .
resumetex-web serve
```

Then open `http://127.0.0.1:5000`. It binds to loopback, stores nothing, and has
no telemetry of any kind. MIT licensed — read the code, run it on your own
machine, and check the privacy claims yourself.
