# ResumeTeX Web — Render / Docker deployment image.
#
# The LaTeX engine is installed best-effort: if apt fails the image still
# builds and the app runs (AI + canvas + .tex export). PDF compile then reports
# a clear "pdflatex not found" instead of crashing.
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

# --- system packages + LaTeX engine (optional) -----------------------------
# The templates need: geometry, hyperref, xcolor, microtype, titlesec,
# enumitem, helvet/parskip, lmodern.  titlesec and enumitem live in
# texlive-latex-extra — WITHOUT it every compile fails with
# "File `titlesec.sty' not found".  lmodern.sty is a separate package
# (texlive-latex-base only pulls the fonts).  newtxtext/newtxmath live in the
# ~2 GB texlive-fonts-extra, so the templates use them only when present and
# fall back to mathptmx otherwise.
RUN set -eux; \
    if apt-get update -qq 2>/dev/null; then \
        apt-get install -y --no-install-recommends \
            lmodern \
            texlive-latex-base \
            texlive-latex-recommended \
            texlive-latex-extra \
            texlive-fonts-recommended \
            || echo "WARNING: TeX Live packages could not be installed - PDF compile disabled"; \
        rm -rf /var/lib/apt/lists/* || true; \
    else \
        echo "WARNING: apt-get update failed (read-only filesystem?) - continuing without LaTeX"; \
    fi; \
    if command -v pdflatex >/dev/null 2>&1; then \
        echo "pdflatex: $(command -v pdflatex)"; \
        printf '%s\n' \
            '\documentclass{article}' \
            '\usepackage{titlesec}' \
            '\usepackage{enumitem}' \
            '\usepackage{microtype}' \
            '\usepackage{xcolor}' \
            '\usepackage[hidelinks]{hyperref}' \
            '\begin{document}ResumeTeX smoke test\end{document}' \
            > /tmp/smoke.tex; \
        if pdflatex -interaction=nonstopmode -halt-on-error \
                -output-directory=/tmp /tmp/smoke.tex >/tmp/smoke.out 2>&1; then \
            echo "LaTeX smoke test: OK (titlesec + enumitem available)"; \
        else \
            echo "WARNING: LaTeX smoke test FAILED - PDF compile will not work:"; \
            tail -n 25 /tmp/smoke.out || true; \
        fi; \
        rm -f /tmp/smoke.* || true; \
    else \
        echo "WARNING: pdflatex not found - server-side PDF compile is disabled"; \
    fi

WORKDIR /app

# --- python dependencies first (better layer caching) -----------------------
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# --- application ------------------------------------------------------------
COPY . .

ENV RESUMETEX_HOST=0.0.0.0 \
    PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys,os; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/healthz', timeout=4).status==200 else 1)"

# Render injects PORT; the shell form expands it.
CMD gunicorn wsgi:app --bind 0.0.0.0:${PORT:-8000} --workers 1 --threads 4 --timeout 120 --access-logfile - --error-logfile -
