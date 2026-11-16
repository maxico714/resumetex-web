# ResumeTeX Web — Render / Docker deployment image.
#
# The image installs LaTeX and then compiles a real resume for every gallery
# template. A missing package fails the build, so Render can never deploy an
# instance whose "Compile PDF" button is silently broken.
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

# --- system packages + LaTeX engine ----------------------------------------
# The templates need: geometry, hyperref, xcolor, microtype, titlesec,
# enumitem, helvet/parskip, lmodern.  titlesec and enumitem live in
# texlive-latex-extra — WITHOUT it every compile fails with
# "File `titlesec.sty' not found".  lmodern.sty is a separate package
# (texlive-latex-base only pulls the fonts).  newtxtext/newtxmath live in the
# ~2 GB texlive-fonts-extra, so the templates use them only when present and
# fall back to mathptmx otherwise.
RUN set -eux; \
    apt-get -o Acquire::Retries=3 update; \
    apt-get -o Acquire::Retries=3 install -y --no-install-recommends \
        lmodern \
        texlive-latex-base \
        texlive-latex-recommended \
        texlive-latex-extra \
        texlive-fonts-recommended; \
    rm -rf /var/lib/apt/lists/*; \
    command -v pdflatex; \
    pdflatex --version | head -n 1

WORKDIR /app

# --- python dependencies first (better layer caching) -----------------------
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# --- application ------------------------------------------------------------
COPY . .

# Strict build-time gate: compile every gallery template to a real PDF with
# the same code path the server uses.  Remove this and a broken TeX install
# only shows up when a user clicks Compile PDF.
RUN python -m resumetex_web.docker_check

ENV RESUMETEX_HOST=0.0.0.0 \
    PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys,os; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/healthz', timeout=4).status==200 else 1)"

# Render injects PORT; the shell form expands it.
CMD gunicorn wsgi:app --bind 0.0.0.0:${PORT:-8000} --workers 1 --threads 4 --timeout 120 --access-logfile - --error-logfile -
