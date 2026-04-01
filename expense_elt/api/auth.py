"""
auth.py — Google OAuth verification + session JWT management.

Env vars:
  GOOGLE_CLIENT_ID  — required for Google sign-in
  ALLOWED_EMAIL     — email allowed to sign in (required)
  SESSION_SECRET    — HMAC key for session JWTs (auto-generated if missing)
"""

from __future__ import annotations

import os
import secrets
import time
import logging

import jwt
from fastapi import HTTPException, Request
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

logger = logging.getLogger(__name__)

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
ALLOWED_EMAIL = os.environ.get("ALLOWED_EMAIL", "")
SESSION_COOKIE = "session"
SESSION_MAX_AGE = 24 * 60 * 60  # 24 hours

_session_secret: str | None = None


def _get_session_secret() -> str:
    global _session_secret
    if _session_secret is None:
        env_secret = os.environ.get("SESSION_SECRET", "")
        if env_secret:
            _session_secret = env_secret
        else:
            _session_secret = secrets.token_hex(32)
            logger.warning(
                "SESSION_SECRET not set — generated a random key. "
                "Sessions will not survive server restarts."
            )
    return _session_secret


def verify_google_token(token: str) -> dict:
    """Verify a Google id_token and return the claims dict.

    Raises HTTPException on invalid/expired tokens.
    """
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(500, "GOOGLE_CLIENT_ID environment variable is not set.")
    try:
        idinfo = id_token.verify_oauth2_token(
            token, google_requests.Request(), GOOGLE_CLIENT_ID
        )
        return idinfo
    except ValueError as e:
        raise HTTPException(401, f"Invalid Google token: {e}")


def create_session_token(user_info: dict, role: str = "owner") -> str:
    """Create an HS256 JWT for the session cookie."""
    now = int(time.time())
    payload = {
        "sub": user_info.get("sub", ""),
        "email": user_info.get("email", ""),
        "name": user_info.get("name", ""),
        "picture": user_info.get("picture", ""),
        "role": role,
        "iat": now,
        "exp": now + SESSION_MAX_AGE,
    }
    return jwt.encode(payload, _get_session_secret(), algorithm="HS256")


def decode_session_token(token: str) -> dict:
    """Decode and verify a session JWT. Returns claims or raises HTTPException."""
    try:
        return jwt.decode(token, _get_session_secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Session expired. Please sign in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid session token.")


def require_auth(request: Request) -> dict:
    """FastAPI dependency — validates session cookie, returns user claims or 401."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(401, "Not authenticated.")
    return decode_session_token(token)


def require_owner(request: Request) -> dict:
    """FastAPI dependency — validates session and requires owner role."""
    claims = require_auth(request)
    if claims.get("role") != "owner":
        raise HTTPException(403, "Owner access required.")
    return claims


def require_flag_permission(request: Request) -> dict:
    """FastAPI dependency — allows owners and any active accountant to flag."""
    claims = require_auth(request)
    if claims.get("role") == "owner":
        return claims
    # Any active accountant can flag
    from staging.database import get_connection, initialize_db
    initialize_db()
    con = get_connection()
    try:
        row = con.execute(
            "SELECT permission FROM authorized_users WHERE email = ? AND status = 'active'",
            [claims.get("email", "")],
        ).fetchone()
    finally:
        con.close()
    if not row:
        raise HTTPException(403, "Account not found or inactive.")
    return claims
