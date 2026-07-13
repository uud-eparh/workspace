#!/bin/bash

PG_VERSION=$(ls /usr/lib/postgresql/ 2>/dev/null | head -1 || echo "17")
PG_DATA_DIR="/var/lib/postgresql/${PG_VERSION}/main"

# Проверяем, запущен ли PostgreSQL
if pg_isready -h localhost -p 5432 -U postgres > /dev/null 2>&1; then
    echo "✅ PostgreSQL is already running"
    # Проверяем, существует ли БД
    if psql -h localhost -U postgres -lqt | cut -d \| -f 1 | grep -qw openledger; then
        echo "✅ Database 'openledger' already exists"
    else
        echo "📦 Creating database 'openledger'..."
        psql -h localhost -U postgres -c "CREATE DATABASE openledger;"
        echo "✅ Database 'openledger' created!"
    fi
    exit 0
fi

# Проверяем, инициализирована ли БД
if [ ! -f "${PG_DATA_DIR}/PG_VERSION" ]; then
    echo "🔧 Initializing PostgreSQL database (version ${PG_VERSION})..."
    
    # Создаем директорию если её нет
    mkdir -p "${PG_DATA_DIR}"
    chown -R postgres:postgres "/var/lib/postgresql/${PG_VERSION}"
    chown -R postgres:postgres "/var/log/postgresql"
    chown -R postgres:postgres "/var/run/postgresql"
    
    # Инициализируем БД
    su - postgres -c "/usr/lib/postgresql/${PG_VERSION}/bin/initdb -D ${PG_DATA_DIR}"
    
    # Создаем конфигурацию для аутентификации
    echo "host all all 127.0.0.1/32 trust" >> "${PG_DATA_DIR}/pg_hba.conf"
    echo "host all all ::1/128 trust" >> "${PG_DATA_DIR}/pg_hba.conf"
    
    # Запускаем PostgreSQL для создания БД
    su - postgres -c "/usr/lib/postgresql/${PG_VERSION}/bin/postgres -D ${PG_DATA_DIR} &"
    
    echo "⏳ Waiting for PostgreSQL to start..."
    sleep 5
    
    # Создаем базу данных
    echo "📦 Creating database 'openledger'..."
    su - postgres -c "psql -c \"CREATE DATABASE openledger;\""
    echo "✅ Database 'openledger' created!"
    
    # Останавливаем PostgreSQL (supervisord запустит его снова)
    su - postgres -c "psql -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid <> pg_backend_pid();\""
    sleep 2
    
    # Убиваем процесс если остался
    pkill -f "postgres -D ${PG_DATA_DIR}" || true
    
    echo "✅ PostgreSQL initialized successfully!"
else
    echo "✅ PostgreSQL already initialized, skipping..."
fi