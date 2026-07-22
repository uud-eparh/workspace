#!/bin/bash

echo "🚀 Starting OpenLedger Development Environment..."

# Инициализируем PostgreSQL и создаем БД если нужно
/usr/local/bin/init-postgres.sh

# Запускаем supervisord
echo "📦 Starting services via supervisord..."
/usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf

# Ждем, пока PostgreSQL и Redis запустятся
echo "⏳ Waiting for services to be ready..."
sleep 10

# Запускаем Alembic
echo "🔄 Running Alembic migrations..."
/usr/local/bin/run-alembic.sh

# Выводим информацию о запуске
echo ""
echo "========================================="
echo "✅ OpenLedger Development Environment is ready!"
echo "========================================="
echo "🔗 VS Code Server: http://localhost:8080"
echo "🐘 PostgreSQL: localhost:5432 (user: postgres, password: postgres)"
echo "📦 Redis: localhost:6379"
echo "========================================="
echo ""
echo "📝 Quick commands:"
echo "  - Connect to PostgreSQL: psql -U postgres -h localhost -d openledger"
echo "  - Check Redis: redis-cli ping"
echo "  - VS Code Server: http://localhost:8080"
echo ""

# Оставляем supervisord работать в foreground
wait