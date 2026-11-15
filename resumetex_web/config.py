"""Configuration. No resume data is ever stored on the server."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Config:
    # Bind to loopback by default: the app is meant to run on your own machine.
    host: str = os.environ.get("RESUMETEX_HOST", "127.0.0.1")
    port: int = int(os.environ.get("RESUMETEX_PORT", "5000"))
    debug: bool = _bool("RESUMETEX_DEBUG", False)

    # Local pdflatex is the default engine. Disable it to run a PII-free
    # instance that never compiles anything on the server.
    allow_compile: bool = _bool("RESUMETEX_ALLOW_COMPILE", True)
    online_compile_url: str = os.environ.get("RESUMETEX_ONLINE_URL", "https://latex.ytotech.com/builds/sync")
    compile_timeout: int = int(os.environ.get("RESUMETEX_COMPILE_TIMEOUT", "75"))

    # Uploads a document to a third-party service (includes contact details).
    allow_online_compile: bool = _bool("RESUMETEX_ALLOW_ONLINE_COMPILE", False)

    max_body_mb: int = int(os.environ.get("RESUMETEX_MAX_BODY_MB", "8"))
    json_ascii: bool = False

    def as_dict(self) -> dict:
        return {
            "host": self.host,
            "port": self.port,
            "allowCompile": self.allow_compile,
            "allowOnlineCompile": self.allow_online_compile,
            "onlineCompileUrl": self.online_compile_url,
        }
