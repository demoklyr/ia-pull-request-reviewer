"""Webhook signature verification (GitHub HMAC-SHA256).

GitHub signs every webhook payload with your configured secret and sends
the signature in the `X-Hub-Signature-256` header. Verifying it proves the
request really came from GitHub (or from someone who knows your secret),
not from a random third party hitting your public URL.

Docs: https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries
"""

import hashlib
import hmac


def verify_github_signature(payload_body: bytes, signature_header: str | None, secret: str) -> bool:
    """Verify the `X-Hub-Signature-256` header GitHub sends with webhooks.

    Returns True if the signature is valid.

    If `secret` is empty, verification is skipped entirely and this always
    returns True — this is intentional for local development, before a
    webhook secret has been configured. In production, always set
    GITHUB_WEBHOOK_SECRET so this check is actually enforced.
    """
    if not secret:
        return True

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected_signature = "sha256=" + hmac.new(
        key=secret.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    # Constant-time comparison: prevents a timing attack that could let an
    # attacker guess the correct signature one character at a time by
    # measuring how long the comparison takes.
    return hmac.compare_digest(expected_signature, signature_header)
