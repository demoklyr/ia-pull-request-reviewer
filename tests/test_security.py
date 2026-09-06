"""Tests for verify_github_signature."""

import hashlib
import hmac

from ai_code_reviewer.api.security import verify_github_signature

SECRET = "my-webhook-secret"
BODY = b'{"action": "opened"}'


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_valid_signature_is_accepted():
    signature = _sign(BODY, SECRET)

    assert verify_github_signature(BODY, signature, SECRET) is True


def test_signature_signed_with_wrong_secret_is_rejected():
    signature = _sign(BODY, "a-different-secret")

    assert verify_github_signature(BODY, signature, SECRET) is False


def test_tampered_body_is_rejected():
    signature = _sign(BODY, SECRET)
    tampered_body = b'{"action": "closed"}'

    assert verify_github_signature(tampered_body, signature, SECRET) is False


def test_missing_signature_header_is_rejected_when_secret_is_configured():
    assert verify_github_signature(BODY, None, SECRET) is False


def test_signature_without_sha256_prefix_is_rejected():
    assert verify_github_signature(BODY, "deadbeef", SECRET) is False


def test_verification_is_skipped_when_no_secret_is_configured():
    # No GITHUB_WEBHOOK_SECRET set (empty string) -> always accepted.
    # This matches local development before a secret has been configured.
    assert verify_github_signature(BODY, None, "") is True
    assert verify_github_signature(BODY, "sha256=garbage", "") is True
