"""Voice command - launches the full voice assistant pipeline (app_optimized.py)."""

import os
import sys


def run(args):
    """Run the voice assistant pipeline."""
    # Resolve app_optimized.py relative to this file
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    script = os.path.join(base, "app_optimized.py")

    if not os.path.exists(script):
        print(f"❌ Voice pipeline not found: {script}")
        return

    # Forward relevant flags to app_optimized.py
    extra = []
    if getattr(args, "no_search", False):
        extra.append("--no-search")
    if getattr(args, "no_vision", False):
        extra.append("--no-vision")
    if getattr(args, "model", None):
        extra += ["--model", args.model]
    if getattr(args, "whisper_model", None):
        extra += ["--whisper-model", args.whisper_model]
    if getattr(args, "backend", None):
        extra += ["--backend", args.backend]

    cmd = [sys.executable, script] + extra
    os.execv(sys.executable, cmd)   # replace current process - clean exit on Ctrl+C
