from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app import config
from app.schemas import TokenResponse
from app.security import authenticate, create_access_token, get_current_user
from app.services.users import User

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends()):
    if not config.PASSWORD_LOGIN_ENABLED:
        raise HTTPException(status_code=403, detail="Password sign-in is turned off. Use single sign-on.")
    user = authenticate(form.username, form.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"email": user.email, "tenant_id": user.tenant_id, "level": user.level, "is_admin": user.is_admin}
