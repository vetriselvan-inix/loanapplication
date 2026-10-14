import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from helpers import login_headers, make_customer, make_user
from loan_application.db import get_db
from loan_application.main import app
from loan_application.tables import Base, UserRole

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def _enable_foreign_keys(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


TestingSession = sessionmaker(bind=engine)


@pytest.fixture()
def db_session():
    Base.metadata.create_all(engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def db(db_session):
    return db_session


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture()
def officer(db_session):
    return make_user(db_session, role=UserRole.OFFICER)


@pytest.fixture()
def officer_headers(client, officer):
    return login_headers(client, officer.username)


@pytest.fixture()
def alice(db_session):
    return make_customer(db_session)


@pytest.fixture()
def bob(db_session):
    return make_customer(db_session)


@pytest.fixture()
def alice_headers(client, db_session, alice):
    return login_headers(client, make_user(db_session, alice).username)