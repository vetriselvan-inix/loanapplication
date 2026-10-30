from helpers import login_headers, make_customer, make_user


def test_me_for_a_customer_shows_their_customer_id(client, db_session):
    customer = make_customer(db_session)
    user = make_user(db_session, customer)

    r = client.get("/auth/me", headers=login_headers(client, user.username))

    assert r.status_code == 200, r.text
    assert r.json() == {
        "username": user.username,
        "role": "CUSTOMER",
        "customer_id": customer.id,
    }


def test_me_for_an_officer_has_no_customer_id(client, officer, officer_headers):
    r = client.get("/auth/me", headers=officer_headers)

    assert r.status_code == 200, r.text
    assert r.json() == {
        "username": officer.username,
        "role": "OFFICER",
        "customer_id": None,
    }


def test_me_needs_a_login(client):
    assert client.get("/auth/me").status_code == 401
    assert (
        client.get("/auth/me", headers={"Authorization": "Bearer nonsense"}).status_code
        == 401
    )


def test_me_never_returns_the_password_hash(client, db_session):
    user = make_user(db_session, make_customer(db_session))

    body = client.get("/auth/me", headers=login_headers(client, user.username)).json()

    assert "password" not in str(body).lower()
    assert set(body) == {"username", "role", "customer_id"}
