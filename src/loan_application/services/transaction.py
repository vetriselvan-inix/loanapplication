from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from loan_application.exceptions import ConflictError


@contextmanager
def transaction(
    db: Session, conflict_message: str = "Conflict with existing data"
) -> Iterator[None]:
    """One unit of work: commit if the block succeeds, roll back if anything fails.

    Only top-level service functions open a transaction. Helpers and repositories
    called inside it may add/flush but never commit, so all their changes are
    saved together or not at all.
    """
    try:
        yield
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(conflict_message) from None
    except Exception:
        db.rollback()
        raise
