#!/bin/bash
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Run database migrations
python -c "
import asyncio
from alembic.config import Config
from alembic import command
from app.core.config import settings

# Only run migrations if DATABASE_URL is set and not SQLite
if settings.DATABASE_URL and not settings.DATABASE_URL.startswith('sqlite'):
    alembic_cfg = Config('alembic.ini')
    command.upgrade(alembic_cfg, 'head')
    print('Database migrations completed')
else:
    print('Skipping migrations - no PostgreSQL database configured')
"
