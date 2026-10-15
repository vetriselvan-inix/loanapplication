#!/bin/sh
set -e

alembic upgrade head
python -m loan_application.seed

exec "$@"
