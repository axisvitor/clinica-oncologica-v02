"""
Shared Firebase Auth transformations.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import HTTPException, status
from firebase_admin import auth

_RESERVED_TOKEN_CLAIMS = {
    "iss",
    "aud",
    "auth_time",
    "user_id",
    "sub",
    "iat",
    "exp",
    "firebase",
    "uid",
    "email",
    "email_verified",
    "phone_number",
    "name",
    "picture",
    "identities",
}


def extract_custom_claims(decoded_token: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in decoded_token.items() if k not in _RESERVED_TOKEN_CLAIMS}


def build_token_user_info(decoded_token: Dict[str, Any]) -> Dict[str, Any]:
    custom_claims = extract_custom_claims(decoded_token)
    return {
        "uid": decoded_token.get("uid"),
        "email": decoded_token.get("email"),
        "email_verified": decoded_token.get("email_verified", False),
        "name": decoded_token.get("name"),
        "picture": decoded_token.get("picture"),
        "custom_claims": custom_claims,
        "auth_time": decoded_token.get("auth_time"),
        "exp": decoded_token.get("exp"),
    }


def serialize_user_record(user_record: Any) -> Dict[str, Any]:
    return {
        "uid": user_record.uid,
        "email": user_record.email,
        "email_verified": user_record.email_verified,
        "display_name": user_record.display_name,
        "photo_url": user_record.photo_url,
        "disabled": user_record.disabled,
        "custom_claims": user_record.custom_claims or {},
        "provider_data": [
            {
                "provider_id": provider.provider_id,
                "uid": provider.uid,
                "email": provider.email,
            }
            for provider in user_record.provider_data
        ],
        "created_at": user_record.user_metadata.creation_timestamp,
        "last_sign_in": user_record.user_metadata.last_sign_in_timestamp,
    }


def verify_token_and_build_user_info(
    token: str,
    *,
    logger: logging.Logger,
    propagate_unexpected: bool = False,
) -> Dict[str, Any]:
    """
    Verify Firebase ID token and normalize expected auth errors.

    When `propagate_unexpected` is True, unknown exceptions are re-raised so
    callers can let outer circuit breakers account for provider failures.
    """
    try:
        decoded_token = auth.verify_id_token(token, check_revoked=True)
        return build_token_user_info(decoded_token)
    except auth.ExpiredIdTokenError:
        logger.warning("Expired token attempted")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except auth.RevokedIdTokenError:
        logger.warning("Revoked token attempted")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except auth.InvalidIdTokenError as exc:
        logger.warning(f"Invalid token: {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except auth.UserDisabledError:
        logger.warning("Disabled user attempted authentication")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account has been disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as exc:
        logger.error(f"Unexpected error verifying token: {str(exc)}")
        if propagate_unexpected:
            raise
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
