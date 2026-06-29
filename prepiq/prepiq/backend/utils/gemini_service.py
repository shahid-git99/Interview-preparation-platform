"""
Gemini AI service
- generate_questions()  → creates personalised interview questions
- evaluate_answers()    → scores answers and produces feedback report
"""

import os
import json
import re
import uuid
from typing import List, Optional

import google.generativeai as genai

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel("gemini-1.5-flash") if GEMINI_API_KEY else None

NUM_QUESTIONS = 10  # questions per interview


# ── Helpers ───────────────────────────────────────────────
def _clean_json(raw: str) -> str:
    """Strip markdown code fences if Gemini wraps in ```json ... ```"""
    raw = raw.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"^```\s*",     "", raw)
    raw = re.sub(r"\s*```$",     "", raw)
    return raw.strip()


def _build_profile_context(profile: dict) -> str:
    domains     = ", ".join(profile.get("domains") or ["General"])
    status      = profile.get("current_status", "fresher")
    exp         = profile.get("experience_years", 0)
    degree      = profile.get("degree_level", "")
    field       = profile.get("field_of_study", "")
    college     = profile.get("college", "")
    grad_year   = profile.get("grad_year", "")
    role        = profile.get("current_role", "")
    resume_text = profile.get("resume_text", "")

    ctx = f"""
Candidate Profile:
- Name: {profile.get('first_name', '')} {profile.get('last_name', '')}
- College: {college}
- Degree: {degree} in {field} (Class of {grad_year})
- Current status: {status}
- Years of experience: {exp}
- Current/Last role: {role or 'N/A'}
- Preferred domains: {domains}
"""
    if resume_text:
        # Limit resume text to avoid huge prompts
        ctx += f"\nResume excerpt:\n{resume_text[:2000]}\n"
    return ctx.strip()


# ── QUESTION GENERATION ───────────────────────────────────
async def generate_questions(profile: dict) -> List[dict]:
    """
    Returns a list of {id, question, type} dicts.
    Falls back to generic questions if Gemini is unavailable.
    """
    if not model:
        return _fallback_questions(profile)

    profile_ctx = _build_profile_context(profile)
    domains     = ", ".join(profile.get("domains") or ["General"])
    status      = profile.get("current_status", "fresher")
    exp         = profile.get("experience_years", 0)

    prompt = f"""
You are a senior recruiter conducting a mock interview for a candidate in the {domains} field.

{profile_ctx}

Generate exactly {NUM_QUESTIONS} interview questions tailored specifically to this candidate.

Guidelines:
- Mix question types: Technical (domain knowledge), Behavioural (past experience/STAR), 
  Situational (hypothetical scenarios), and HR (motivation, goals, culture fit).
- Adjust difficulty to match the candidate's experience level ({status}, {exp} years).
- Reference their specific domain(s): {domains}
- If resume excerpt is provided, reference specific skills or experiences from it.
- Freshers/students: more fundamentals + hypotheticals; Experienced: deeper architecture, leadership, trade-offs.

Return ONLY a valid JSON array. No extra text. No markdown fences.
Format:
[
  {{"id": "q1", "question": "...", "type": "Technical"}},
  {{"id": "q2", "question": "...", "type": "Behavioural"}},
  ...
]
"""
    try:
        response = model.generate_content(prompt)
        cleaned  = _clean_json(response.text)
        questions = json.loads(cleaned)
        # Ensure UUIDs
        for q in questions:
            if not q.get("id"):
                q["id"] = str(uuid.uuid4())[:8]
        return questions[:NUM_QUESTIONS]
    except Exception as e:
        print(f"[Gemini] Question generation error: {e}")
        return _fallback_questions(profile)


def _fallback_questions(profile: dict) -> List[dict]:
    """Used when Gemini key is missing or API fails."""
    domain = (profile.get("domains") or ["General"])[0]
    base = [
        {"id": "q01", "type": "HR",          "question": f"Tell me about yourself and why you're interested in {domain}."},
        {"id": "q02", "type": "Behavioural", "question": "Describe a challenging project you worked on and how you handled it."},
        {"id": "q03", "type": "Technical",   "question": f"What are the core concepts a professional in {domain} must know?"},
        {"id": "q04", "type": "Situational", "question": "How would you approach learning a completely new technology in 2 weeks?"},
        {"id": "q05", "type": "Behavioural", "question": "Tell me about a time you had a conflict with a teammate and how you resolved it."},
        {"id": "q06", "type": "Technical",   "question": f"Walk me through a {domain} problem you're proud of solving."},
        {"id": "q07", "type": "Situational", "question": "Your project deadline is in 24 hours and a critical bug appears. What do you do?"},
        {"id": "q08", "type": "HR",          "question": "Where do you see yourself professionally in 3–5 years?"},
        {"id": "q09", "type": "Technical",   "question": f"What recent trends in {domain} excite you the most and why?"},
        {"id": "q10", "type": "HR",          "question": "Do you have any questions for us about the role or company?"},
    ]
    return base


# ── ANSWER EVALUATION ─────────────────────────────────────
async def evaluate_answers(
    profile: dict,
    questions: List[dict],
    answers: List[dict],
) -> dict:
    """
    Evaluates answers and returns a full feedback report dict.
    """
    if not model:
        return _fallback_feedback(questions, answers)

    profile_ctx = _build_profile_context(profile)
    domain      = (profile.get("domains") or ["General"])[0]

    # Build Q&A text for prompt
    qa_text = ""
    for i, (q, a) in enumerate(zip(questions, answers)):
        ans_text = a.get("answer", "").strip() or "(no answer / skipped)"
        qa_text += f"\nQ{i+1} [{q.get('type','General')}]: {q.get('question','')}\nA{i+1}: {ans_text}\n"

    prompt = f"""
You are an expert interviewer and career coach evaluating a mock interview.

{profile_ctx}

Here are the interview questions and the candidate's answers:
{qa_text}

Evaluate the answers and produce a detailed feedback report.

Return ONLY valid JSON (no markdown, no extra text) with this exact structure:
{{
  "overall_score": <integer 0-100>,
  "summary": "<2-3 sentence overall assessment>",
  "category_scores": {{
    "Technical Knowledge": <0-100>,
    "Communication": <0-100>,
    "Problem Solving": <0-100>,
    "Domain Expertise": <0-100>
  }},
  "strengths": ["<strength 1>", "<strength 2>", "<strength 3>"],
  "improvements": ["<area 1>", "<area 2>", "<area 3>"],
  "answers": [
    {{
      "question": "<question text>",
      "type": "<question type>",
      "user_answer": "<candidate answer>",
      "skipped": <true|false>,
      "score": <0-100 or null if skipped>,
      "feedback": "<specific constructive feedback>",
      "ideal_points": "<what a strong answer would include>"
    }}
  ]
}}
"""
    try:
        response = model.generate_content(prompt)
        cleaned  = _clean_json(response.text)
        feedback = json.loads(cleaned)
        return feedback
    except Exception as e:
        print(f"[Gemini] Evaluation error: {e}")
        return _fallback_feedback(questions, answers)


def _fallback_feedback(questions: List[dict], answers: List[dict]) -> dict:
    """Minimal feedback used when Gemini is unavailable."""
    answered = sum(1 for a in answers if not a.get("skipped") and a.get("answer","").strip())
    score = max(0, min(100, int((answered / max(len(questions), 1)) * 70) + 10))

    return {
        "overall_score": score,
        "summary": (
            "Your answers have been recorded. Configure your Gemini API key "
            "to unlock AI-generated feedback."
        ),
        "category_scores": {
            "Technical Knowledge": score,
            "Communication":       score,
            "Problem Solving":     score,
            "Domain Expertise":    score,
        },
        "strengths":    ["Completed the interview", "Provided answers to most questions"],
        "improvements": ["Add Gemini API key for detailed improvement suggestions"],
        "answers": [
            {
                "question":     q.get("question", ""),
                "type":         q.get("type", "General"),
                "user_answer":  a.get("answer", ""),
                "skipped":      a.get("skipped", False),
                "score":        None if a.get("skipped") else 60,
                "feedback":     "Gemini API not configured — add GEMINI_API_KEY to .env",
                "ideal_points": "A strong answer would provide specific examples, use structured thinking, and demonstrate domain knowledge.",
            }
            for q, a in zip(questions, answers)
        ],
    }
