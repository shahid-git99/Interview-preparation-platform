"""
Profile routes — /profile/setup (POST), /profile/me (GET)
"""

import json
import os
import shutil
import PyPDF2
import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from typing import Optional
from bson import ObjectId
from datetime import datetime

from config.database import get_db
from models.schemas import ProfileOut
from utils.auth_utils import get_current_user

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads", "resumes")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _extract_pdf_text(file_bytes: bytes) -> str:
    """Extract text from PDF resume bytes."""
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text.strip()[:4000]  # cap at 4k chars for prompt safety
    except Exception:
        return ""


@router.post("/setup", status_code=status.HTTP_200_OK)
async def setup_profile(
    college:          str         = Form(...),
    college_city:     str         = Form(""),
    degree_level:     str         = Form(...),
    field_of_study:   str         = Form(...),
    grad_year:        int         = Form(...),
    current_status:   str         = Form(...),
    domains:          str         = Form(...),   # JSON string list
    experience_years: float       = Form(...),
    current_role:     str         = Form(""),
    resume:           Optional[UploadFile] = File(None),
    user_id:          str         = Depends(get_current_user),
):
    db = get_db()

    # Parse domains JSON
    try:
        domains_list = json.loads(domains)
    except Exception:
        raise HTTPException(400, "Invalid domains format.")

    # Handle resume upload
    resume_filename = None
    resume_text     = ""
    if resume and resume.filename:
        ext = os.path.splitext(resume.filename)[1].lower()
        if ext not in [".pdf", ".docx"]:
            raise HTTPException(400, "Resume must be a PDF or DOCX file.")
        safe_name = f"{user_id}{ext}"
        save_path = os.path.join(UPLOAD_DIR, safe_name)
        file_bytes = await resume.read()
        with open(save_path, "wb") as f:
            f.write(file_bytes)
        resume_filename = resume.filename
        if ext == ".pdf":
            resume_text = _extract_pdf_text(file_bytes)

    profile_doc = {
        "user_id":          user_id,
        "college":          college,
        "college_city":     college_city,
        "degree_level":     degree_level,
        "field_of_study":   field_of_study,
        "grad_year":        grad_year,
        "current_status":   current_status,
        "domains":          domains_list,
        "experience_years": experience_years,
        "current_role":     current_role,
        "resume_filename":  resume_filename,
        "resume_text":      resume_text,
        "updated_at":       datetime.utcnow(),
    }

    # Upsert profile
    await db.profiles.update_one(
        {"user_id": user_id},
        {"$set": profile_doc},
        upsert=True,
    )

    # Mark user profile complete
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"profile_complete": True}},
    )

    return {"message": "Profile saved successfully."}


@router.get("/me", response_model=ProfileOut)
async def get_profile(user_id: str = Depends(get_current_user)):
    db = get_db()
    profile = await db.profiles.find_one({"user_id": user_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Please complete profile setup.")

    # Merge user name fields
    user = await db.users.find_one({"_id": ObjectId(user_id)})

    return ProfileOut(
        user_id          = user_id,
        college          = profile.get("college"),
        college_city     = profile.get("college_city"),
        degree_level     = profile.get("degree_level"),
        field_of_study   = profile.get("field_of_study"),
        grad_year        = profile.get("grad_year"),
        current_status   = profile.get("current_status"),
        domains          = profile.get("domains", []),
        experience_years = profile.get("experience_years"),
        current_role     = profile.get("current_role"),
        resume_filename  = profile.get("resume_filename"),
        resume_text      = profile.get("resume_text"),
    )
