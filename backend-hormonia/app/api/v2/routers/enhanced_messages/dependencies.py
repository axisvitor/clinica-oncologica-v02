"""
Helper functions and dependencies for enhanced messages API.

This module contains shared utility functions used across multiple
enhanced messaging endpoints.
"""

from typing import Optional, Dict
from datetime import datetime
import re
import logging
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


def _check_admin_or_owner(
    current_user: dict, resource_owner_id: Optional[str] = None
) -> None:
    """
    Check if user is admin or owns the resource.

    Args:
        current_user: User data from session
        resource_owner_id: ID of resource owner (optional)

    Raises:
        HTTPException: If user lacks permissions
    """
    role = current_user.get("role", "").lower()
    user_id = str(current_user.get("id", ""))

    is_admin = role in ["admin", "administrator"]
    is_owner = resource_owner_id is None or user_id == str(resource_owner_id)

    if not (is_admin or is_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )


def _render_template(template_content: str, variables: Dict[str, str]) -> str:
    """
    Render template by replacing variables.

    Args:
        template_content: Template string with {{variable}} placeholders
        variables: Dictionary of variable values

    Returns:
        Rendered content

    Raises:
        ValueError: If required variables are missing
    """
    # Find all variables in template
    var_pattern = r"\{\{(\w+)\}\}"
    template_vars = set(re.findall(var_pattern, template_content))

    # Check for missing variables
    missing_vars = template_vars - set(variables.keys())
    if missing_vars:
        raise ValueError(f"Missing required variables: {', '.join(missing_vars)}")

    # Replace variables
    rendered = template_content
    for var_name, var_value in variables.items():
        rendered = rendered.replace(f"{{{{{var_name}}}}}", str(var_value))

    return rendered


async def _calculate_engagement_score(
    redis_cache,
    message_id: str,
    sent_at: datetime,
    delivered_at: Optional[datetime],
    read_at: Optional[datetime],
    responded_at: Optional[datetime],
) -> float:
    """
    Calculate engagement score for a message.

    Scoring:
    - Delivered: 25 points
    - Read: 35 points
    - Responded: 40 points
    - Speed bonuses for quick reads/responses

    Args:
        redis_cache: Redis cache instance
        message_id: Message ID
        sent_at: When message was sent
        delivered_at: When message was delivered
        read_at: When message was read
        responded_at: When message was responded to

    Returns:
        Engagement score (0-100)
    """
    score = 0.0

    # Delivery (25 points)
    if delivered_at:
        score += 25.0
        delivery_time = (delivered_at - sent_at).total_seconds()
        if delivery_time < 5:  # Fast delivery bonus
            score += 5.0

    # Read (35 points)
    if read_at and delivered_at:
        score += 35.0
        read_time = (read_at - delivered_at).total_seconds() / 60  # minutes
        if read_time < 5:  # Quick read bonus
            score += 10.0
        elif read_time < 15:
            score += 5.0

    # Response (40 points)
    if responded_at and read_at:
        score += 40.0
        response_time = (responded_at - read_at).total_seconds() / 60  # minutes
        if response_time < 10:  # Quick response bonus
            score += 10.0
        elif response_time < 30:
            score += 5.0

    return min(score, 100.0)
