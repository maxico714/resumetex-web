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
RUN set -eux; \
    if apt-get update -qq 2>/dev/null; then \
        apt-get install -y --no-install-recommends \
            texlive-latex-base \
            texlive-latex-recommended \
            texlive-fonts-recommended \
            || echo "WARNING: LaTeX packages could not be installed - PDF compile disabled"; \
        rm -rf /var/lib/apt/lists/* || true; \
    else \
        echo "WARNING: apt-get update failed (read-only filesystem?) - continuing without LaTeX"; \
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
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+__import__('os').environ.get('PORT','8000')+'/healthz', timeout=4).status==200 else 1)"

# Render injects PORT; the shell form expands it.
CMD gunicorn wsgi:app --bind 0.0.0.0:${PORT:-8000} --workers 1 --threads 4 --timeout 120 --access-logfile - --error-logfile -
