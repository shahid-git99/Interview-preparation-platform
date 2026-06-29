"""
Auth utilities — JWT tokens + bcrypt password hashing
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

SECRET_KEY  = os.getenv("SECRET_KEY", "prepiq-super-secret-change-in-prod-2025")
ALGORITHM   = "HS256"
TOKEN_EXPIRE_DAYS = 30

pwd_ctx  = CryptContext(schemes=["bcrypt"], deprecated="auto", truncate_error=False)
bearer   = HTTPBearer()


def _truncate(password: str) -> str:
    """Truncate to 72 bytes — bcrypt hard limit."""
    encoded = password.encode("utf-8")
    return encoded[:72].decode("utf-8", errors="ignore")


def hash_password(password: str) -> str:
    return pwd_ctx.hash(_truncate(password))


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(_truncate(plain), hashed)


def create_token(data: dict, expire_days: int = TOKEN_EXPIRE_DAYS) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(days=expire_days)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer)
):
    """FastAPI dependency — resolves Bearer token to user_id string."""
    token = credentials.credentials
    payload = decode_token(token)
    if not payload or "user_id" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )
    return payload["user_id"]
