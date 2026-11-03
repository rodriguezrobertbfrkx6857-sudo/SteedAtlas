from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.user import User

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)
USER_ROLES = {"user", "operator", "admin"}
STAFF_ROLES = {"operator", "admin"}
ADMIN_ROLES = {"admin"}


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(data: dict, expires_delta: timedelta) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(user_id: str) -> str:
    return create_token(
        {"sub": user_id, "type": "access"},
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: str) -> str:
    return create_token(
        {"sub": user_id, "type": "refresh"},
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


def normalize_user_role(role: str | None) -> str:
    normalized = str(role or "user").strip().lower()
    if normalized in USER_ROLES:
        return normalized
    return "user"


def resolve_registration_role(phone: str | None) -> str:
    normalized_phone = str(phone or "").strip()
    if normalized_phone and normalized_phone in set(settings.ADMIN_BOOTSTRAP_PHONES):
        return "admin"
    if normalized_phone and normalized_phone in set(settings.OPERATOR_BOOTSTRAP_PHONES):
        return "operator"
    return "user"


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def get_optional_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if not token:
        return None
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None
    return db.query(User).filter(User.id == payload["sub"]).first()


def require_roles(*allowed_roles: str) -> Callable:
    normalized_roles = {normalize_user_role(role) for role in allowed_roles}

    async def dependency(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        user_role = normalize_user_role(getattr(user, "role", "user"))
        if user_role not in normalized_roles:
            from sqlalchemy import inspect
            if inspect(db.get_bind()).has_table("v2_events"):
                from app.v2.domain import emit
                emit(db, user.id, user.id, "AUTHORIZATION_DENIED", {"required_roles": sorted(normalized_roles)})
                db.commit()
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return dependency


async def get_current_staff_user(user: User = Depends(require_roles(*STAFF_ROLES))) -> User:
    return user


async def get_current_admin_user(user: User = Depends(require_roles(*ADMIN_ROLES))) -> User:
    return user
