"""Supabase JWT verification for FastAPI.

Verifies Supabase Auth tokens using SUPABASE_JWT_SECRET.
Falls back to legacy custom JWT for dev accounts (backwards compatibility).
"""

import os
from typing import Optional

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL", "") or os.getenv("SUPABASE_URL", "")


def is_supabase_token(payload: dict) -> bool:
    """Check if JWT payload is from Supabase (has iss containing supabase)."""
    iss = payload.get("iss", "")
    return "supabase" in iss.lower() or "supabase.co" in iss


def decode_supabase_token(token: str) -> dict:
    """Decode and verify a Supabase JWT token.

    Returns payload dict with: sub (user UUID), email, role, user_metadata.
    Raises ValueError if token is invalid.
    """
    from jose import jwt, JWTError

    if not SUPABASE_JWT_SECRET:
        raise ValueError("SUPABASE_JWT_SECRET not configured")

    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid Supabase token: {e}")


def extract_user_from_supabase_payload(payload: dict) -> dict:
    """Extract user info from Supabase JWT payload.

    Returns dict compatible with the User model.
    """
    user_meta = payload.get("user_metadata", {}) or {}
    app_meta = payload.get("app_metadata", {}) or {}

    email = payload.get("email", "") or user_meta.get("email", "")
    full_name = user_meta.get("full_name", "") or user_meta.get("name", "") or email.split("@")[0]

    # Role: check app_metadata first, then default to "attorney" for OAuth users
    role = app_meta.get("role", "") or user_meta.get("role", "") or "attorney"

    return {
        "username": payload.get("sub", email),  # UUID as username
        "full_name": full_name,
        "email": email,
        "role": role,
    }
