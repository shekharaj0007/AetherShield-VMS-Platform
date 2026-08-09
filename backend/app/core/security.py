from datetime import datetime, timedelta, timezone
from typing import Optional, Any
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
settings = get_settings()

ROLE_PERMISSIONS = {
    "admin": {
        "cameras:read", "cameras:write", "cameras:delete",
        "events:read", "events:write", "events:manage",
        "zones:read", "zones:write",
        "recordings:read", "recordings:write",
        "users:manage", "reports:export", "analytics:read",
        "incidents:manage", "system:admin",
    },
    "operator": {
        "cameras:read", "cameras:write",
        "events:read", "events:write", "events:manage",
        "zones:read", "zones:write",
        "recordings:read", "recordings:write",
        "reports:export", "analytics:read",
        "incidents:manage",
    },
    "viewer": {
        "cameras:read", "events:read", "zones:read",
        "recordings:read", "analytics:read",
    },
}


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    from app.models import User

    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def require_permission(permission: str):
    def checker(user=Depends(get_current_user)):
        perms = ROLE_PERMISSIONS.get(user.role, set())
        if permission not in perms and user.role != "admin":
            raise HTTPException(status_code=403, detail=f"Missing permission: {permission}")
        return user

    return checker
