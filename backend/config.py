"""
Application configuration, constants, priority conventions, and compatibility matrix.
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

# Priority Conventions (Rule 7)
# 1 = Highest Urgency (Emergency / Safety Critical)
# 5 = Lowest Urgency (Routine / Deferrable)
PRIORITY_HIGHEST = 1
PRIORITY_HIGH = 2
PRIORITY_MEDIUM = 3
PRIORITY_LOW = 4
PRIORITY_LOWEST = 5
PRIORITY_MIN = 1
PRIORITY_MAX = 5

PRIORITY_LABELS = {
    1: "P1 - Critical Safety / Emergency",
    2: "P2 - High Operational Urgency",
    3: "P3 - Standard Periodic Maintenance",
    4: "P4 - Preventative Inspection",
    5: "P5 - Routine / Deferrable"
}

# Compatibility Matrix (Configurable, Section 5)
# Tracks department compatibility for joint bundling within a shared maintenance block
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
