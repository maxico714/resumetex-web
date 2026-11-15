"""WSGI entry point.

Local:      python -m resumetex_web.cli serve
Render:     gunicorn wsgi:app
"""

from __future__ import annotations

import os

from resumetex_web.app import create_app
from resumetex_web.config import Config

config = Config()

# Render (and most PaaS providers) inject the port as PORT.
port = os.environ.get("PORT")
if port:
    config.port = int(port)

# A public instance must never be able to compile documents for strangers by
# default. Set RESUMETEX_ALLOW_COMPILE=1 explicitly to turn it back on.
if os.environ.get("RESUMETEX_ALLOW_COMPILE") == "1":
    config.allow_compile = True
elif os.environ.get("RESUMETEX_ALLOW_COMPILE", "").lower() in ("0", "false", "no"):
    config.allow_compile = False

if os.environ.get("RESUMETEX_ALLOW_ONLINE_COMPILE") == "1":
    config.allow_online_compile = True

app = create_app(config)

if __name__ == "__main__":
    app.run(host=config.host, port=config.port)
