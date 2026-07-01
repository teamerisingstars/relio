# relio/accounts/routes.py
from __future__ import annotations

import hmac
import secrets
import time
from typing import Any, Callable, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from ..server.auth import JWTAuth
from ..server.security import RateLimiter
from .github import GitHubOAuth
from .google import GoogleOAuth
from .microsoft import MicrosoftOAuth
from .passwords import hash_password, verify_password
from .revocation import RevocationStore
from .store import User, UserStore
from .tokens import issue_reset_token, issue_token, issue_tokens, read_token

_STATE_COOKIE = "relio_oauth_state"


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: Optional[str] = None
    profile: dict[str, Any] = {}


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh: str


class ResetRequest(BaseModel):
    email: str


class ResetConfirm(BaseModel):
    token: str
    password: str


class LogoutRequest(BaseModel):
    refresh: str


def build_accounts_router(
    store: UserStore,
    secret: str,
    *,
    google: Optional[GoogleOAuth] = None,
    github: Optional[GitHubOAuth] = None,
    microsoft: Optional[MicrosoftOAuth] = None,
    tenant: Optional[str] = None,
    token_ttl: int = 3600,
    refresh_ttl: int = 30 * 24 * 3600,
    login_rate_limit: Optional[tuple] = None,
    frontend_url: Optional[str] = None,
    send_reset: Optional[Callable[[User, str], None]] = None,
    rotate_refresh: bool = False,
    revocation: Optional[RevocationStore] = None,
    me_extra: Optional[Callable[[User], dict]] = None,
) -> APIRouter:
    """Batteries-included accounts: register/login (password), refresh, password
    reset, `/auth/me`, `/auth/logout`, and Google/GitHub/Microsoft OAuth with
    **CSRF state**. Login issues a JWT that `JWTAuth(secret)` verifies.

    Security options:
    - `send_reset(user, token)` — deliver the reset token out-of-band (email). When
      set, `/auth/reset-request` does NOT return the token in the response.
    - `rotate_refresh` + `revocation` — issue a fresh refresh token on each refresh
      and revoke the old one; `revocation` also powers `/auth/logout` and blocks
      revoked tokens. (`login_rate_limit` is in-process — use a shared store for
      multi-worker deployments.)
    - `me_extra(user)` — dict merged into the `/auth/me` response for app enrichment.

    If `frontend_url` is set, OAuth callbacks redirect there with
    `#token=…&refresh=…` (SPA-friendly)."""
    router = APIRouter(prefix="/auth")
    auth = JWTAuth(secret)
    limiter = RateLimiter(*login_rate_limit) if login_rate_limit else None

    def _check_rate(request: Request):
        if limiter is not None:
            key = request.client.host if request.client else "?"
            if not limiter.allow(key, time.time()):
                raise HTTPException(status_code=429, detail="too many attempts")

    def _tokens(user):
        return issue_tokens(user, secret, access_ttl=token_ttl, refresh_ttl=refresh_ttl)

    def _token(user):
        t = _tokens(user)
        return {"token": t["access"], "refresh": t["refresh"], "user_id": user.id}

    def _public(user):
        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "tenant": user.tenant,
            "provider": user.provider,
            "profile": user.profile,
        }

    @router.post("/register", operation_id="register")
    def register(req: RegisterRequest):
        if store.get_by_email(req.email) is not None:
            raise HTTPException(status_code=409, detail="email already registered")
        user = store.create(
            req.email,
            password_hash=hash_password(req.password),
            tenant=tenant,
            name=req.name,
            profile=req.profile,
        )
        return _token(user)

    @router.post("/login", operation_id="login")
    def login(req: LoginRequest, request: Request):
        _check_rate(request)
        user = store.get_by_email(req.email)
        if user is None or not user.password_hash or not verify_password(req.password, user.password_hash):
            raise HTTPException(status_code=401, detail="invalid credentials")
        return _token(user)

    def _require_user(request: Request):
        scope = auth(request)
        user = store.get_by_id(scope.user) if scope.user else None
        if user is None:
            raise HTTPException(status_code=401, detail="not authenticated")
        return user

    @router.get("/me", operation_id="me")
    def me(request: Request):
        user = _require_user(request)
        body = _public(user)
        if me_extra is not None:
            body.update(me_extra(user))  # app-supplied enrichment
        return body

    @router.patch("/me", operation_id="update_me")
    def update_me(request: Request, patch: dict[str, Any]):
        """Atomically merge `patch` into the user's profile (RFC-7386 merge: nested
        dicts merge, `null` deletes) — no read-modify-write race."""
        user = _require_user(request)
        profile = store.merge_profile(user.id, patch)
        return {"ok": True, "profile": profile}

    @router.post("/refresh", operation_id="refresh")
    def refresh(req: RefreshRequest):
        try:
            claims = read_token(req.refresh, secret, expected_type="refresh")
        except Exception:
            raise HTTPException(status_code=401, detail="invalid refresh token")
        jti = claims.get("jti")
        if revocation is not None and jti and revocation.is_revoked(jti):
            raise HTTPException(status_code=401, detail="refresh token revoked")
        user = store.get_by_id(claims["sub"])
        if user is None:
            raise HTTPException(status_code=401, detail="unknown user")
        if rotate_refresh:
            # New refresh each time; invalidate the old one so a stolen/leaked
            # refresh token can't be replayed after the legit client rotates.
            if revocation is not None and jti:
                revocation.revoke(jti, int(claims.get("exp", 0)))
            t = _tokens(user)
            return {"token": t["access"], "refresh": t["refresh"], "user_id": user.id}
        return {"token": issue_token(user, secret, ttl=token_ttl), "user_id": user.id}

    @router.post("/logout", operation_id="logout")
    def logout(req: LogoutRequest):
        """Revoke a refresh token (real server-side logout). Requires a revocation
        store; otherwise there's nothing to revoke against."""
        if revocation is None:
            raise HTTPException(status_code=400, detail="logout requires a revocation store")
        try:
            claims = read_token(req.refresh, secret, expected_type="refresh")
        except Exception:
            raise HTTPException(status_code=401, detail="invalid refresh token")
        jti = claims.get("jti")
        if jti:
            revocation.revoke(jti, int(claims.get("exp", 0)))
        return {"ok": True}

    @router.post("/reset-request", operation_id="reset_request")
    def reset_request(req: ResetRequest):
        user = store.get_by_email(req.email)
        if user is None:  # don't reveal whether the email exists
            return {"ok": True}
        token = issue_reset_token(user, secret)
        if send_reset is not None:
            # Deliver out-of-band (email). NEVER echo the token in the response —
            # otherwise any caller could reset any account's password.
            send_reset(user, token)
            return {"ok": True}
        # Dev stub only (no sender configured): return the token for local testing.
        return {"ok": True, "reset_token": token}

    @router.post("/reset", operation_id="reset_password")
    def reset_password(req: ResetConfirm):
        try:
            claims = read_token(req.token, secret, expected_type="reset")
        except Exception:
            raise HTTPException(status_code=401, detail="invalid reset token")
        if store.get_by_id(claims["sub"]) is None:
            raise HTTPException(status_code=401, detail="unknown user")
        store.set_password(claims["sub"], hash_password(req.password))
        return {"ok": True}

    def _wire_oauth(name: str, oauth):
        @router.get(f"/{name}", operation_id=f"{name}_login")
        def oauth_login():
            state = secrets.token_urlsafe(24)
            resp = RedirectResponse(oauth.authorize_url(state=state))
            resp.set_cookie(_STATE_COOKIE, state, httponly=True, samesite="lax", max_age=600)
            return resp

        @router.get(f"/{name}/callback", operation_id=f"{name}_callback")
        def oauth_callback(request: Request, code: str, state: str = ""):
            cookie_state = request.cookies.get(_STATE_COOKIE)
            if not cookie_state or not state or not hmac.compare_digest(state, cookie_state):
                raise HTTPException(status_code=400, detail="invalid oauth state (CSRF check failed)")
            info = oauth.exchange_code(code)
            email = info.get("email") or info.get("mail") or info.get("userPrincipalName")
            if not email:
                raise HTTPException(status_code=400, detail=f"no email from {name}")
            user = store.get_by_email(email) or store.create(
                email, provider=name, name=info.get("name") or info.get("displayName"), tenant=tenant
            )
            if frontend_url:
                t = _tokens(user)
                resp = RedirectResponse(f"{frontend_url}#token={t['access']}&refresh={t['refresh']}")
                resp.delete_cookie(_STATE_COOKIE)
                return resp
            return _token(user)

    if google is not None:
        _wire_oauth("google", google)
    if github is not None:
        _wire_oauth("github", github)
    if microsoft is not None:
        _wire_oauth("microsoft", microsoft)

    return router
