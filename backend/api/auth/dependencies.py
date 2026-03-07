"""FastAPI dependency injection for auth and RBAC."""

from typing import Optional

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from .jwt import decode_token
from .models import Role, User, get_user

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def _resolve_token(
    bearer: Optional[str] = Depends(oauth2_scheme),
    token: Optional[str] = Query(default=None),
) -> str:
    """Accept token from Authorization header or ?token= query param."""
    raw = bearer or token
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return raw


def get_current_user(token: str = Depends(_resolve_token)) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise credentials_error
        username: str = payload.get("sub", "")
    except JWTError:
        raise credentials_error

    user = get_user(username)
    if user is None:
        raise credentials_error
    return user


def require_role(*roles: Role):
    """Return a dependency that enforces one of the given roles."""
    def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not authorized for this action",
            )
        return current_user
    return _check


# Convenience role guards
require_attorney = require_role(Role.attorney, Role.admin)
require_admin = require_role(Role.admin)
require_any = get_current_user  # any authenticated user
