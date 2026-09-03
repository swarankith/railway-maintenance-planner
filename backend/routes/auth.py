"""
Authentication API Endpoints:
- POST /api/v1/auth/login
- GET /api/v1/auth/me
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import DBUser, LoginRequest, TokenResponse, UserOut
from backend.auth import verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Validates username and password.
    Returns JWT access token with user details and assigned role.
    """
    user = db.query(DBUser).filter(DBUser.username == payload.username.strip()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
        department=user.department
    )

    user_out = UserOut.model_validate(user)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=user_out
    )


@router.get("/me", response_model=UserOut)
def get_my_profile(current_user: DBUser = Depends(get_current_user)):
    """Returns currently authenticated user profile."""
    return UserOut.model_validate(current_user)
