import pytest
from conftest import TestingSession
from helpers import make_user

from loan_application import reset_password as rp
from loan_application.security import verify_password


@pytest.fixture()
def user(db_session, monkeypatch):
    monkeypatch.setattr(rp, "SessionLocal", TestingSession)
    return make_user(db_session, username="officer")


def _prompts(monkeypatch, *answers):
    it = iter(answers)
    monkeypatch.setattr(rp, "getpass", lambda _prompt: next(it))


def _hash(db_session, user):
    db_session.expire_all()
    return db_session.get(type(user), user.id).password_hash


def test_resets_password(db_session, user, monkeypatch, capsys):
    _prompts(monkeypatch, "NewPass123", "NewPass123")
    assert rp.main(["officer"]) == 0
    assert verify_password("NewPass123", _hash(db_session, user))
    assert "Password updated for officer" in capsys.readouterr().out


def test_unknown_user(user, monkeypatch, capsys):
    _prompts(monkeypatch, "NewPass123", "NewPass123")
    assert rp.main(["nobody"]) == 1
    assert "not found" in capsys.readouterr().out


def test_mismatched_confirmation(db_session, user, monkeypatch, capsys):
    old = _hash(db_session, user)
    _prompts(monkeypatch, "NewPass123", "Different1")
    assert rp.main(["officer"]) == 1
    assert _hash(db_session, user) == old
    assert "do not match" in capsys.readouterr().out


def test_too_short(user, monkeypatch, capsys):
    _prompts(monkeypatch, "short")
    assert rp.main(["officer"]) == 1
    assert "8 to 128" in capsys.readouterr().out


def test_usage_without_username(capsys):
    assert rp.main([]) == 2
    assert "Usage" in capsys.readouterr().out
