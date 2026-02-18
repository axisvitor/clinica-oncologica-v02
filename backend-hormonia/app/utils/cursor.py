"""
Utilities for stable cursor-based pagination encoding.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Any


def encode_cursor(item_id: Any, created_at: datetime) -> str:
    """Encode pagination cursor payload as URL-safe base64 JSON."""
    cursor_data = {"id": str(item_id), "created_at": created_at.isoformat()}
    return base64.b64encode(json.dumps(cursor_data).encode()).decode()
