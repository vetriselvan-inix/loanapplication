from pydantic import BaseModel, Field

from loan_application.schemas.customer_schemas import CustomerIn


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class RegisterIn(CustomerIn):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=8, max_length=128)


class MeOut(BaseModel):
    username: str
    role: str
    customer_id: int | None


class RegisterOut(BaseModel):
    username: str
    customer_id: int

class ChangePasswordIn(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)