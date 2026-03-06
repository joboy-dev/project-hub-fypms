#!/bin/bash

# This script deploys the FastAPI project.

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$PROJECT_DIR"

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Running database migrations..."
alembic upgrade head

echo "Seeding data"
python3 scripts/seeders/seed_departments.py
python3 scripts/seeders/seed_users.py
