#!/bin/bash
# Creates the Discord bot's database on first boot.
# Runs after the SQL init scripts (Docker sorts initdb files alphabetically).
# BOT_DB_NAME is injected from docker-compose via the postgres service environment.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE "$BOT_DB_NAME";
EOSQL

echo "Bot database '$BOT_DB_NAME' created."
