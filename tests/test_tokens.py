# tests/test_tokens.py — direct unit tests for relio/accounts/tokens.py.
import pytest

pytest.importorskip("jwt")

from relio.accounts.store import User  # noqa: E402
from relio.accounts.tokens import (  # noqa: E402
    issue_reset_token,
    issue_token,
    issue_tokens,
    read_token,
)


def _user():
    return User(id="u1", email="a@b.com", tenant="acme")


def test_issue_token_round_trips_claims():
    secret = "s3cret"
    tok = issue_token(_user(), secret, ttl=3600)
    claims = read_token(tok, secret)
    assert claims["sub"] == "u1"
    assert claims["email"] == "a@b.com"
    assert claims["tenant"] == "acme"


def test_issue_tokens_returns_access_and_refresh_with_jti():
    pair = issue_tokens(_user(), "s")
    assert set(pair) == {"access", "refresh"}
    refresh = read_token(pair["refresh"], "s", expected_type="refresh")
    assert refresh["jti"]  # unique id enables rotation/revocation


def test_read_token_rejects_wrong_type():
    reset = issue_reset_token(_user(), "s")
    # a reset token must not be accepted where a refresh token is expected
    with pytest.raises(Exception):
        read_token(reset, "s", expected_type="refresh")


def test_read_token_rejects_bad_secret():
    tok = issue_token(_user(), "right")
    with pytest.raises(Exception):
        read_token(tok, "wrong")
