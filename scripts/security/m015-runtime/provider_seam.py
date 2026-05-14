#!/usr/bin/env python3
"""M015/S03 provider seam probe entrypoint.

The real Taskiq task lives in ``m015_provider_security_taskiq.py`` and is mounted
into the backend package for provider-worker import. This thin entrypoint keeps
the Compose probe surface explicit while sharing the worker/probe implementation.
"""

from __future__ import annotations

from m015_provider_security_taskiq import main


if __name__ == "__main__":
    raise SystemExit(main())
