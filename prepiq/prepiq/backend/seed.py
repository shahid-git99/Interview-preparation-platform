"""
seed.py — Optional seed script
Run once to insert reference data into MongoDB:
    python seed.py

Creates:
  - domains collection with supported interview domains
  - question_types collection with category definitions
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME   = os.getenv("DB_NAME", "prepiq")

DOMAINS = [
    {"slug": "software-engineering",   "label": "Software Engineering",   "icon": "💻",
     "description": "Data structures, algorithms, system design, coding best practices.",
     "difficulty_levels": ["Fresher", "Junior", "Mid-level", "Senior"]},

    {"slug": "data-science-ml",        "label": "Data Science & ML",      "icon": "📈",
     "description": "Statistics, machine learning, deep learning, data pipelines.",
     "difficulty_levels": ["Fresher", "Junior", "Mid-level", "Senior"]},

    {"slug": "ui-ux-design",           "label": "UI/UX Design",           "icon": "🎨",
     "description": "User research, wireframing, Figma, accessibility, design systems.",
     "difficulty_levels": ["Fresher", "Junior", "Mid-level", "Senior"]},

    {"slug": "digital-marketing",      "label": "Digital Marketing",      "icon": "📣",
     "description": "SEO, paid ads, content strategy, analytics, social media.",
     "difficulty_levels": ["Fresher", "Junior", "Mid-level", "Senior"]},

    {"slug": "finance-banking",        "label": "Finance & Banking",      "icon": "💰",
     "description": "Financial analysis, accounting, investment banking, risk management.",
     "difficulty_levels": ["Fresher", "Junior", "Mid-level", "Senior"]},

    {"slug": "civil-engineering",      "label": "Civil Engineering",      "icon": "🏗️",
     "description": "Structural analysis, project management, AutoCAD, site supervision.",
     "difficulty_levels": ["Fresher", "Junior", "Mid-level", "Senior"]},

    {"slug": "electrical-engineering", "label": "Electrical Engineering", "icon": "⚡",
     "description": "Circuit design, power systems, embedded systems, VLSI.",
     "difficulty_levels": ["Fresher", "Junior", "Mid-level", "Senior"]},

    {"slug": "biotech-life-sciences",  "label": "Biotech & Life Sciences","icon": "🧬",
     "description": "Molecular biology, clinical trials, regulatory, lab techniques.",
     "difficulty_levels": ["Fresher", "Junior", "Mid-level", "Senior"]},

    {"slug": "product-management",     "label": "Product Management",     "icon": "📦",
     "description": "Product strategy, roadmaps, user stories, metrics, stakeholder mgmt.",
     "difficulty_levels": ["Fresher", "Junior", "Mid-level", "Senior"]},

    {"slug": "cybersecurity",          "label": "Cybersecurity",          "icon": "🔐",
     "description": "Network security, ethical hacking, SIEM, compliance, threat modelling.",
     "difficulty_levels": ["Fresher", "Junior", "Mid-level", "Senior"]},

    {"slug": "cloud-devops",           "label": "Cloud & DevOps",         "icon": "☁️",
     "description": "AWS/GCP/Azure, CI/CD, Docker, Kubernetes, infrastructure as code.",
     "difficulty_levels": ["Fresher", "Junior", "Mid-level", "Senior"]},

    {"slug": "hr-people-ops",          "label": "HR & People Ops",        "icon": "📋",
     "description": "Recruitment, HRIS, performance management, L&D, labour law.",
     "difficulty_levels": ["Fresher", "Junior", "Mid-level", "Senior"]},
]

QUESTION_TYPES = [
    {"type": "Technical",   "description": "Tests domain knowledge and technical skills."},
    {"type": "Behavioural", "description": "Past behaviour using STAR method."},
    {"type": "Situational", "description": "Hypothetical scenarios and problem solving."},
    {"type": "HR",          "description": "Motivation, culture fit, career goals."},
]


async def seed():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]

    print(f"Seeding database: {DB_NAME}")

    # Domains
    await db.domains.drop()
    for d in DOMAINS:
        d["created_at"] = datetime.utcnow()
    await db.domains.insert_many(DOMAINS)
    print(f"  ✅ Inserted {len(DOMAINS)} domains")

    # Question types
    await db.question_types.drop()
    await db.question_types.insert_many(QUESTION_TYPES)
    print(f"  ✅ Inserted {len(QUESTION_TYPES)} question types")

    # Indexes
    await db.users.create_index("email", unique=True)
    await db.interview_sessions.create_index("user_id")
    await db.interview_sessions.create_index("completed_at")
    await db.profiles.create_index("user_id", unique=True)
    print("  ✅ Indexes created")

    client.close()
    print("\nSeed complete! 🌱")


if __name__ == "__main__":
    asyncio.run(seed())
