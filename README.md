# Loan Application Service

A small backend service for a lending company. It lets you **register customers**, **accept loan applications**, **decide eligibility automatically**, and **report a customer's loan position** through a clean REST API.

I built this as part of a REST API assessment, and I used it to learn how a real backend is put together: a web framework, a real database running in Docker, versioned migrations, automated tests and code-quality checks.

---

## What it does

- Registers customers with proper validation (name, email, phone, date of birth, monthly income).
- Accepts loan applications for a customer and calculates the EMI on the server.
- Approves or rejects each application automatically. A rejected loan always carries a reason.
- Reports a customer's loan position.
- Returns consistent, predictable JSON errors, and never leaks a stack trace to the client.

## Tech stack

| Tool | Why it is here |
|---|---|
| **Python 3.12+** | The language |
| **FastAPI** | The web framework. It also gives a free interactive API page at `/docs` |
| **Uvicorn** | The server that runs the FastAPI app |
| **SQLAlchemy 2.x** | The ORM: database tables as Python classes |
| **PostgreSQL 16 (Docker)** | The database |
| **psycopg 3** | The driver that connects Python to PostgreSQL |
| **Alembic** | Database migrations. Tables are created by migrations, never by app code |
| **Pydantic + email-validator** | Request validation and response shapes |
| **pydantic-settings** | Reading settings from the environment |
| **pytest + httpx** | Automated tests |
| **Ruff + Black + pre-commit** | Linting and formatting, checked on every commit |
| **uv** | Package and virtual environment manager |

## Project structure

```
loanapplication/
├── src/loan_application/   # The application code
│   ├── db.py               # Database engine, session and the Base class
│   ├── models.py           # SQLAlchemy models: customers and loans tables
│   ├── schemas.py          # Pydantic request/response models and validation rules
│   ├── repository.py       # The only layer that talks to the database
│   └── main.py             # FastAPI app and the API endpoints
├── alembic/                # Database migrations (versions/ holds each change)
├── alembic.ini             # Alembic configuration
├── tests/                  # Automated tests (run with pytest)
├── postman/                # Postman collection for trying the APIs
├── .postman/               # Postman workspace metadata
├── Dockerfile              # API image
├── docker-entrypoint.sh    # Runs migrations and seeding, then starts the server
├── docker-compose.yml      # API + PostgreSQL
├── .env.example            # Template for .env (copy and fill in)
├── .github/workflows/      # CI pipeline
├── pyproject.toml          # Project metadata, dependencies and pytest settings
├── uv.lock                 # Exact locked dependency versions
├── .python-version         # Python version used by uv
└── README.md               # You are here
```

### How the layers fit together

```
Client (Postman, /docs, a browser)
   -> main.py          receives the request, validates it with schemas.py
   -> repository.py    the only place that reads and writes the database
   -> models.py        describes the tables
   -> db.py            session and engine
   -> PostgreSQL in Docker
```

Keeping the database code in one layer means the endpoints stay short and the logic is easy to test.

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

The `api` container waits for the database to be healthy, runs `alembic upgrade head`, creates the officer user from `SEED_OFFICER_USERNAME` / `SEED_OFFICER_PASSWORD` (skipped if unset), and starts the server on port `8000`.

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
| `JWT_SECRET_KEY` | API | Signs access tokens |
| `SEED_OFFICER_USERNAME` / `SEED_OFFICER_PASSWORD` | Seed script | Optional initial officer account |

## API overview

All requests and responses use `Content-Type: application/json`.

| Method | Endpoint | What it does |
|---|---|---|
| `GET` | `/health` | Confirms the app is running and can reach the database |
| `POST` | `/api/customers` | Registers a customer (direct insert) |
| `GET` | `/api/customers/{id}` | Fetches one customer |
| | _the remaining assessment APIs (loan application, loan decision, loan position)_ | _add endpoint, request and response examples here_ |

### Example: register a customer

```bash
curl -X POST http://127.0.0.1:8000/api/customers \
  -H "Content-Type: application/json" \
  -d '{
        "name": "Ravi Kumar",
        "email": "ravi@example.com",
        "phone": "9876543210",
        "date_of_birth": "1998-04-12",
        "monthly_income": 45000
      }'
```

## Data model

### `customers`

| Column | Type | Rules |
|---|---|---|
| `id` | integer, auto-generated | Primary key |
| `name` | string | Required, 3 to 50 characters, letters and spaces only |
| `email` | string | Required, valid email format, **unique** |
| `phone` | string | Required, exactly 10 digits |
| `date_of_birth` | date | Required, `YYYY-MM-DD`, must be in the past |
| `monthly_income` | decimal | Required, greater than 0 |

### `loans`

| Column | Type | Rules |
|---|---|---|
| `id` | integer, auto-generated | Primary key |
| `customer_id` | integer | Foreign key to `customers` |
| `amount` | decimal | Required, 10,000 to 5,000,000 |
| `tenure_months` | integer | Required, one of 12, 24, 36, 48, 60 |
| `interest_rate` | decimal | Set by the server |
| `emi` | decimal | Calculated by the server |
| `status` | string | `APPROVED` or `REJECTED` |
| `rejection_reason` | string | Empty when the loan is approved |
| `applied_on` | date | Set by the server to the current date |

One customer can have many loans.

## Error handling

Every error comes back as JSON in a predictable shape.

**Validation failure: `400 Bad Request`**, listing *all* failing fields, not just the first:

```json
{
  "error": "VALIDATION_FAILED",
  "details": [
    { "field": "email", "message": "must be a valid email address" },
    { "field": "phone", "message": "must be exactly 10 digits" }
  ]
}
```

**Record not found: `404 Not Found`**

```json
{ "error": "NOT_FOUND", "message": "Customer with id 42 not found" }
```

**Malformed or empty JSON body: `400 Bad Request`** with `"error": "INVALID_REQUEST"`.

**Anything unexpected: `500 Internal Server Error`** with `"error": "INTERNAL_ERROR"`. A stack trace is never sent to the client.

## Database migrations

Tables are only ever created or changed through Alembic.

```bash
# Create a new migration after changing models.py
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

pytest is configured in `pyproject.toml` to look for tests in `tests/` and to import code from `src/`. Tests use an in-memory SQLite database, so PostgreSQL does not need to be running.

## Continuous integration

GitHub Actions (`.github/workflows/ci.yml`) runs on every pull request and on pushes to `main`:

- `ruff check .`
- `pytest` with a 90% coverage gate
- `docker build` to make sure the image still builds

## Code quality

Ruff (linting) and Black (formatting) run automatically on every commit through pre-commit. Set it up once:

```bash
uv run pre-commit install
```

You can also run them by hand:

```bash
uv run ruff check .
uv run black .
```

## Trying the APIs in Postman

The `postman/` folder contains a collection you can import into Postman. Start the server first, then send the requests against `http://127.0.0.1:8000`.

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
| Alembic generates an empty migration | `alembic/env.py` is not importing `models`, so Alembic cannot see the tables |
| `ModuleNotFoundError: loan_application` | Run commands with `uv run`, and make sure `src/loan_application/__init__.py` exists |

## What I learned building this

- How a request travels from the API through a repository layer to the database.
- Why migrations are better than creating tables in code.
- Using dependency injection (`Depends`) to give each request its own database session.
- Splitting validation between the API layer (friendly errors) and the database (constraints as a last safety net).
- Keeping a project clean with linting, formatting and tests from day one.

---

Built by [vetriselvan-inix](https://github.com/vetriselvan-inix).
