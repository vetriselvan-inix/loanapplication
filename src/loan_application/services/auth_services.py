from sqlalchemy.orm import Session

from loan_application.exceptions import ConflictError, InvalidInputError
from loan_application.repositories import user_repositories
from loan_application.schemas.customer_schemas import CustomerIn
from loan_application.security import hash_password, verify_password
from loan_application.services import customer_services
from loan_application.services.transaction import transaction
from loan_application.tables import User, UserRole


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = user_repositories.get_by_username(db, username)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user

def register_user(db: Session, data) -> tuple[User, int]:
    if user_repositories.get_by_username(db, data.username):
        raise ConflictError("Username already taken")

    customer_data = CustomerIn(**data.model_dump(exclude={"username", "password"}))

    # Customer and user are one unit of work: both are saved or neither is.
    with transaction(db, "Username, email or phone already exists"):
        customer = customer_services.add_customer(db, customer_data)
        user = User(
            username=data.username,
            password_hash=hash_password(data.password),
            role=UserRole.CUSTOMER,
            customer_id=customer.id,
        )
        user_repositories.add(db, user)
    return user, customer.id

def change_password(db: Session, user: User, old_password: str, new_password: str) -> None:
    if not verify_password(old_password, user.password_hash):
        raise InvalidInputError("Old password is incorrect")
    if old_password == new_password:
        raise InvalidInputError("New password must be different from the old password")

    with transaction(db):
        user.password_hash = hash_password(new_password)