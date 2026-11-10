"""Vercel serverless entrypoint for ShopVibe."""
import os
import sys

_BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from main import app

# Explicit top-level assignment for Vercel AST entrypoint detector
app = app
