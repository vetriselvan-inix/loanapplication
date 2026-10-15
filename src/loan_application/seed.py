from loan_application.config import settings
from loan_application.db import SessionLocal
from loan_application.repositories import user_repositories
from loan_application.security import hash_password
from loan_application.tables import User, UserRole


def main() -> None:
    username = settings.seed_officer_username
    password = settings.seed_officer_password
    if not username or not password:
        print("SEED_OFFICER_USERNAME/SEED_OFFICER_PASSWORD not set, skipping")
        return
    create_officer_user(username, password)


def create_customer_user(username: str, password: str, customer_id: int) -> None:
    with SessionLocal() as db:
        if user_repositories.get_by_username(db, username):
            print("User already exists")
            return
        db.add(
            User(
                username=username,
                password_hash=hash_password(password),
                role=UserRole.CUSTOMER,
                customer_id=customer_id,
            )
        )
        db.commit()
        print("Customer user created")

def create_officer_user(username: str, password: str) -> None:
    with SessionLocal() as db:
        if user_repositories.get_by_username(db, username):
            print("User already exists")
            return
        db.add(
            User(
                username=username,
                password_hash=hash_password(password),
                role=UserRole.OFFICER,
            )
        )
        db.commit()
        print("Officer created")

if __name__ == "__main__":
    main()