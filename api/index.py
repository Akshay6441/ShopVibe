"""Vercel serverless entrypoint for ShopVibe.

Vercel looks for a FastAPI instance named `app` in api/index.py and serves
the whole FastAPI app as a single Vercel Function, routing all /api/* paths
to it. The real app lives in backend/main.py, so we expose it here.
"""
import os
import sys

_BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

try:
    from main import app  # noqa: E402, F401
except Exception:
    import traceback

    traceback.print_exc()
    raise
