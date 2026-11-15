"""Flask application factory."""

from __future__ import annotations

from flask import Flask, render_template

from .api import api
from .config import Config

__version__ = "0.2.0"


def create_app(config: Config | None = None) -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    cfg = config or Config()

    app.config.update(
        ALLOW_COMPILE=cfg.allow_compile,
        ALLOW_ONLINE_COMPILE=cfg.allow_online_compile,
        ONLINE_COMPILE_URL=cfg.online_compile_url,
        COMPILE_TIMEOUT=cfg.compile_timeout,
        JSON_AS_ASCII=cfg.json_ascii,
        MAX_CONTENT_LENGTH=cfg.max_body_mb * 1024 * 1024,
        RESUMETEX_VERSION=__version__,
    )
    app.config["JSON_SORT_KEYS"] = False

    app.register_blueprint(api)

    @app.get("/")
    def index():
        return render_template("index.html", version=__version__,
                               allow_compile=cfg.allow_compile)

    @app.get("/gallery")
    def gallery_page():
        return render_template("gallery.html", version=__version__)

    @app.get("/privacy")
    def privacy_page():
        return render_template("privacy.html", version=__version__)

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.after_request
    def _no_store(response):
        # Resume data must not linger in a shared cache.
        if response.mimetype == "application/json" or "text/html" in (response.mimetype or ""):
            response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    return app
