from datetime import datetime, timedelta, timezone
import secrets
from sqlalchemy.orm import Session
from .models import SessionToken

SESSION_TTL_MINUTES = 30

def create_session(db: Session, user_id: int) -> SessionToken:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    row = SessionToken(
        id=secrets.token_hex(32),
        user_id=user_id,
        created_at=now,
        expires_at=now + timedelta(minutes=SESSION_TTL_MINUTES),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

def get_session(db: Session, token: str | None) -> SessionToken | None:
    if not token:
        return None
    row = db.get(SessionToken, token)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if not row or row.expires_at <= now:
        if row:
            db.delete(row)
            db.commit()
        return None
    return row

def delete_session(db: Session, token: str | None) -> None:
    row = db.get(SessionToken, token) if token else None
    if row:
        db.delete(row)
        db.commit()
