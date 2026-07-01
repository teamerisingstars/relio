# relio/accounts/google.py
from __future__ import annotations

from typing import Callable, Optional
from urllib.parse import urlencode


class GoogleOAuth:
    """Google OAuth2 (authorization-code) helper.

    The token/userinfo exchange is injectable via `fetch` so it's testable
    offline; in production it uses httpx to call Google.
    """

    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        *,
        fetch: Optional[Callable[[str], dict]] = None,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self._fetch = fetch

    def authorize_url(self, state: str = "") -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
        }
        if state:
            params["state"] = state
        return f"{self.AUTH_URL}?{urlencode(params)}"

    def exchange_code(self, code: str) -> dict:
        """Exchange an auth code for the user's profile (`email`, `name`, `sub`)."""
        if self._fetch is not None:
            return self._fetch(code)
        import httpx  # lazy: needs the `accounts` extra

        token = httpx.post(
            self.TOKEN_URL,
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
            self.USERINFO_URL, headers={"Authorization": f"Bearer {access}"}
        ).json()
