"""Authentication endpoints: login, refresh, me."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from pydantic import BaseModel

from api.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from api.auth.models import get_user
from api.auth.dependencies import get_current_user, User
from api.audit.logger import log_login

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class MeResponse(BaseModel):
    username: str
    full_name: str
    role: str


@router.post("/login", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends()):
    user = get_user(form.username)
    if user is None or not verify_password(form.password, user.hashed_password):
        log_login(form.username, success=False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    log_login(user.username, success=True)
    access = create_access_token(user.username, user.role)
    refresh = create_refresh_token(user.username, user.role)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest):
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("not a refresh token")
        username: str = payload["sub"]
        role: str = payload["role"]
    except (JWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    access = create_access_token(username, role)
    new_refresh = create_refresh_token(username, role)
    return TokenResponse(access_token=access, refresh_token=new_refresh)


@router.get("/me", response_model=MeResponse)
async def me(current_user: User = Depends(get_current_user)):
    return MeResponse(
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role,
    )
