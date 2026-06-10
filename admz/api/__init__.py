"""FastAPI application package for ADMZ.

**Import discipline (H-2).** This package's ``__init__`` is deliberately
side-effect free. It used to do ``from admz.api.main import app`` at import
time, which meant that importing *any* submodule here — e.g. the leaf
``admz.api.confirm_store`` that ``admz.operations`` depends on — would build
the entire FastAPI app (every router, CORS, templates, auth middleware) as a
side effect. That made every stdio MCP subprocess pay for the web stack it
never uses, and created a latent ``operations → api → routes → operations``
import cycle held together only by function-level imports.

``app`` is now exposed lazily via ``__getattr__``: ``from admz.api import app``
(or ``admz.api.app``) still works and builds the app on first access, but
merely importing a submodule no longer constructs it. Production launches the
server via the string target ``admz.api.main:app`` (see ``admz/__main__.py``),
which imports ``admz.api.main`` directly and is unaffected.
"""

__all__ = ["app"]


def __getattr__(name):
    # PEP 562 module-level __getattr__: build the app only when `app` is
    # actually accessed, not when this package (or a submodule) is imported.
    if name == "app":
        from admz.api.main import app

        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
