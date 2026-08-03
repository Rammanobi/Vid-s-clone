from __future__ import annotations


from fastapi import APIRouter, Depends, Form, HTTPException, status

from app.auth import authenticate_admin, create_access_token, get_current_user
from app.logging_setup import get_logger
from app.monitoring import auth_attempts_total

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token")
async def login(
    username: str = Form(...), password: str = Form(...)
) -> dict[str, str]:
    if authenticate_admin(username, password):
        token = create_access_token(username)
        auth_attempts_total.labels(result="success").inc()
        logger.info("admin_login_success", username=username)
        return {"access_token": token, "token_type": "bearer"}
    auth_attempts_total.labels(result="failure").inc()
    logger.warning("admin_login_failed", username=username)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
    )


@router.get("/me")
async def me(user: str = Depends(get_current_user)) -> dict[str, str]:
    return {"user": user}