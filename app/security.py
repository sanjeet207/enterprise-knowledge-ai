import datetime as dt
import uuid
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app import config
from app.services import users
from app.services.users import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


_DUMMY_HASH = hash_password("not-a-real-password")


def authenticate(email: str, password: str) -> Optional[User]:
    found = users.get_with_password_hash(email)
    if found is None or not found[1]:
        verify_password(password, _DUMMY_HASH)
        return None
    user, password_hash = found
    if not verify_password(password, password_hash) or not user.is_active:
        return None
    return user


def create_access_token(user_id: str) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + dt.timedelta(minutes=config.ACCESS_TOKEN_MINUTES),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        user_id = str(uuid.UUID(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise credentials_error
    user = users.get_by_id(user_id)
    if user is None or not user.is_active:
        raise credentials_error
    return user


def require_level(minimum: int):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.level < minimum:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return dependency
