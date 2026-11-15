"""Command line entry point: `resumetex-web serve`."""

from __future__ import annotations

import argparse
import sys

from .app import create_app
from .config import Config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="resumetex-web",
                                     description="Private, local-first resume builder.")
    parser.add_argument("command", nargs="?", default="serve", choices=["serve"])
    parser.add_argument("--host", default=None, help="default 127.0.0.1 (loopback only)")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--no-compile", action="store_true",
                        help="disable server-side pdflatex (the server then never sees a document)")
    parser.add_argument("--allow-online-compile", action="store_true",
                        help="allow compiling through a third-party service (uploads the document)")
    args = parser.parse_args(argv)

    config = Config()
    if args.host:
        config.host = args.host
    if args.port:
        config.port = args.port
    if args.debug:
        config.debug = True
    if args.no_compile:
        config.allow_compile = False
    if args.allow_online_compile:
        config.allow_online_compile = True

    app = create_app(config)
    print(f"ResumeTeX Web → http://{config.host}:{config.port}")
    print(f"  local pdflatex : {'on' if config.allow_compile else 'off'}")
    print(f"  online compile: {'on' if config.allow_online_compile else 'off'}")
    app.run(host=config.host, port=config.port, debug=config.debug, threaded=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
