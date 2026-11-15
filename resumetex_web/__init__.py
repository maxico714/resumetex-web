"""ResumeTeX Web — a private, local-first resume builder.

The personal details and the AI provider key live in the browser. The server
never stores resume data and never receives contact details for AI calls.
"""

from .app import create_app, __version__

__all__ = ["create_app", "__version__"]
