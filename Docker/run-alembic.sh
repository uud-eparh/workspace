#!/bin/bash

echo "⏳ Waiting for PostgreSQL to be ready..."

# Ждем, пока PostgreSQL будет готов принимать соединения
MAX_RETRIES=30
RETRY_COUNT=0

until pg_isready -h localhost -p 5432 -U postgres; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "❌ PostgreSQL not ready after $MAX_RETRIES attempts. Exiting."
        exit 1
    fi
    echo "   Waiting for PostgreSQL... (attempt $RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

echo "✅ PostgreSQL is ready!"

echo "⏳ Waiting for database 'openledger' to exist..."
RETRY_COUNT=0
until psql -h localhost -U postgres -d openledger -c "SELECT 1" > /dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "❌ Database 'openledger' not ready after $MAX_RETRIES attempts."
        echo "   Creating database 'openledger'..."
        psql -h localhost -U postgres -c "CREATE DATABASE openledger;"
        break
    fi
    echo "   Waiting for database 'openledger'... (attempt $RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

echo "✅ Database 'openledger' exists!"

echo "🔄 Running Alembic migrations..."
cd /workspace

# Проверяем наличие alembic
if command -v alembic &> /dev/null; then
    if [ -d "/workspace/alembic" ] && [ -f "/workspace/alembic.ini" ]; then
        echo "📝 Applying migrations..."
        alembic upgrade head
        if [ $? -eq 0 ]; then
            echo "✅ Alembic migrations completed successfully!"
        else
            echo "❌ Alembic migrations failed!"
            exit 1
        fi
    else
        echo "ℹ️ Alembic not initialized yet. Skipping migrations."
        echo "   To initialize Alembic, run:"
        echo "   cd /workspace && alembic init -t async alembic"
    fi
else
    echo "⚠️ Alembic not installed!"
fi