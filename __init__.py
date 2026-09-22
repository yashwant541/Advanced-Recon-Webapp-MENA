"""iraq_recon: framework-independent financial reconciliation engine.

This package must never import Flask, Dataiku, Dash, Django, FastAPI, or any
UI/browser library. Only ``iraq_recon.adapters.dataiku_io`` (and other
adapter modules explicitly named for a runtime) may import ``dataiku``.

Public entry point: :mod:`iraq_recon.api`.
"""

__version__ = "0.1.0"
