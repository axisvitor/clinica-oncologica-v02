#!/usr/bin/env python3
"""M015/S02 session seam probe entrypoint.

The real Taskiq task lives in ``m015_session_security_taskiq.py`` and is mounted
into the backend package for worker import.  This thin probe entrypoint keeps the
runtime surface explicit: Compose runs ``session_seam.py`` for the API/cache/DB
probe while the worker imports ``app.tasks.m015_session_security_taskiq``.
"""

from __future__ import annotations

from m015_session_security_taskiq import main


if __name__ == "__main__":
    raise SystemExit(main())
