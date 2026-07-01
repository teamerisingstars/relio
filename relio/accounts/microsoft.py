# relio/accounts/microsoft.py
from __future__ import annotations

from typing import Callable, Optional
from urllib.parse import urlencode


class MicrosoftOAuth:
    """Microsoft (Azure AD / Entra) OAuth2 helper — same shape as GoogleOAuth.
    The token/userinfo exchange is injectable (`fetch`) for offline tests."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        *,
        tenant_id: str = "common",
        fetch: Optional[Callable[[str], dict]] = None,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.tenant_id = tenant_id
        self._fetch = fetch

    @property
    def auth_url(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/authorize"

    @property
    def token_url(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"

    def authorize_url(self, state: str = "") -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid email profile User.Read",
        }
        if state:
            params["state"] = state
        return f"{self.auth_url}?{urlencode(params)}"

    def exchange_code(self, code: str) -> dict:
        """Return the user's profile (`email`, `name`)."""
        if self._fetch is not None:
            return self._fetch(code)
        import httpx  # lazy: needs the `accounts` extra

        token = httpx.post(
            self.token_url,
            data={
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            },
        ).json()
        access = token["access_token"]
        return httpx.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {access}"},
        ).json()
