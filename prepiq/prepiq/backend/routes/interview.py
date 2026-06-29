"""
Interview routes
  POST /interview/start           → generate questions, create session
  POST /interview/submit          → save answers, trigger AI evaluation
  GET  /interview/feedback/{id}   → fetch feedback for a session
  GET  /interview/sessions        → list all sessions for current user
"""

from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from datetime import datetime
from typing import List

from config.database import get_db
from models.schemas import (
    StartSessionResponse,
    SubmitInterviewRequest,
    FeedbackResponse,
    AnswerFeedback,
    Question,
)
from utils.auth_utils import get_current_user
from utils.gemini_service import generate_questions, evaluate_answers

router = APIRouter()


# ── Helper: fetch merged profile dict for Gemini ──────────
async def _get_full_profile(user_id: str, db) -> dict:
    profile = await db.profiles.find_one({"user_id": user_id})
    user    = await db.users.find_one({"_id": ObjectId(user_id)})
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found. Please complete your profile setup first.",
        )
    merged = {**profile}
    if user:
        merged["first_name"] = user.get("first_name", "")
        merged["last_name"]  = user.get("last_name", "")
    return merged


# ── START SESSION ─────────────────────────────────────────
@router.post("/start", response_model=StartSessionResponse)
async def start_interview(user_id: str = Depends(get_current_user)):
    db = get_db()
    profile = await _get_full_profile(user_id, db)
    domain  = (profile.get("domains") or ["General"])[0]

    # Generate questions via Gemini
    raw_questions = await generate_questions(profile)

    # Persist session (status: in_progress, no answers yet)
    session_doc = {
        "user_id":    user_id,
        "domain":     domain,
        "questions":  raw_questions,
        "answers":    [],
        "status":     "in_progress",
        "started_at": datetime.utcnow(),
    }
    result = await db.interview_sessions.insert_one(session_doc)
    session_id = str(result.inserted_id)

    questions = [Question(id=q["id"], question=q["question"], type=q.get("type", "General"))
                 for q in raw_questions]

    return StartSessionResponse(
        session_id=session_id,
        questions=questions,
        domain=domain,
    )


# ── SUBMIT & EVALUATE ─────────────────────────────────────
@router.post("/submit")
async def submit_interview(
    body:    SubmitInterviewRequest,
    user_id: str = Depends(get_current_user),
):
    db = get_db()

    # Validate session
    try:
        oid = ObjectId(body.session_id)
    except Exception:
        raise HTTPException(400, "Invalid session ID.")

    session = await db.interview_sessions.find_one({"_id": oid, "user_id": user_id})
    if not session:
        raise HTTPException(404, "Interview session not found.")
    if session.get("status") == "completed":
        raise HTTPException(400, "This session has already been submitted.")

    profile   = await _get_full_profile(user_id, db)
    questions = session["questions"]

    # Build answers list aligned with questions
    answer_map = {a.question_id: a for a in body.answers}
    aligned_answers = []
    for q in questions:
        a = answer_map.get(q["id"])
        aligned_answers.append({
            "question_id": q["id"],
            "answer":      a.answer  if a else "",
            "skipped":     a.skipped if a else True,
        })

    # Evaluate with Gemini
    feedback_data = await evaluate_answers(profile, questions, aligned_answers)

    # Persist completed session
    completed_at = datetime.utcnow()
    await db.interview_sessions.update_one(
        {"_id": oid},
        {"$set": {
            "answers":          aligned_answers,
            "feedback":         feedback_data,
            "score":            feedback_data.get("overall_score", 0),
            "status":           "completed",
            "duration_seconds": body.duration_seconds,
            "question_count":   len(questions),
            "completed_at":     completed_at,
        }},
    )

    return {
        "message":    "Interview submitted and evaluated.",
        "session_id": body.session_id,
        "score":      feedback_data.get("overall_score", 0),
    }


# ── GET FEEDBACK ──────────────────────────────────────────
@router.get("/feedback/{session_id}", response_model=FeedbackResponse)
async def get_feedback(session_id: str, user_id: str = Depends(get_current_user)):
    db = get_db()

    try:
        oid = ObjectId(session_id)
    except Exception:
        raise HTTPException(400, "Invalid session ID.")

    session = await db.interview_sessions.find_one({"_id": oid, "user_id": user_id})
    if not session:
        raise HTTPException(404, "Session not found.")
    if session.get("status") != "completed":
        raise HTTPException(400, "This interview is not yet completed.")

    fb       = session.get("feedback", {})
    questions = session.get("questions", [])
    raw_ans   = session.get("answers", [])

    # Build per-answer feedback list
    fb_answers_raw = fb.get("answers", [])
    answer_feedbacks = []
    for i, q in enumerate(questions):
        raw = fb_answers_raw[i] if i < len(fb_answers_raw) else {}
        a   = raw_ans[i]        if i < len(raw_ans)        else {}
        answer_feedbacks.append(AnswerFeedback(
            question     = q.get("question", ""),
            type         = q.get("type", "General"),
            user_answer  = a.get("answer", ""),
            skipped      = a.get("skipped", False),
            score        = raw.get("score"),
            feedback     = raw.get("feedback"),
            ideal_points = raw.get("ideal_points"),
        ))

    return FeedbackResponse(
        session_id       = session_id,
        domain           = session.get("domain", "General"),
        overall_score    = fb.get("overall_score", 0),
        summary          = fb.get("summary", ""),
        category_scores  = fb.get("category_scores", {}),
        strengths        = fb.get("strengths", []),
        improvements     = fb.get("improvements", []),
        answers          = answer_feedbacks,
        question_count   = session.get("question_count", len(questions)),
        duration_seconds = session.get("duration_seconds", 0),
        completed_at     = session.get("completed_at", datetime.utcnow()),
    )


# ── LIST SESSIONS ─────────────────────────────────────────
@router.get("/sessions")
async def list_sessions(user_id: str = Depends(get_current_user)):
    db = get_db()

    cursor = db.interview_sessions.find(
        {"user_id": user_id, "status": "completed"},
        sort=[("completed_at", -1)],
        limit=20,
    )
    sessions = []
    async for s in cursor:
        sessions.append({
            "_id":              str(s["_id"]),
            "domain":           s.get("domain", "General"),
            "score":            s.get("score", 0),
            "question_count":   s.get("question_count", 0),
            "duration_minutes": round(s.get("duration_seconds", 0) / 60, 1),
            "completed_at":     s.get("completed_at", datetime.utcnow()).isoformat(),
        })
    return sessions
