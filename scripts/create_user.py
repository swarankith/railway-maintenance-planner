"""
CLI Script to create users directly in database.
Usage:
    python scripts/create_user.py --username <user> --password <pass> --role <Planner|Operations|Approver> [--dept <Engineering>]
    python scripts/create_user.py --init-defaults
"""
import sys
import os
import argparse

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import SessionLocal, init_db
from backend.models import DBUser, UserRoleEnum
from backend.auth import hash_password


def create_user(username, password, role="Planner", department="Engineering"):
    init_db()
    db = SessionLocal()
    try:
        existing = db.query(DBUser).filter(DBUser.username == username).first()
        if existing:
            print(f"[!] User '{username}' already exists. Updating password & role...")
            existing.password_hash = hash_password(password)
            existing.role = role
            existing.department = department
            db.commit()
            print(f"[OK] User '{username}' successfully updated!")
            return existing

        user = DBUser(
            username=username,
            password_hash=hash_password(password),
            role=role,
            department=department
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"[OK] User '{username}' ({role} - {department}) successfully created with ID: {user.id}")
        return user
    finally:
        db.close()


def init_default_users():
    """Initializes 3 standard demonstration user accounts."""
    default_users = [
        ("planner1", "planner123", "Planner", "Civil / Engineering"),
        ("ops1", "ops123", "Operations", "Train Operations"),
        ("approver1", "approver123", "Approver", "Chief Controller"),
    ]
    for u, p, r, d in default_users:
        create_user(u, p, r, d)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Railway Maintenance Planner User Management")
    parser.add_argument("--username", "-u", type=str, help="Username")
    parser.add_argument("--password", "-p", type=str, help="Password")
    parser.add_argument("--role", "-r", type=str, choices=["Planner", "Operations", "Approver"], default="Planner", help="User Role")
    parser.add_argument("--dept", "-d", type=str, default="Engineering", help="Department")
    parser.add_argument("--init-defaults", action="store_true", help="Initialize standard default users (planner1, ops1, approver1)")

    args = parser.parse_args()

    if args.init_defaults or (not args.username and not args.password):
        print("Initializing default users...")
        init_default_users()
    else:
        if not args.username or not args.password:
            print("Error: Both --username and --password are required.")
            sys.exit(1)
        create_user(args.username, args.password, args.role, args.dept)
