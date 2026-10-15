from pydantic import BaseModel, Field

from loan_application.schemas.customer_schemas import CustomerIn


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class RegisterIn(CustomerIn):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=8, max_length=128)


class RegisterOut(BaseModel):
    username: str
    customer_id: int