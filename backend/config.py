"""
Application configuration, constants, priority conventions, and security settings.
Phase 2 Updates:
- Priority Convention: 1 = Emergency, 2 = High Urgent, 3 = Normal (Values > 3 flagged)
- Emergency Escalation Timeout: 15 Minutes
- JWT Authentication Settings
"""
import os
from zoneinfo import ZoneInfo
from typing import Dict, Set, Tuple

# Timezone standard: Indian Standard Time (IST, UTC+5:30)
APP_TIMEZONE = ZoneInfo("Asia/Kolkata")
TIMEZONE_STR = "Asia/Kolkata"

# Database Configuration (supports PostgreSQL, SQLite, etc. via env var)
raw_db_url = os.getenv("DATABASE_URL", "sqlite:///./railway_planner.db")
if raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)
DATABASE_URL = raw_db_url

# JWT Authentication Settings
JWT_SECRET = os.getenv("JWT_SECRET", "railway-block-planner-jwt-secret-key-2026-v2")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Priority Conventions (Phase 2)
# 1 = Emergency (Immediate / Safety Critical)
# 2 = High Urgent (Speed restriction removal / Urgent operational)
# 3 = Normal (Standard / Routine maintenance)
PRIORITY_EMERGENCY = 1
PRIORITY_HIGH_URGENT = 2
PRIORITY_NORMAL = 3
PRIORITY_MIN = 1
PRIORITY_MAX = 3

PRIORITY_LABELS = {
    1: "P1 - Emergency",
    2: "P2 - High Urgent",
    3: "P3 - Normal"
}

# Emergency Escalation Timeout (in minutes)
EMERGENCY_ESCALATION_MINUTES = 15

# Compatibility Matrix (Tracks department compatibility for joint bundling)
DEFAULT_COMPATIBILITY_PAIRS: Set[Tuple[str, str]] = {
    ("Engineering", "Electrical"),
    ("Electrical", "Engineering"),
    ("Engineering", "S&T"),
    ("S&T", "Engineering"),
    ("Electrical", "S&T"),
    ("S&T", "Electrical"),
    ("Engineering", "Engineering"),
    ("Electrical", "Electrical"),
    ("S&T", "S&T"),
}

def is_department_pair_compatible(dept1: str, dept2: str) -> bool:
    """
    Check if two departments are safely compatible to share a maintenance block window.
    Live train movements are NEVER compatible with any maintenance block.
    """
    d1 = dept1.strip()
    d2 = dept2.strip()
    return (d1, d2) in DEFAULT_COMPATIBILITY_PAIRS or (d2, d1) in DEFAULT_COMPATIBILITY_PAIRS
