from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from loan_application.db import get_db
from loan_application.schemas.auth_schemas import TokenResponse,RegisterIn, RegisterOut
from loan_application.security import create_access_token
from loan_application.services import auth_services

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = auth_services.authenticate_user(db, form.username, form.password)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=create_access_token(user.id, user.role.value))




@router.post("/register", response_model=RegisterOut, status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    user, customer_id = auth_services.register_user(db, data)
    return RegisterOut(username=user.username, customer_id=customer_id)