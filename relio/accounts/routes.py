# relio/accounts/routes.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from .google import GoogleOAuth
from .passwords import hash_password, verify_password
from .store import UserStore
from .tokens import issue_token


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


def build_accounts_router(
    store: UserStore,
    secret: str,
    *,
    google: Optional[GoogleOAuth] = None,
    tenant: Optional[str] = None,
    token_ttl: int = 3600,
) -> APIRouter:
    """Register/login (password) + optional Google OAuth. Login issues a JWT that
    `JWTAuth(secret)` verifies — wire that as the app's auth hook."""
    router = APIRouter(prefix="/auth")

    def _token(user):
        return {"token": issue_token(user, secret, ttl=token_ttl), "user_id": user.id}

    @router.post("/register", operation_id="register")
    def register(req: RegisterRequest):
        if store.get_by_email(req.email) is not None:
            raise HTTPException(status_code=409, detail="email already registered")
        user = store.create(req.email, password_hash=hash_password(req.password), tenant=tenant)
        return _token(user)

    @router.post("/login", operation_id="login")
    def login(req: LoginRequest):
        user = store.get_by_email(req.email)
        if user is None or not user.password_hash or not verify_password(req.password, user.password_hash):
            raise HTTPException(status_code=401, detail="invalid credentials")
        return _token(user)

    if google is not None:
        @router.get("/google", operation_id="google_login")
        def google_login():
            return RedirectResponse(google.authorize_url())

        @router.get("/google/callback", operation_id="google_callback")
        def google_callback(code: str):
            info = google.exchange_code(code)
            email = info.get("email")
            if not email:
                raise HTTPException(status_code=400, detail="no email from Google")
            user = store.get_by_email(email) or store.create(
                email, provider="google", name=info.get("name"), tenant=tenant
            )
            return _token(user)

    return router
