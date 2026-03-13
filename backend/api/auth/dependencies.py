"""FastAPI dependency injection for auth and RBAC.

Supports two token types:
  1. Supabase JWT (from OAuth flow) — verified with SUPABASE_JWT_SECRET
  2. Legacy custom JWT (dev accounts) — backwards compatible
"""

from typing import Optional

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt as _jwt

from .jwt import decode_token
from .models import Role, User, get_user

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def _resolve_token(
    bearer: Optional[str] = Depends(oauth2_scheme),
    token: Optional[str] = Query(default=None),
) -> str:
    raw = bearer or token
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return raw


def _try_decode_any(token: str) -> User:
    """Try Supabase JWT first, then fall back to legacy custom JWT."""
    # Peek at the payload without verification to detect token type
    try:
        unverified = _jwt.get_unverified_claims(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token format")

    from .supabase_auth import is_supabase_token, decode_supabase_token, extract_user_from_supabase_payload

    if is_supabase_token(unverified):
        try:
            payload = decode_supabase_token(token)
            info = extract_user_from_supabase_payload(payload)
            # Build a transient User object for Supabase users (not in local store)
            return User(
                username=info["username"],
                full_name=info["full_name"],
                role=Role(info["role"]) if info["role"] in Role.__members__.values() else Role.attorney,
                hashed_password="",
            )
        except ValueError as e:
            raise HTTPException(status_code=401, detail=str(e))

    # Legacy custom JWT
    try:
        from jose import JWTError
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        username = payload.get("sub", "")
        user = get_user(username)
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_current_user(token: str = Depends(_resolve_token)) -> User:
    return _try_decode_any(token)


def require_role(*roles: Role):
    def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not authorized for this action",
            )
        return current_user
    return _check


require_attorney = require_role(Role.attorney, Role.admin)
require_admin = require_role(Role.admin)
require_any = get_current_user
