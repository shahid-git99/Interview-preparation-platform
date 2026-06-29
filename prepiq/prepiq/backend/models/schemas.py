"""
PrepIQ — Pydantic models for request/response validation
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any
from datetime import datetime


# ── AUTH ──────────────────────────────────────────────────
class SignupRequest(BaseModel):
    first_name: str
    last_name:  str
    email:      EmailStr
    password:   str = Field(min_length=8)


class LoginRequest(BaseModel):
    email:    EmailStr
    password: str


class UserOut(BaseModel):
    id:               str
    first_name:       str
    last_name:        str
    email:            str
    profile_complete: bool = False


class AuthResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user:         UserOut


# ── PROFILE ───────────────────────────────────────────────
class ProfileOut(BaseModel):
    user_id:          str
    college:          Optional[str]
    college_city:     Optional[str]
    degree_level:     Optional[str]
    field_of_study:   Optional[str]
    grad_year:        Optional[int]
    current_status:   Optional[str]   # student | fresher | experienced
    domains:          List[str] = []
    experience_years: Optional[float]
    current_role:     Optional[str]
    resume_filename:  Optional[str]
    resume_text:      Optional[str]   # extracted text for AI context


# ── INTERVIEW ─────────────────────────────────────────────
class Question(BaseModel):
    id:       str
    question: str
    type:     str   # Technical | Behavioural | Situational | HR


class StartSessionResponse(BaseModel):
    session_id: str
    questions:  List[Question]
    domain:     str


class AnswerItem(BaseModel):
    question_id: str
    answer:      str
    skipped:     bool = False


class SubmitInterviewRequest(BaseModel):
    session_id:       str
    answers:          List[AnswerItem]
    duration_seconds: int


# ── FEEDBACK ──────────────────────────────────────────────
class AnswerFeedback(BaseModel):
    question:     str
    type:         str
    user_answer:  str
    skipped:      bool
    score:        Optional[int]
    feedback:     Optional[str]
    ideal_points: Optional[str]


class FeedbackResponse(BaseModel):
    session_id:      str
    domain:          str
    overall_score:   int
    summary:         str
    category_scores: dict
    strengths:       List[str]
    improvements:    List[str]
    answers:         List[AnswerFeedback]
    question_count:  int
    duration_seconds: int
    completed_at:    datetime
