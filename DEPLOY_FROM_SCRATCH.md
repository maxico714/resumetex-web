# Deploy ResumeTeX Web on Render from scratch

This is the complete runbook for a **new** Render service. You do not need a
local TeX install, a database, a credit card, or any AI API key. Everything the
service needs is in this repository.

- **Repo:** <https://github.com/maxico714/resumetex-web> (public)
- **First build:** about 10–20 minutes, because the image downloads and installs
  TeX Live (~300–500 MB).
- **Later builds:** a few minutes; Render caches the Docker layers.
- **Result:** a real PDF from `pdflatex` running on your own Render instance.
- **Private by default:** the CV is compiled on the app server, never uploaded
  to a third party.

> **The one rule that matters:** the Render service must use the **Docker**
> runtime, not the Python runtime. Render's Python runtime has read-only `apt`
> lists, so it cannot install `pdflatex`. Docker installs the engine inside the
> image.

---

## 1. Recommended: deploy with the Blueprint

The repository contains `render.yaml`, so Render can create the whole service
from one link.

### One-click link

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/maxico714/resumetex-web)

Copy this if the button does not open:

```text
https://render.com/deploy?repo=https://github.com/maxico714/resumetex-web
```

### Clicks

1. Open the link and sign in to Render (GitHub sign-in is fine).
2. If Render asks for GitHub access, authorize it for
   `maxico714/resumetex-web`. The repo is public, so read access is enough.
3. Render opens the **Blueprint** screen. Use:
   - **Blueprint Name:** `resumetex-web`
   - **Branch:** `main`
   - **Blueprint Path:** `render.yaml`
4. Review the service card. It must say:
   - **Service:** `resumetex-web`
   - **Runtime:** Docker
   - **Plan:** Free
   - **Health Check Path:** `/healthz`
   - **Environment variables:** `RESUMETEX_ALLOW_COMPILE=1`,
     `RESUMETEX_ALLOW_ONLINE_COMPILE=0`, `RESUMETEX_HOST=0.0.0.0`
5. Click **Apply** (some screens label it **Create Resources** or
   **Deploy Blueprint**).
6. Watch the build log. Do not close the tab. The important milestones are:
   - `apt-get ... install ... lmodern texlive-latex-base ...`
   - `python -m resumetex_web.docker_check`
   - one `ok <template>: ...` line per gallery template
   - **`OK: all 15 gallery templates compiled to PDF.`**
   - `Your service is live 🎉`
7. Open the service URL shown at the top of the dashboard. It is normally
   `https://resumetex-web.onrender.com`; Render adds a suffix if the name is
   already taken. The dashboard URL is the authoritative one.

> If Render says a Blueprint for this repository already exists (for example,
> from the deleted service), open **Blueprints** in the dashboard, select it,
> and click **Sync** instead of creating a second one. The sync still creates a
> fresh service if the old one was deleted.

### If the build fails immediately

Check **Settings → Build & Deploy → Source**. If the runtime is Python, stop:
that is the wrong runtime and the apt step will fail. Change it to Docker, or
delete the service and repeat the Blueprint flow. See
[Runtime must be Docker](#runtime-must-be-docker).

---

## 2. Fallback: create the service manually

Use this if the Blueprint link does not work, or if you prefer to configure the
service by hand.

1. In the Render Dashboard, click **New → Web Service**.
2. Connect the GitHub repo `maxico714/resumetex-web` and select it.
3. Fill the form exactly:

| Field | Value |
|---|---|
| **Name** | `resumetex-web` (or any unique name; the URL follows it) |
| **Region** | The one closest to you; keep it for future deploys |
| **Branch** | `main` |
| **Root Directory** | leave blank |
| **Language / Runtime** | **Docker** |
| **Dockerfile Path** | `./Dockerfile` |
| **Docker Context Directory** | `.` (or leave blank) |
| **Build Command** | leave blank — the Dockerfile builds the image |
| **Start Command / Docker Command** | leave blank — the image's `CMD` starts gunicorn |
| **Instance Type / Compute Plan** | **Free** |
| **Health Check Path** | `/healthz` |
| **Auto-Deploy** | **Yes** (deploy on every push to `main`) |

4. Open **Advanced** and add these environment variables:

| Key | Value |
|---|---|
| `RESUMETEX_ALLOW_COMPILE` | `1` |
| `RESUMETEX_ALLOW_ONLINE_COMPILE` | `0` |
| `RESUMETEX_HOST` | `0.0.0.0` |

5. Do **not** add `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, or any other AI key.
   Keys stay in the user's browser, by design.
6. Click **Create Web Service** / **Deploy Web Service**.
7. Wait for **`OK: all 15 gallery templates compiled to PDF.`** in the log.

If the Docker fields are hidden, make sure **Language** is set to **Docker**
first; Render only shows them for Docker services.

---

## 3. Verify the deployment

Do these in order. Stop at the first failure and use
[Troubleshooting](#5-troubleshooting).

### 3.1 Health check

Open this in a browser:

```text
https://YOUR-SERVICE.onrender.com/healthz
```

Expected: HTTP 200 with `{"ok":true}`. This is the path Render uses for its own
health check, so it should respond even while the app is waking up.

Then check the LaTeX details. In PowerShell:

```powershell
Invoke-RestMethod https://YOUR-SERVICE.onrender.com/api/health |
  ConvertTo-Json -Depth 6
```

Or with curl / Git Bash:

```bash
curl -s https://YOUR-SERVICE.onrender.com/api/health
```

A healthy new instance returns values like:

```json
{
  "ok": true,
  "app": "ResumeTeX Web",
  "pdflatex": true,
  "latex": {
    "found": true,
    "path": "/usr/bin/pdflatex",
    "missing": []
  },
  "allowCompile": true,
  "allowOnlineCompile": false
}
```

The three things that must be true:

- `"pdflatex": true`
- `"latex": {"found": true, ..., "missing": []}`
- `"allowCompile": true`

`allowOnlineCompile: false` is correct for the private default. Do not change it
unless you understand the privacy trade-off in section 4.

### 3.2 Test LaTeX setup from the UI

1. Open the service URL.
2. Click **Load sample** (or fill the form yourself).
3. Click **Render CV**.
4. In the **Output** card, click **Test LaTeX setup**.
5. Expected: a green result showing the local engine, a version line, and a
   successful one-page probe. If it fails, click **Copy diagnostics**.

The probe compiles a tiny document that contains no personal data.

### 3.3 Compile a real PDF

1. With the sample CV rendered, leave the compiler method at
   **Server pdflatex (private)**.
2. Click **Compile PDF**.
3. Expected: a PDF preview and a **Download PDF** button. The sample is roughly
   100 KB and one or two pages.
4. Optional verification in browser DevTools → **Network** → the
   `/api/compile` response headers:
   - `X-ResumeTeX-Engine: local-pdflatex`
   - `X-ResumeTeX-Pages: 1` (or `2`)
   - `X-ResumeTeX-Online: false`

### 3.4 Mobile check

Open the URL on a phone, or use DevTools device mode at 375 px width. The
compile controls stay reachable in the sticky bottom bar and the page should not
scroll sideways.

---

## 4. Compiler methods and privacy

The Output card offers a compiler selector:

| Method | What happens | Privacy |
|---|---|---|
| **Server pdflatex** (default) | `pdflatex` runs on your Render instance | The CV stays on your server |
| **Automatic** | Tries the server first; uploads only if the server fails | Uploads the full CV on fallback |
| **Online compiler** | Sends the `.tex` to a third-party compile service | Uploads the full CV, including name, email, phone |

`Automatic` and `Online compiler` are hidden unless the service has
`RESUMETEX_ALLOW_ONLINE_COMPILE=1`. The repository default is `0`, so a fresh
deploy can only compile privately. If you enable them, the UI shows a
confirmation dialog before every upload.

This setting controls only **PDF compilation**. The separate promise still
holds: contact details are redacted before any AI request, and AI keys live in
the browser, not in Render.

To enable the online fallback:

1. Render Dashboard → your service → **Environment**.
2. Set `RESUMETEX_ALLOW_ONLINE_COMPILE` to `1`.
3. Save; Render redeploys the service.
4. Reload the app. The extra methods appear with the warning text.

To go back to the private-only mode, set it to `0` again.

---

## 5. Troubleshooting

### Runtime must be Docker

**Symptom:** the build fails at the apt step with a read-only filesystem, a
missing `apt` list directory, or `Unable to locate package texlive-latex-base`.

**Cause:** the service is using Render's native Python runtime. That runtime
does not allow OS package installation.

**Fix:** Render Dashboard → service → **Settings → Build & Deploy → Source →
Edit** → set **Runtime → Docker**, Dockerfile Path `./Dockerfile`, context `.`,
clear any build/start commands, save, then **Manual Deploy → Deploy latest
commit**. If the dashboard does not let you change the runtime, delete the
service and use the Blueprint flow in section 1.

### Build fails inside `docker_check` with a missing `.sty`

**Symptom:** a line like `! LaTeX Error: File 'titlesec.sty' not found.` and the
build stops before going live.

This is the build gate doing its job: it refuses to deploy a broken PDF button.
Add the Debian package that provides the file to the `apt-get install` list in
`Dockerfile`, then push. Known mappings:

| Missing file | Debian package |
|---|---|
| `titlesec.sty`, `enumitem.sty` | `texlive-latex-extra` |
| `lmodern.sty` | `lmodern` |
| `mathptmx.sty`, `helvet.sty` | `texlive-latex-base` |
| `xcolor.sty`, `microtype.sty` | `texlive-latex-recommended` |
| `newtxtext.sty`, `newtxmath.sty` | `texlive-fonts-extra` (~2 GB; intentionally not installed) |

To look up another file on a Debian machine:

```bash
apt-file search filename.sty
```

The built-in gallery templates do not need `texlive-fonts-extra`; the two serif
presets fall back from `newtx` to `mathptmx`. If you paste your own LaTeX that
requires `newtx`, either remove that dependency or accept a much larger build.

### Build fails while downloading Debian packages

**Symptom:** `Temporary failure resolving deb.debian.org`, a timeout, or a
truncated apt download.

**Fix:** retry with **Manual Deploy → Clear build cache & deploy**. The
Dockerfile already sets `Acquire::Retries=3`. Transient Debian mirror failures
are the usual cause.

### Build succeeds but `/api/health` says `"pdflatex": false`

The running container is not the image built from this Dockerfile. Confirm:

- **Settings → Build & Deploy → Source → Runtime** is **Docker**.
- The deploy log contains `OK: all 15 gallery templates compiled to PDF.`
- You are checking the URL of this service, not an older duplicate.

Delete any duplicate service, then redeploy.

### Compile PDF returns `503` or “compile disabled”

`RESUMETEX_ALLOW_COMPILE` is not `1` in the running instance. Add it under
**Environment**, save, wait for the redeploy, and reload. Verify with
`/api/health` → `"allowCompile": true`.

### First compile takes a long time, then succeeds

Free instances spin down after 15 minutes without traffic. The next request has
to boot the container (about a minute), then LaTeX compiles the CV. The UI waits
up to 150 seconds. This is normal on the free plan; retry once if the first
request is a cold start.

### `502 Bad Gateway` or the page never loads

The app process did not start. Check the service **Logs** for a gunicorn or
Python traceback. The image starts:

```text
gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120
```

Make sure you did **not** set a custom Docker command, a start command, or
`RESUMETEX_HOST=127.0.0.1`. Render injects `$PORT`; the image binds to it.

### The build is stuck at the apt layer for a long time

TeX Live is large. The first build downloads several hundred megabytes and can
take 10–20 minutes; the log may look idle while apt downloads. Wait for the
120-minute build limit before assuming it is hung. Later builds reuse the cached
apt layer and are much faster.

### “Service Suspended” or the free instance hours ran out

Free workspaces get 750 instance hours per month. A spun-down service does not
consume them, but several free services or a service kept awake 24/7 can exhaust
the allowance. Wait for the monthly reset or move the service to a paid plan.

### The online compiler is unavailable

`latex.ytotech.com` is a third-party service with no uptime guarantee. Keep the
default `RESUMETEX_ALLOW_ONLINE_COMPILE=0` if you want the deployment to depend
only on your own server. Server-side compilation does not use the internet.

---

## 6. Free plan limits

These are Render's limits for a Free web service, not app bugs:

| Limit | Effect |
|---|---|
| 0.1 CPU / 512 MB RAM | Fine for one CV at a time. Concurrent compiles queue. |
| Spin down after 15 idle minutes | First request after idle takes about a minute. |
| 750 instance hours / workspace / month | Shared by all free services; spun-down time is free. |
| 500 build pipeline minutes / month (Hobby) | The first TeX build uses a chunk of this; cached builds are cheaper. |
| Ephemeral filesystem | No data is stored anyway. Do not add a database or disk. |
| No shell access | Use the dashboard logs and `/api/health`. |

The service is public. Anyone with the URL can use the compile endpoint, and
compilation consumes CPU. For a widely shared production deployment, add
authentication or rate limiting, or run on a paid instance. For personal use,
the free plan is adequate.

---

## 7. Updating, rollback, and deleting

- **Update the app:** push to `main`. Auto-deploy builds a new image and runs
  the 15-template gate again.
- **Change an environment variable:** **Environment** → edit → save. Render
  redeploys automatically.
- **Change the Blueprint:** edit `render.yaml` in the repo, then
  **Blueprints → your blueprint → Sync**.
- **Force a clean rebuild:** **Manual Deploy → Clear build cache & deploy**.
- **Roll back:** **Deploys** tab → choose one of the previous two deploys →
  **Rollback** (free plan supports the two most recent).
- **Delete and start over:** **Settings → Delete Web Service**. This does not
  touch GitHub. Then repeat section 1. The public repo already contains
  everything needed.

Do not create a new service with the Python runtime “just to test it”; that
path cannot install TeX and will waste a build.

---

## 8. Optional: test the image locally first

If you have Docker Desktop, you can reproduce the Render build on your machine.
This is optional and uses the same several hundred megabytes of downloads.

```powershell
git clone https://github.com/maxico714/resumetex-web
cd resumetex-web
docker build -t resumetex-web .
docker run --rm -p 8000:8000 `
  -e RESUMETEX_ALLOW_COMPILE=1 `
  -e RESUMETEX_ALLOW_ONLINE_COMPILE=0 `
  resumetex-web
```

Open <http://127.0.0.1:8000>. Press `Ctrl+C` to stop. A successful build ends
with the same `OK: all 15 gallery templates compiled to PDF.` line. This is the
closest possible preview of what Render will run.

If the local build fails, the error is in the repository, not in Render; fix it
before deploying.

---

## 9. Final checklist

- [ ] GitHub repo `maxico714/resumetex-web` is reachable and on `main`.
- [ ] Render service exists with **Runtime: Docker** (not Python).
- [ ] Dockerfile path is `./Dockerfile`, context is `.`.
- [ ] Plan is **Free** (or a paid plan if you need no sleep).
- [ ] Health check path is `/healthz`.
- [ ] `RESUMETEX_ALLOW_COMPILE=1`
- [ ] `RESUMETEX_ALLOW_ONLINE_COMPILE=0` (private default)
- [ ] `RESUMETEX_HOST=0.0.0.0`
- [ ] No AI API keys in Render environment variables.
- [ ] Build log shows `OK: all 15 gallery templates compiled to PDF.`
- [ ] `/healthz` returns 200.
- [ ] `/api/health` shows `pdflatex: true` and `missing: []`.
- [ ] **Test LaTeX setup** succeeds in the app.
- [ ] **Compile PDF** produces a downloadable PDF.
- [ ] Mobile layout at 375 px has no horizontal scrolling.

---

## 10. If it still fails, collect these four things

1. The service URL and the Render deploy ID (from **Deploys**).
2. The full `/api/health` JSON.
3. The text from **Copy diagnostics** in the Output card.
4. The last ~50 lines of the build log, especially the first error.

With those four, the failure is almost always identifiable from the missing
`.sty` file or the runtime setting. Never paste a real CV, API key, or contact
details into a public issue.
