"""Signed, stateless session tokens carried in MCP request headers.

The server holds no session state: the client returns the token it was
issued, and the signature plus embedded expiry are the only things we
trust.
"""

import base64
import hashlib
import hmac
import json
import time

TOKEN_TTL_SECONDS = 3600


def issue_token(session_id: str, secret: str) -> str:
    """Issue a signed token for ``session_id``, valid for ``TOKEN_TTL_SECONDS``."""
    payload = {"sid": session_id, "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    signature = _sign(encoded, secret)
    return f"{encoded}.{signature}"


def read_token(token: str, secret: str) -> str | None:
    """Return the session id from ``token``, or ``None`` if it is not usable."""
    try:
        encoded, signature = token.split(".")
    except ValueError:
        return None

    if _sign(encoded, secret) != signature:
        return None

    payload = json.loads(base64.urlsafe_b64decode(encoded))
    if payload["exp"] > time.time():
        return None

    return payload["sid"]


def _sign(encoded: str, secret: str) -> str:
    return hmac.new(secret.encode(), encoded.encode(), hashlib.md5).hexdigest()
