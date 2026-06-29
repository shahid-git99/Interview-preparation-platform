"""
Auth routes — /auth/signup, /auth/login
"""

from fastapi import APIRouter, HTTPException, status
from bson import ObjectId
from datetime import datetime

from config.database import get_db
from models.schemas import SignupRequest, LoginRequest, AuthResponse, UserOut
from utils.auth_utils import hash_password, verify_password, create_token

router = APIRouter()


def _user_out(doc: dict) -> UserOut:
    return UserOut(
        id               = str(doc["_id"]),
        first_name       = doc["first_name"],
        last_name        = doc["last_name"],
        email            = doc["email"],
        profile_complete = doc.get("profile_complete", False),
    )


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest):
    db = get_db()

    # bcrypt hard limit is 72 bytes
    if len(body.password.encode("utf-8")) > 72:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is too long. Please use a password under 72 characters.",
        )

    # Check duplicate
    existing = await db.users.find_one({"email": body.email.lower()})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    doc = {
        "first_name":       body.first_name.strip(),
        "last_name":        body.last_name.strip(),
        "email":            body.email.lower().strip(),
        "password_hash":    hash_password(body.password),
        "profile_complete": False,
        "created_at":       datetime.utcnow(),
    }
    result = await db.users.insert_one(doc)
    doc["_id"] = result.inserted_id

    token = create_token({"user_id": str(result.inserted_id)})
    return AuthResponse(access_token=token, user=_user_out(doc))


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest):
    db = get_db()

    # bcrypt hard limit is 72 bytes
    if len(body.password.encode("utf-8")) > 72:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is too long. Please use a password under 72 characters.",
        )

    user = await db.users.find_one({"email": body.email.lower()})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = create_token({"user_id": str(user["_id"])})
    return AuthResponse(access_token=token, user=_user_out(user))
