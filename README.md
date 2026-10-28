# Loan Application Service

A small backend service for a lending company. It lets you **register customers**, **accept loan applications**, **decide eligibility automatically**, and **report a customer's loan position** through a REST API secured with **JWT login and role-based access**.

I built this as part of a REST API assessment, and I used it to learn how a real backend is put together: a web framework, a real database running in Docker, versioned migrations, layered code (routers, services, repositories), authentication, automated tests and CI.

---

## What it does

- Lets a customer **self-register** (customer profile + login in one step) and log in to get a JWT.
- Supports two roles: **OFFICER** (staff, sees and manages everything) and **CUSTOMER** (sees and acts only on their own data).
- Validates customers properly (name, email, phone, date of birth, monthly income).
- Accepts loan applications and **approves or rejects them instantly** using eligibility rules. Approved loans get an interest rate and an EMI calculated on the server; rejected loans always carry a reason.
- Reports a customer's loan position: totals, EMI-to-income ratio and a risk band.
- Lists loans with **pagination** and status filtering.
- Returns consistent JSON errors and never leaks a stack trace to the client.

## Tech stack

| Tool | Why it is here |
|---|---|
| **Python 3.12+** | The language |
| **FastAPI** | The web framework. It also gives an interactive API page at `/docs` |
| **Uvicorn** | The server that runs the FastAPI app |
| **SQLAlchemy 2.x** | The ORM: database tables as Python classes |
| **PostgreSQL 16 (Docker)** | The database |
| **psycopg 3** | The driver that connects Python to PostgreSQL |
| **Alembic** | Database migrations. Tables are created by migrations, never by app code |
| **Pydantic + email-validator** | Request validation and response shapes |
| **pydantic-settings** | Reading settings and secrets from the environment |
| **PyJWT** | Signing and verifying access tokens |
| **pwdlib (Argon2)** | Password hashing |
| **python-multipart** | Parsing the login form |
| **pytest + httpx + pytest-cov** | Automated tests and coverage |
| **Ruff + Black** | Linting and formatting |
| **uv** | Package and virtual environment manager |

## Project structure

```
loan_application/
├── src/loan_application/
│   ├── main.py                 # Creates the FastAPI app, mounts routers, /health, error handlers
│   ├── config.py               # Settings loaded from .env (pydantic-settings)
│   ├── db.py                   # Database engine and per-request session (get_db)
│   ├── tables.py               # SQLAlchemy models: customers, loans, users
│   ├── security.py             # Password hashing and JWT create/decode
│   ├── exceptions.py           # Domain errors: NotFound, InvalidInput, Conflict
│   ├── logging_context.py      # Log format that includes the current user id
│   ├── seed.py                 # Creates the initial officer account
│   ├── routers/                # HTTP layer: URLs, status codes, auth dependencies
│   │   ├── auth_routers.py     #   /auth/...
│   │   ├── customer_routers.py #   /customers/...
│   │   └── loan_routers.py     #   /loans/... and /api/loans
│   ├── schemas/                # Pydantic request/response models and validation
│   ├── dependencies/auth.py    # get_current_user, require_roles, request logging
│   ├── services/               # Business rules
│   │   ├── auth_services.py    #   login, register, change password
│   │   ├── customer_services.py
│   │   ├── loan_services.py    #   eligibility, interest rate, EMI, summary, pagination
│   │   ├── access.py           #   "can this user see this customer?"
│   │   └── transaction.py      #   commit/rollback unit of work
│   └── repositories/           # The only layer that queries the database
├── alembic/                    # Database migrations (versions/ holds each change)
├── alembic.ini
├── docs/adr/                   # Architecture decision records
├── tests/                      # Automated tests (pytest, in-memory SQLite)
├── postman/                    # Postman collection for trying the APIs
├── .postman/                   # Postman workspace metadata
├── Dockerfile                  # API image
├── docker-entrypoint.sh        # Runs migrations and seeding, then starts the server
├── docker-compose.yml          # API + PostgreSQL
├── .env.example                # Template for .env (copy and fill in)
├── .github/workflows/ci.yml    # CI pipeline
├── pyproject.toml              # Project metadata, dependencies, pytest/coverage/ruff settings
├── uv.lock                     # Exact locked dependency versions
└── .python-version             # Python version used by uv
```

### How a request flows through the layers

```
Client (Postman, /docs, a browser)
   -> routers/          receives the request; schemas/ validate the body
   -> dependencies/     checks the JWT, loads the user, checks the role
   -> services/         applies business rules, opens a transaction
   -> repositories/     the only place that reads and writes the database
   -> tables.py         describes the tables
   -> db.py             session and engine
   -> PostgreSQL in Docker
```

Routers stay thin, business logic lives in services, and all SQL lives in repositories, so each layer is easy to read and test.

## Getting started

### What you need first

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (it must be running)
- Git
- For local development without Docker: [Python 3.12+](https://www.python.org/downloads/) and [uv](https://docs.astral.sh/uv/)

### Option A: run everything in Docker (API + PostgreSQL)

```bash
git clone https://github.com/vetriselvan-inix/loanapplication.git
cd loanapplication
cp .env.example .env
```

Open `.env` and replace every `change-me` value. Generate a JWT secret with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Then start the stack:

```bash
docker compose up -d --build
```

The `api` container waits for the database to be healthy, runs `alembic upgrade head`, creates the officer user from `SEED_OFFICER_USERNAME` / `SEED_OFFICER_PASSWORD` (skipped if unset or if it already exists), and starts the server on port `8000`.

- Health check: http://127.0.0.1:8000/health
- Interactive API docs: http://127.0.0.1:8000/docs

### Option B: run the API locally, database in Docker

```bash
uv sync
cp .env.example .env          # then fill in the values as above
docker compose up -d db
uv run alembic upgrade head
uv run python -m loan_application.seed
uv run uvicorn loan_application.main:app --reload
```

`DATABASE_URL` in `.env` points at `localhost`, which is right for this option. Inside compose, the `api` service overrides it to use the `db` host.

If `/health` returns `{"status":"ok","database":"connected"}`, everything is wired up correctly.

## Configuration

All settings and secrets come from environment variables (loaded from `.env` by `pydantic-settings`). `.env` is git-ignored; `.env.example` is the template.

| Variable | Used by | Purpose |
|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `db` container | Database credentials (applied only when the `pgdata` volume is first created) |
| `DATABASE_URL` | API, Alembic | SQLAlchemy connection URL |
| `JWT_SECRET_KEY` | API | Signs access tokens (required) |
| `JWT_ALGORITHM` | API | Optional, defaults to `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | API | Optional, defaults to `30` |
| `SEED_OFFICER_USERNAME` / `SEED_OFFICER_PASSWORD` | Seed script | Optional initial officer account |

## Authentication and roles

1. **Register** with `POST /auth/register`, or let the seed script create an officer.
2. **Log in** with `POST /auth/login` (form fields `username` and `password`). The response is:
   ```json
   { "access_token": "<jwt>", "token_type": "bearer" }
   ```
3. Send the token on every other request:
   ```
   Authorization: Bearer <jwt>
   ```

In Swagger (`/docs`), click **Authorize** and enter your username and password.

The token is signed with HS256, carries the user id and role, and expires after 30 minutes. On each request the server verifies the token and reloads the user; a missing, expired or invalid token, or an inactive user, gets `401`. See [docs/adr/0001-jwt-vs-session-auth.md](docs/adr/0001-jwt-vs-session-auth.md) for why JWT was chosen over server-side sessions.

| Role | Can do |
|---|---|
| `OFFICER` | Everything: create, view, update and delete any customer; view and delete any loan; see all loans in the paginated list; change any customer's income or date of birth |
| `CUSTOMER` | Only their own data: view and update their profile (but **not** income or date of birth), apply for loans for themselves, view their own loans and summary |

Accessing another customer's data, or calling an officer-only endpoint, returns `403`.

## API overview

All JSON requests and responses use `Content-Type: application/json` (except login, which is a form).

### Health and auth

| Method | Endpoint | Auth | What it does |
|---|---|---|---|
| `GET` | `/health` | Public | Confirms the app is running and can reach the database |
| `POST` | `/auth/register` | Public | Creates a customer and a CUSTOMER login together; returns `username` and `customer_id` |
| `POST` | `/auth/login` | Public | Returns a JWT access token |
| `POST` | `/auth/change-password` | Logged in | Changes the password (`old_password`, `new_password`) |

### Customers

| Method | Endpoint | Auth | What it does |
|---|---|---|---|
| `POST` | `/customers/` | Officer | Creates a customer |
| `GET` | `/customers/{customer_id}` | Officer or that customer | Fetches one customer |
| `PUT` | `/customers/{customer_id}` | Officer or that customer | Updates a customer (customers cannot change income or date of birth) |
| `DELETE` | `/customers/{customer_id}` | Officer | Deletes a customer (fails with `409` if they have loans) |
| `GET` | `/customers/{customer_id}/summary` | Officer or that customer | Loan position report |
| `GET` | `/customers/{customer_id}/loans?status=` | Officer or that customer | The customer's loans, newest first |

### Loans

| Method | Endpoint | Auth | What it does |
|---|---|---|---|
| `POST` | `/loans/apply` | Officer or that customer | Applies for a loan; it is approved or rejected immediately |
| `GET` | `/loans/{loan_id}` | Officer or the loan's customer | Fetches one loan |
| `GET` | `/loans/?customer_id=&status=` | Officer or that customer | A customer's loans, newest first |
| `DELETE` | `/loans/{loan_id}` | Officer | Deletes a loan |
| `GET` | `/api/loans?status=&page=&size=` | Logged in | Paginated loans: officers see all, customers see only their own |

`status` filters accept `APPROVED` or `REJECTED` (case-insensitive). For `/api/loans`, `page` starts at 1 and `size` is 1 to 100 (default 10).

### Example: register and log in

```bash
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
        "username": "ravi_k",
        "password": "StrongPass123",
        "name": "Ravi Kumar",
        "email": "ravi@example.com",
        "phone": "9876543210",
        "date_of_birth": "1998-04-12",
        "monthly_income": 45000
      }'

curl -X POST http://127.0.0.1:8000/auth/login \
  -d "username=ravi_k&password=StrongPass123"
```

### Example: apply for a loan

```bash
curl -X POST http://127.0.0.1:8000/loans/apply \
  -H "Authorization: Bearer <jwt>" \
  -H "Content-Type: application/json" \
  -d '{ "customer_id": 1, "amount": 200000, "tenure_months": 24 }'
```

Approved response (`201`):

```json
{
  "id": 1,
  "customer_id": 1,
  "amount": "200000.00",
  "tenure_months": 24,
  "interest_rate": "11.00",
  "emi": "9321.57",
  "status": "APPROVED",
  "rejection_reason": null,
  "applied_on": "2026-10-21"
}
```

### Example: paginated loan list

`GET /api/loans?status=APPROVED&page=1&size=10`

```json
{
  "items": [ { "id": 1, "status": "APPROVED", "...": "..." } ],
  "page": 1,
  "size": 10,
  "total": 25,
  "total_pages": 3,
  "has_next": true,
  "has_previous": false
}
```

## Business rules

### Loan eligibility

When a loan is applied for, the rules are checked in order. The first one that fails becomes the `rejection_reason` and the loan is saved as `REJECTED`:

1. The customer's age must be between **21 and 60**.
2. The amount must not exceed **20 × monthly income**.
3. The customer must have fewer than **2 approved loans**.

If every rule passes, the loan is saved as `APPROVED` with an interest rate and EMI.

### Interest rate by tenure

| Tenure (months) | 12 | 24 | 36 | 48 | 60 |
|---|---|---|---|---|---|
| Annual rate | 10% | 11% | 12% | 13% | 13% |

### EMI

```
r   = annual_rate / 12 / 100
EMI = P × r × (1 + r)^n / ((1 + r)^n − 1)
```

`P` is the amount and `n` the tenure in months. The result is rounded to 2 decimals (half-up).

### Customer summary

`GET /customers/{customer_id}/summary` returns the total, approved and rejected application counts, the total approved amount, the total monthly EMI of approved loans, and:

- `emi_to_income_ratio` = total monthly EMI ÷ monthly income × 100
- `risk_band`: `LOW` if the ratio is below 30, `MEDIUM` from 30 to 50, `HIGH` above 50

## Data model

### `customers`

| Column | Type | Rules |
|---|---|---|
| `id` | integer, auto-generated | Primary key |
| `name` | string | Required, at least 3 characters after trimming |
| `email` | string | Required, valid email, **unique** (stored lowercase on create) |
| `phone` | string | Exactly 10 digits, **unique** |
| `date_of_birth` | date | `YYYY-MM-DD`, must be in the past |
| `monthly_income` | decimal | Greater than 0 |

### `loans`

| Column | Type | Rules |
|---|---|---|
| `id` | integer, auto-generated | Primary key |
| `customer_id` | integer | Foreign key to `customers` |
| `amount` | decimal | Required, 10,000 to 5,000,000 |
| `tenure_months` | integer | Required, one of 12, 24, 36, 48, 60 |
| `interest_rate` | decimal | Set by the server for approved loans |
| `emi` | decimal | Calculated by the server for approved loans |
| `status` | string | `APPROVED` or `REJECTED` |
| `rejection_reason` | string | Only set when the loan is rejected |
| `applied_on` | date | Set by the database to the current date |

### `users`

| Column | Type | Rules |
|---|---|---|
| `id` | integer, auto-generated | Primary key |
| `username` | string | **Unique**, 3 to 50 letters, digits or underscores |
| `password_hash` | string | Argon2 hash (plain passwords are never stored) |
| `role` | enum | `OFFICER` or `CUSTOMER` |
| `customer_id` | integer, nullable | Links a CUSTOMER user to exactly one customer; empty for officers |
| `is_active` | boolean | Inactive users cannot log in |

One customer can have many loans and at most one user login.

## Transactions

Every write goes through `services/transaction.py`:

```python
with transaction(db, "message used if a unique constraint fails"):
    ...  # add / update / delete
```

The block commits if it succeeds and rolls back if anything fails. Only top-level service functions open a transaction; helpers inside it may add and flush but never commit. This is why registration saves the customer and the user **together or not at all**. A database unique or foreign key violation inside a transaction becomes a `409 CONFLICT` with a clear message.

## Error handling

Every error comes back as JSON in a predictable shape.

**Validation failure: `400 Bad Request`**, listing *all* failing fields, not just the first:

```json
{
  "error": "VALIDATION_FAILED",
  "message": "Invalid input",
  "details": [
    { "field": "email", "message": "value is not a valid email address: ..." },
    { "field": "phone", "message": "Phone number must be 10 digits" }
  ]
}
```

| Situation | Status | `error` |
|---|---|---|
| Invalid request body, query or path values | 400 | `VALIDATION_FAILED` |
| Business validation (e.g. bad status filter, wrong old password) | 400 | `VALIDATION_FAILED` |
| Missing or invalid token | 401 | `UNAUTHORIZED` |
| Not allowed for your role or customer | 403 | `FORBIDDEN` |
| Record not found | 404 | `NOT_FOUND` |
| Duplicate username, email or phone; deleting a customer with loans | 409 | `CONFLICT` |
| Database unavailable on `/health` | 503 | `SERVICE_UNAVAILABLE` |
| Anything unexpected | 500 | `INTERNAL_ERROR` |

Non-validation errors look like:

```json
{ "error": "NOT_FOUND", "message": "Customer with id 42 not found" }
```

A stack trace is never sent to the client.

## Logging

Every authenticated request is logged with the method, path and role, and each log line includes the current user id:

```
2026-10-21 10:15:02,123 INFO user=3 loan_application.dependencies.auth: POST /loans/apply role=CUSTOMER
```

## Database migrations

Tables are only ever created or changed through Alembic. `alembic/env.py` reads `DATABASE_URL` from settings and uses the models in `tables.py`.

```bash
# Create a new migration after changing tables.py
uv run alembic revision --autogenerate -m "describe the change"

# Apply all pending migrations
uv run alembic upgrade head

# Go back one step
uv run alembic downgrade -1
```

Always read the generated file in `alembic/versions/` before applying it. Never edit a migration that has already been applied; create a new one instead.

## Running the tests

```bash
uv run pytest --cov=loan_application
```

pytest is configured in `pyproject.toml` to look for tests in `tests/` and to import code from `src/`. Tests use an **in-memory SQLite** database (tables are built from the models) and override the `get_db` dependency, so PostgreSQL does not need to be running. Shared fixtures in `tests/conftest.py` provide an officer, customers and ready-made auth headers.

| Test file | Covers |
|---|---|
| `test_auth_api.py` | Login, register, change password |
| `test_customers_api.py` | Customer endpoints and access rules |
| `test_loans_api.py` | Loan endpoints and access rules |
| `test_loans_pagination.py` | `/api/loans` paging and filtering |
| `test_customer_services.py`, `test_loan_services.py` | Service-layer logic |
| `test_transaction.py` | Commit/rollback behaviour |
| `test_units.py` | EMI, age, risk band and other pure functions |
| `test_smoke.py` | Basic app wiring |

## Continuous integration

GitHub Actions (`.github/workflows/ci.yml`) runs on every pull request and on pushes to `main`:

- `ruff check .`
- `pytest` with a **90% coverage gate**
- `docker build` to make sure the image still builds

## Code quality

```bash
uv run ruff check .
uv run black .
```

## Trying the APIs in Postman

The `postman/` folder contains a collection with customer and loan requests. Start the server, log in with `POST /auth/login`, then send the requests against `http://127.0.0.1:8000` with the `Authorization: Bearer <jwt>` header.

## Useful Docker commands

```bash
docker compose up -d --build   # build and start the API and the database
docker compose up -d db        # start only the database
docker compose down            # stop everything (data is kept)
docker compose down -v         # stop it AND delete all data (use only on practice data)
docker compose logs api        # see API logs
docker compose logs db         # see database logs
```

To look inside the database:

```bash
docker exec -it <container-name> psql -U vetri -d loan_db
```

Find the container name with `docker ps`. Inside `psql`, `\dt` lists the tables and `SELECT * FROM customers;` shows the rows.

## Troubleshooting

| Problem | Likely cause and fix |
|---|---|
| `/health` returns `database unavailable` | The database is not running. Run `docker compose up -d` and check `docker ps` |
| `password authentication failed` | The password in `DATABASE_URL` does not match the one the database was created with. `POSTGRES_PASSWORD` only applies when the `pgdata` volume is first created, so either reset it with `ALTER USER` or run `docker compose down -v` and start again |
| Connection error with a strange host name | The password contains `@`, `:` or `/`, which breaks the connection URL. Use letters and numbers only |
| App fails to start with a settings error | `DATABASE_URL` or `JWT_SECRET_KEY` is missing from `.env` |
| Every request returns `401` | The token is missing, expired (30 minutes) or signed with a different `JWT_SECRET_KEY`. Log in again |
| `403 Insufficient permissions` | The endpoint is officer-only. Log in as the seeded officer |
| Alembic generates an empty migration | `alembic/env.py` is not importing `tables`, so Alembic cannot see the models |
| `ModuleNotFoundError: loan_application` | Run commands with `uv run`, and make sure `src/loan_application/__init__.py` exists |

## Authentication code walkthrough (file by file, line by line)

This section explains the authentication code I wrote after the loan and customer endpoints were finished and tested. Line numbers refer to the files as they are now.

### The big picture

```
REGISTER   POST /auth/register -> auth_routers.register -> auth_services.register_user
                                  -> saves a Customer + a User (password stored as an Argon2 hash)

LOGIN      POST /auth/login    -> auth_routers.login    -> auth_services.authenticate_user
                                  -> verify_password -> create_access_token -> JWT returned

EVERY      Authorization: Bearer <jwt>
OTHER      -> dependencies/auth.get_current_user: decode JWT -> load user -> 401 if bad
REQUEST    -> require_roles(...): 403 if the role is not allowed
```

Files involved, in the order a request meets them:

| # | File | Job |
|---|---|---|
| 1 | `config.py` | Holds the JWT secret, algorithm and expiry |
| 2 | `security.py` | Hashes/verifies passwords, creates/decodes JWTs |
| 3 | `tables.py` (`User`, `UserRole`) | The `users` table |
| 4 | `repositories/user_repositories.py` | The only code that queries `users` |
| 5 | `schemas/auth_schemas.py` | Shape and validation of auth requests/responses |
| 6 | `services/auth_services.py` | Business logic: authenticate, register, change password |
| 7 | `routers/auth_routers.py` | The three `/auth/...` URLs |
| 8 | `dependencies/auth.py` | `get_current_user`, `require_roles`, request logging |
| 9 | `seed.py` + `docker-entrypoint.sh` | Creates the first officer account on startup |
| 10 | `logging_context.py` | Puts the user id in every log line |
| 11 | `tests/test_auth_api.py` | Proves all of the above works |

---

### 1. `config.py`: where the secrets live

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
```
Imports the class that reads settings from environment variables / the `.env` file.

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```
Defines the settings class. `env_file=".env"` means "also read the `.env` file". `extra="ignore"` means unrelated variables in `.env` (like `POSTGRES_USER`) do not cause an error.

```python
    database_url: str
    jwt_secret_key: str
```
No default value, so they are **required**. If `JWT_SECRET_KEY` is missing the app refuses to start, so I can never run with an empty signing key by accident.

```python
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
```
Optional, with defaults: sign tokens with HS256 and let them live 30 minutes.

```python
    seed_officer_username: str | None = None
    seed_officer_password: str | None = None
```
Optional. If both are set, the seed script creates the first officer. `str | None` means "a string or nothing".

```python
settings = Settings()
```
Creates one shared settings object. Every other file does `from loan_application.config import settings`.

---

### 2. `security.py`: passwords and tokens

```python
from datetime import UTC, datetime, timedelta
import jwt
from pwdlib import PasswordHash
from loan_application.config import settings
```
`datetime`/`timedelta`/`UTC` are for token timestamps. `jwt` is PyJWT (signs and verifies tokens). `PasswordHash` is from pwdlib (Argon2 hashing). `settings` supplies the secret and expiry.

```python
_hasher = PasswordHash.recommended()
```
Builds one hasher using the library's recommended algorithm, **Argon2**. The leading `_` means "private to this file". Argon2 is deliberately slow and salted, so stolen hashes are very hard to crack, and the same password hashes differently each time.

```python
def hash_password(password: str) -> str:
    return _hasher.hash(password)
```
Turns a plain password into a hash string. This is what is stored in `users.password_hash`. The plain password is never saved.

```python
def verify_password(password: str, hashed: str) -> bool:
    return _hasher.verify(password, hashed)
```
Checks a typed password against a stored hash. Returns `True` or `False`. You cannot "decrypt" a hash; you can only hash again and compare.

```python
def create_access_token(user_id: int, role: str) -> str:
    now = datetime.now(UTC)
```
Builds a JWT for a user. `now` is the current time in UTC.

```python
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
```
The **claims** (data) inside the token:
- `sub` ("subject"): who the token is for. The JWT standard says it must be a string, hence `str(user_id)`.
- `role`: `OFFICER` or `CUSTOMER`, for convenience.
- `iat` ("issued at"): when it was created.
- `exp` ("expires"): `now + 30 minutes`. After this time the token is rejected automatically.

```python
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
```
Signs the payload with the secret and returns the compact `xxxxx.yyyyy.zzzzz` token string. The payload is **readable** by anyone (it is only base64), but it **cannot be changed** without the secret, because the signature would no longer match. So never put secrets in it.

```python
def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "sub"]},
    )
```
Verifies the signature and expiry, then returns the payload as a dict. It **raises** a `jwt.PyJWTError` subclass if the token is expired, tampered with, or signed with another key.
- `algorithms=[...]` pins the allowed algorithm, which blocks the classic "alg: none" attack.
- `require: ["exp", "sub"]` rejects tokens that have no expiry or no subject.

---

### 3. `tables.py`: the `users` table

```python
class UserRole(str, enum.Enum):
    OFFICER = "OFFICER"
    CUSTOMER = "CUSTOMER"
```
The only two allowed roles. Using an enum means a typo like `"ofiicer"` is impossible. Inheriting from `str` lets it be compared and serialised as plain text.

```python
class User(Base):
    __tablename__ = "users"
```
A SQLAlchemy model mapped to the `users` table.

| Line | Meaning |
|---|---|
| `id ... primary_key=True` | Unique row id (also the `sub` in the JWT) |
| `username ... String(50), unique=True, index=True` | At most 50 chars, no two users share one (the database enforces it), and indexed so login lookups are fast |
| `password_hash ... String(255)` | Room for the long Argon2 string |
| `role ... Enum(UserRole, name="user_role")` | Stored as a PostgreSQL enum type |
| `customer_id ... ForeignKey("customers.id"), unique=True, nullable=True` | Links a CUSTOMER login to its customer. `unique` means one customer has at most one login. `nullable` because officers have no customer |
| `is_active ... default=True` | Lets staff disable a login without deleting it |

---

### 4. `repositories/user_repositories.py`: database access only

```python
def get_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))
```
Runs `SELECT ... FROM users WHERE username = ...` and returns the user or `None`. Used by login, register and the seed script.

```python
def get_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)
```
Fetches by primary key (fast). Used on every authenticated request to turn the token's `sub` back into a user.

```python
def add(db: Session, user: User) -> None:
    db.add(user)
```
Stages a new user to be saved. It does **not** commit; the service decides when to commit (see Transactions above).

---

### 5. `schemas/auth_schemas.py`: request and response shapes

```python
from pydantic import BaseModel, Field
from loan_application.schemas.customer_schemas import CustomerIn
```
`BaseModel` gives automatic validation; `Field` adds rules. `CustomerIn` is reused so registration does not repeat the customer rules.

```python
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
```
What login returns: `{"access_token": "...", "token_type": "bearer"}`. `"bearer"` is what the OAuth2 standard (and Swagger's Authorize button) expects.

```python
class RegisterIn(CustomerIn):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=8, max_length=128)
```
Registration = everything a customer has (`name`, `email`, `phone`, `date_of_birth`, `monthly_income`, inherited from `CustomerIn`) **plus**:
- `username`: 3 to 50 characters, only letters, digits and `_`. The regex `^[A-Za-z0-9_]+$` means "from start to end, only these characters".
- `password`: at least 8 characters. The max of 128 stops someone sending a huge string to slow down the hasher.

There is **no `role` field on purpose**: a caller cannot choose to become an officer. If someone sends `"role": "OFFICER"` it is ignored (tested in `test_register_ignores_a_role_in_the_body`).

```python
class RegisterOut(BaseModel):
    username: str
    customer_id: int
```
What registration returns. The password and hash are never sent back.

```python
class ChangePasswordIn(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
```
The old password only needs to be non-empty (it is checked against the hash later); the new one must meet the 8-character rule.

---

### 6. `services/auth_services.py`: the business rules

#### `authenticate_user`

```python
def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = user_repositories.get_by_username(db, username)
```
Looks the user up by username.

```python
    if user is None or not user.is_active:
        return None
```
Unknown user or disabled account: fail.

```python
    if not verify_password(password, user.password_hash):
        return None
    return user
```
Wrong password: fail. Otherwise return the user. Every failure returns the same `None`, so the router can give one generic message and never reveal whether the username or the password was wrong.

#### `register_user`

```python
def register_user(db: Session, data) -> tuple[User, int]:
    if user_repositories.get_by_username(db, data.username):
        raise ConflictError("Username already taken")
```
Friendly early check. A duplicate username becomes `409 CONFLICT`.

```python
    customer_data = CustomerIn(**data.model_dump(exclude={"username", "password"}))
```
Takes the registration data, removes `username` and `password`, and rebuilds a plain `CustomerIn`. That is exactly what the existing `customer_services.add_customer` expects, so customer logic is reused, not copied.

```python
    with transaction(db, "Username, email or phone already exists"):
```
Opens **one unit of work**. Everything inside is committed together at the end, or rolled back if anything fails. The message is used if the database reports a unique-constraint clash (for example the same email or phone, or two people registering the same username at the same moment).

```python
        customer = customer_services.add_customer(db, customer_data)
```
Creates the customer row (this only stages and flushes; it does not commit, which is why the user can join the same transaction).

```python
        user = User(
            username=data.username,
            password_hash=hash_password(data.password),
            role=UserRole.CUSTOMER,
            customer_id=customer.id,
        )
        user_repositories.add(db, user)
```
Builds the login: the password is **hashed**, the role is **hard-coded to `CUSTOMER`**, and it is linked to the new customer. Then it is staged.

```python
    return user, customer.id
```
After the block exits, the commit has happened. If the user insert had failed, the customer would be rolled back too, so there are never customers without logins from a half-finished registration.

#### `change_password`

```python
def change_password(db: Session, user: User, old_password: str, new_password: str) -> None:
    if not verify_password(old_password, user.password_hash):
        raise InvalidInputError("Old password is incorrect")
```
Proves the caller really knows the current password (a stolen token alone is not enough). Becomes a `400`.

```python
    if old_password == new_password:
        raise InvalidInputError("New password must be different from the old password")
```
Blocks "changing" to the same password.

```python
    with transaction(db):
        user.password_hash = hash_password(new_password)
```
Replaces the hash. Because `user` is already tracked by the session, assigning the new value is enough; the transaction commits it.

---

### 7. `routers/auth_routers.py`: the URLs

```python
router = APIRouter(prefix="/auth", tags=["auth"])
```
Every route here starts with `/auth`, and they are grouped under "auth" in `/docs`.

#### `POST /auth/login`

```python
@router.post("/login", response_model=TokenResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
```
- `OAuth2PasswordRequestForm` reads `username` and `password` from a **form** (not JSON). That is the standard, and it is why Swagger's **Authorize** button works. It needs `python-multipart`.
- `get_db` gives a database session for this request and closes it afterwards.
- `response_model=TokenResponse` makes sure only the token fields are returned.

```python
    user = auth_services.authenticate_user(db, form.username, form.password)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
```
Failed login gives `401` with one generic message. The `WWW-Authenticate: Bearer` header is the standard hint telling the client which scheme to use.

```python
    return TokenResponse(access_token=create_access_token(user.id, user.role.value))
```
Success: create a token containing the user's id and role (`.value` turns the enum into the string `"OFFICER"`/`"CUSTOMER"`) and return it.

#### `POST /auth/register`

```python
@router.post("/register", response_model=RegisterOut, status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    user, customer_id = auth_services.register_user(db, data)
    return RegisterOut(username=user.username, customer_id=customer_id)
```
Public endpoint (no token needed). `data: RegisterIn` is the JSON body, validated automatically (bad input becomes a `400` listing every bad field). `201 Created` is the right status for a new resource. It returns only the username and customer id.

#### `POST /auth/change-password`

```python
@router.post("/change-password")
def change_password(
    data: ChangePasswordIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    auth_services.change_password(db, user, data.old_password, data.new_password)
    return {"message": "Password changed successfully"}
```
`Depends(get_current_user)` is what protects this route: no valid token, no entry (`401`). The user comes **from the token**, not from the request body, so you can only ever change **your own** password.

---

### 8. `dependencies/auth.py`: protecting the other endpoints

```python
logger = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
```
`logger` writes log lines tagged with this module's name. `OAuth2PasswordBearer` reads the `Authorization: Bearer <token>` header. If the header is missing it automatically raises `401`. `tokenUrl="/auth/login"` tells Swagger where to send the username and password.

#### `get_current_user`

```python
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
```
FastAPI calls this before the endpoint: it extracts the token and opens a DB session.

```python
    unauthorized = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
```
One prepared error, reused for every failure, so the client cannot tell *why* the token was rejected.

```python
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise unauthorized
```
Decode and verify the token, then read the user id. Failures caught: bad signature, expired or malformed token (`PyJWTError`), no `sub` (`KeyError`), or a `sub` that is not a number (`ValueError`). All become `401`.

```python
    user = user_repositories.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user
```
Reloads the user **from the database on every request**. So a deleted or deactivated user is locked out immediately, even though their token has not expired yet. This is the trade-off explained in the JWT ADR.

#### `require_roles`

```python
def require_roles(*roles: UserRole):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return checker
```
A **dependency factory**. `require_roles(UserRole.OFFICER)` returns a checker function that first authenticates (via `get_current_user`) and then compares the role. `401` = "I don't know who you are"; `403` = "I know who you are, but you may not do this". It is used on routes like `POST /customers/` and `DELETE /loans/{id}`.

#### `authenticated_user`

```python
async def authenticated_user(
    request: Request,
    user: User = Depends(get_current_user),
) -> User:
    user_id_ctx.set(str(user.id))
    logger.info("%s %s role=%s", request.method, request.url.path, user.role.value)
    return user
```
Used as a router-wide dependency. After the user is authenticated it (1) stores the user id in a context variable so every log line for this request carries it, and (2) logs one line such as `POST /loans/apply role=CUSTOMER`. It is `async` so the context variable is set in the same context the request handler runs in.

---

### 9. `seed.py` and `docker-entrypoint.sh`: the first officer

There is no public way to create an officer (registration always makes a CUSTOMER), so the first officer is created from the environment.

`seed.py`:
- `main()` reads `SEED_OFFICER_USERNAME` / `SEED_OFFICER_PASSWORD`. If either is empty it prints a message and stops (safe to run anywhere).
- `create_officer_user()` opens its own session, **skips if the username already exists** (so running it on every start is safe), otherwise saves a `User` with `role=OFFICER`, a hashed password and no `customer_id`, then commits.
- `create_customer_user()` is the same idea for a CUSTOMER login linked to an existing customer id.
- `if __name__ == "__main__": main()` makes `python -m loan_application.seed` work.

`docker-entrypoint.sh`:
```sh
set -e                           # stop immediately if any step fails
alembic upgrade head             # apply pending migrations
python -m loan_application.seed  # create the officer (skipped if already there / not configured)
exec "$@"                        # replace the shell with the real command (uvicorn)
```
So every time the container starts, the database is migrated, the officer exists, and only then does the server start. `exec` makes uvicorn the main process so it receives shutdown signals properly.

---

### 10. `logging_context.py`: user id in every log line

- `user_id_ctx = ContextVar("user_id", default="-")` is a variable that holds a **different value per request**, even with many requests running at once. `-` is shown for requests with no logged-in user.
- `UserContextFilter.filter()` copies that value onto each log record as `record.user_id`.
- `setup_logging()` installs a handler whose format includes `user=%(user_id)s`, and sets the level to `INFO`.

Result: `2026-10-21 10:15:02,123 INFO user=3 loan_application.dependencies.auth: POST /loans/apply role=CUSTOMER`.

---

### 11. `tests/test_auth_api.py`: proof it works

| Group | What is checked |
|---|---|
| `make_token`, `bearer` helpers | Build forged/expired tokens and the `Authorization` header for the tests |
| **login** | Good login returns a token; wrong password, unknown user and inactive user are all `401`; missing form fields are `400` |
| **401 on every protected route** | A parametrised test hits each customer/loan route with no token and expects `401` |
| **bad tokens** | Garbage, expired and wrong-key tokens are all `401` |
| **403 role/ownership** | A customer cannot create or delete customers, delete loans, or read another customer's data or loans |
| **registration** | Creates customer + login (`201`); a registered user can read only their own record; cannot create customers; a `role` in the body is ignored; duplicate username or email is `409`; short password or bad username is `400` |
| **change password** | New password works and the old one stops working; wrong old password, same password and short new password are `400`; no token is `401`; a customer registered with a temporary password can change it |

Run them with `uv run pytest tests/test_auth_api.py`.

---

### Security choices in one list

1. Passwords are hashed with Argon2 and never stored or returned in plain text.
2. Login errors are generic, so an attacker cannot discover which usernames exist.
3. Tokens are signed, expire in 30 minutes, and the algorithm is pinned on decode.
4. The user is reloaded from the database on every request, so deactivation takes effect at once.
5. Registration can only create `CUSTOMER` accounts; officers come only from the seed script.
6. Customer and login are saved in one transaction, so there are no half-registered users.
7. The JWT secret is required and comes from `.env`, never from the code.

## What I learned building this

- How a request travels through routers, services and repositories to the database.
- Why migrations are better than creating tables in code.
- Using dependency injection (`Depends`) for database sessions, the current user and role checks.
- Stateless authentication with JWT, password hashing, and role-based access control.
- Keeping related writes in one transaction so data never ends up half-saved.
- Splitting validation between the API layer (friendly errors) and the database (constraints as a last safety net).
- Keeping a project healthy with linting, tests, a coverage gate and CI from day one.

---

Built by [vetriselvan-inix](https://github.com/vetriselvan-inix).
