#!/bin/sh
# Downloads and loads the Chinook sample database (music store: artists, albums,
# tracks, invoices). Runs once on first container init.
set -e

CHINOOK_URL="https://raw.githubusercontent.com/lerocha/chinook-database/master/ChinookDatabase/DataSources/Chinook_PostgreSql.sql"
CHINOOK_FILE="/tmp/chinook.sql"

echo "==> Downloading Chinook sample DB..."
wget -q -O "$CHINOOK_FILE" "$CHINOOK_URL"

echo "==> Loading Chinook into ${POSTGRES_DB}..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f "$CHINOOK_FILE"

echo "==> Chinook loaded. Tables created:"
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -c "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY 1;"
