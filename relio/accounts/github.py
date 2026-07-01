# relio/accounts/github.py
from __future__ import annotations

from typing import Callable, Optional
from urllib.parse import urlencode


class GitHubOAuth:
    """GitHub OAuth2 helper — same shape as `GoogleOAuth`. The token/userinfo
    exchange is injectable (`fetch`) so it's testable offline."""

    AUTH_URL = "https://github.com/login/oauth/authorize"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    USER_URL = "https://api.github.com/user"

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
            "scope": "read:user user:email",
        }
        if state:
            params["state"] = state
        return f"{self.AUTH_URL}?{urlencode(params)}"

    def exchange_code(self, code: str) -> dict:
        """Return the user's profile (`email`, `name`)."""
        if self._fetch is not None:
            return self._fetch(code)
        import httpx  # lazy: needs the `accounts` extra

        token = httpx.post(
            self.TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
            },
        ).json()
        access = token["access_token"]
        return httpx.get(
            self.USER_URL,
            headers={"Authorization": f"Bearer {access}", "Accept": "application/vnd.github+json"},
        ).json()
