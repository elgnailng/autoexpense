"""Accountant management routes — owner only."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.auth import ALLOWED_EMAIL
from api.dependencies import get_db, require_pipeline_idle
from api.schemas import (
    AccountantResponse,
    InviteAccountantRequest,
    UpdateAccountantRequest,
)

router = APIRouter()


@router.get("/accountants", response_model=list[AccountantResponse])
def list_accountants(con=Depends(get_db)):
    """List all invited accountants."""
    rows = con.execute(
        "SELECT email, role, permission, status, invited_by, invited_at, last_login "
        "FROM authorized_users ORDER BY invited_at DESC"
    ).fetchall()
    return [
        AccountantResponse(
            email=r[0],
            role=r[1],
            permission=r[2],
            status=r[3],
            invited_by=r[4],
            invited_at=str(r[5]) if r[5] else None,
            last_login=str(r[6]) if r[6] else None,
        )
        for r in rows
    ]


@router.post("/accountants", response_model=AccountantResponse, status_code=201)
def invite_accountant(
    body: InviteAccountantRequest,
    con=Depends(get_db),
    _idle=Depends(require_pipeline_idle),
):
    """Invite an accountant by email."""
    email = body.email.strip().lower()
    if email == ALLOWED_EMAIL.lower():
        raise HTTPException(400, "Cannot invite the owner as an accountant.")

    # Check if already exists
    existing = con.execute(
        "SELECT status FROM authorized_users WHERE email = ?", [email]
    ).fetchone()
    if existing:
        if existing[0] == "active":
            raise HTTPException(409, "Accountant already exists and is active.")
        # Re-activate revoked accountant
        con.execute(
            "UPDATE authorized_users SET status = 'active', permission = ? WHERE email = ?",
            [body.permission, email],
        )
        con.commit()
    else:
        con.execute(
            "INSERT INTO authorized_users (email, role, permission, invited_by) VALUES (?, 'accountant', ?, ?)",
            [email, body.permission, ALLOWED_EMAIL],
        )
        con.commit()

    row = con.execute(
        "SELECT email, role, permission, status, invited_by, invited_at, last_login "
        "FROM authorized_users WHERE email = ?",
        [email],
    ).fetchone()
    return AccountantResponse(
        email=row[0],
        role=row[1],
        permission=row[2],
        status=row[3],
        invited_by=row[4],
        invited_at=str(row[5]) if row[5] else None,
        last_login=str(row[6]) if row[6] else None,
    )


@router.put("/accountants/{email}", response_model=AccountantResponse)
def update_accountant(
    email: str,
    body: UpdateAccountantRequest,
    con=Depends(get_db),
    _idle=Depends(require_pipeline_idle),
):
    """Update an accountant's permission level."""
    email = email.strip().lower()
    row = con.execute(
        "SELECT status FROM authorized_users WHERE email = ?", [email]
    ).fetchone()
    if not row:
        raise HTTPException(404, "Accountant not found.")
    con.execute(
        "UPDATE authorized_users SET permission = ? WHERE email = ?",
        [body.permission, email],
    )
    con.commit()
    row = con.execute(
        "SELECT email, role, permission, status, invited_by, invited_at, last_login "
        "FROM authorized_users WHERE email = ?",
        [email],
    ).fetchone()
    return AccountantResponse(
        email=row[0],
        role=row[1],
        permission=row[2],
        status=row[3],
        invited_by=row[4],
        invited_at=str(row[5]) if row[5] else None,
        last_login=str(row[6]) if row[6] else None,
    )


@router.delete("/accountants/{email}")
def revoke_accountant(
    email: str,
    con=Depends(get_db),
    _idle=Depends(require_pipeline_idle),
):
    """Revoke an accountant's access (soft delete)."""
    email = email.strip().lower()
    row = con.execute(
        "SELECT status FROM authorized_users WHERE email = ?", [email]
    ).fetchone()
    if not row:
        raise HTTPException(404, "Accountant not found.")
    if row[0] == "revoked":
        raise HTTPException(400, "Accountant is already revoked.")
    con.execute(
        "UPDATE authorized_users SET status = 'revoked' WHERE email = ?", [email]
    )
    con.commit()
    return {"success": True, "message": f"Access revoked for {email}"}
