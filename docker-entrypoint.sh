#!/bin/sh
set -e  #stop immediatrely if any step fails

alembic upgrade head # apply any pending migrations to the postgres
python -m loan_application.seed  # create the officer user (skipped if already there / not configured

exec "$@" # replace the shell with the cmd (uvicorn)
