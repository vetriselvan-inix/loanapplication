"""Reset a user's password from the command line.

Usage: uv run python -m loan_application.reset_password <username>
"""

import sys
from getpass import getpass

from loan_application.db import SessionLocal
from loan_application.repositories import user_repositories
from loan_application.security import hash_password

MIN_LENGTH = 8
MAX_LENGTH = 128


def reset_password(username: str, password: str) -> bool:
    """Set a new password for the user. Returns False if the user does not exist."""
    with SessionLocal() as db:
        user = user_repositories.get_by_username(db, username)
        if user is None:
            return False
        user.password_hash = hash_password(password)
        db.commit()
        return True


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("Usage: python -m loan_application.reset_password <username>")
        return 2
    username = argv[0]

    password = getpass(f"New password for {username}: ")
    if not MIN_LENGTH <= len(password) <= MAX_LENGTH:
        print(f"Password must be {MIN_LENGTH} to {MAX_LENGTH} characters")
        return 1
    if getpass("Confirm new password: ") != password:
        print("Passwords do not match")
        return 1

    if not reset_password(username, password):
        print(f"User '{username}' not found")
        return 1
    print(f"Password updated for {username}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
