"""
Application configuration, constants, priority conventions, and catalog definitions.
Phase 2 Final (v6):
- Priority Convention: 1 = Emergency, 2 = High Urgent, 3 = Normal
- Emergency Escalation Timeout: 15 Minutes
- Category A and Category B definitions
- Incompatible Category A pairs & Rule C
- Clean PostgreSQL / SQLite connection string sanitization (pgbouncer stripped, sslmode handled)
"""
import os
import re
from zoneinfo import ZoneInfo
from typing import Dict, Set, Tuple

# Timezone standard: Indian Standard Time (IST, UTC+5:30)
APP_TIMEZONE = ZoneInfo("Asia/Kolkata")
TIMEZONE_STR = "Asia/Kolkata"

# Database Configuration (supports PostgreSQL, SQLite, etc. via env var)
raw_db_url = os.getenv("DATABASE_URL", "sqlite:///./railway_planner.db")
if raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)

# Clean pgbouncer parameters if present (SQLAlchemy cannot parse pgbouncer parameter)
if "pgbouncer=true" in raw_db_url:
    raw_db_url = raw_db_url.replace("?pgbouncer=true&", "?")
    raw_db_url = raw_db_url.replace("&pgbouncer=true", "")
    raw_db_url = raw_db_url.replace("?pgbouncer=true", "")

# Auto-append ?sslmode=require if postgres and sslmode not specified
if raw_db_url.startswith("postgresql://") and "sslmode=" not in raw_db_url:
    delimiter = "&" if "?" in raw_db_url else "?"
    raw_db_url = f"{raw_db_url}{delimiter}sslmode=require"

DATABASE_URL = raw_db_url

# Priority Conventions (Phase 2)
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

# Work Types Catalogs (Part A.1)
CATEGORY_A_CATALOG = [
    "Rail renewal/replacement",
    "Track/rail repair & welding",
    "Sleeper replacement",
    "Ballast work (tamping/screening)",
    "Points & crossing maintenance",
    "Point machine maintenance/repair",
    "Track circuit testing & calibration",
    "Trackside signal mast/aspect maintenance",
    "Signal cable laying/repair",
    "OHE replacement/repair",
    "OHE insulator/hardware replacement",
    "Feeder/catenary cable replacement",
    "Pantograph–OHE contact wire inspection",
]

CATEGORY_B_CATALOG = [
    "Bridge/tunnel routine inspection",
    "Track patrolling & vegetation/cess clearance",
    "Level crossing gate/interlocking maintenance",
    "Relay room/interlocking servicing",
    "Station equipment update",
    "Traction substation repair/maintenance",
    "Power distribution/feeder testing",
]

# 4 Incompatible Category A pairs (Part A.2)
INCOMPATIBLE_CAT_A_PAIRS = {
    (
        "rail renewal/replacement",
        "sleeper replacement",
    ),
    (
        "rail renewal/replacement",
        "ballast work (tamping/screening)",
    ),
    (
        "sleeper replacement",
        "ballast work (tamping/screening)",
    ),
    (
        "ohe replacement/repair",
        "feeder/catenary cable replacement",
    ),
}

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
    d1 = dept1.strip()
    d2 = dept2.strip()
    return (d1, d2) in DEFAULT_COMPATIBILITY_PAIRS or (d2, d1) in DEFAULT_COMPATIBILITY_PAIRS
