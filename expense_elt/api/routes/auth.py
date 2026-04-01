"""Auth routes — Google sign-in, session management."""

from __future__ import annotations

import os

from fastapi import APIRouter, Request, Response, HTTPException

from api.auth import (
    ALLOWED_EMAIL,
    GOOGLE_CLIENT_ID,
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    create_session_token,
    decode_session_token,
    verify_google_token,
)
from api.schemas import AuthUserResponse, GoogleAuthRequest
from api.dependencies import limiter

_is_production = os.environ.get("ENV", "").lower() == "production"

router = APIRouter()


@router.post("/auth/google", response_model=AuthUserResponse)
@limiter.limit("10/minute")
def google_login(request: Request, body: GoogleAuthRequest, response: Response):
    """Verify Google id_token, check email, set session cookie."""
    idinfo = verify_google_token(body.credential)

    email = idinfo.get("email", "").lower()
    role = "owner"
    permission = "full"

    if email == ALLOWED_EMAIL.lower():
        role = "owner"
        permission = "full"
    else:
        # Check if email is an authorized accountant
        from staging.database import get_connection, initialize_db
        initialize_db()
        con = get_connection()
        try:
            row = con.execute(
                "SELECT permission FROM authorized_users WHERE email = ? AND status = 'active'",
                [email],
            ).fetchone()
        finally:
            con.close()
        if not row:
            raise HTTPException(403, "This Google account is not authorized.")
        role = "accountant"
        permission = row[0]
        # Update last_login
        con = get_connection()
        try:
            con.execute(
                "UPDATE authorized_users SET last_login = CURRENT_TIMESTAMP WHERE email = ?",
                [email],
            )
            con.commit()
        finally:
            con.close()

    token = create_session_token(idinfo, role=role)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=_is_production,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
        path="/",
    )
    return AuthUserResponse(
        email=email,
        name=idinfo.get("name", ""),
        picture=idinfo.get("picture", ""),
        role=role,
        permission=permission,
    )


@router.get("/auth/me", response_model=AuthUserResponse)
def get_me(request: Request):
    """Return current user from session cookie, or 401."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(401, "Not authenticated.")
    claims = decode_session_token(token)
    role = claims.get("role", "owner")
    permission = "full"
    if role == "accountant":
        from staging.database import get_connection, initialize_db
        initialize_db()
        con = get_connection()
        try:
            row = con.execute(
                "SELECT permission, status FROM authorized_users WHERE email = ?",
                [claims.get("email", "")],
            ).fetchone()
        finally:
            con.close()
        if not row or row[1] != "active":
            raise HTTPException(403, "Account has been revoked.")
        permission = row[0]
    return AuthUserResponse(
        email=claims.get("email", ""),
        name=claims.get("name", ""),
        picture=claims.get("picture", ""),
        role=role,
        permission=permission,
    )


@router.post("/auth/logout")
def logout(response: Response):
    """Clear the session cookie."""
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"success": True}


@router.get("/auth/client-id")
def get_client_id():
    """Return the Google Client ID for frontend GIS initialization."""
    return {"client_id": GOOGLE_CLIENT_ID}
