FROM python:3.11-slim

# Устанавливаем переменные окружения
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# Устанавливаем все необходимые пакеты
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    ca-certificates \
    build-essential \
    libpq-dev \
    postgresql \
    postgresql-contrib \
    postgresql-client \
    redis-server \
    supervisor \
    gnupg \
    lsb-release \
    vim \
    nano \
    htop \
    git \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем code-server
RUN curl -fsSL https://code-server.dev/install.sh | sh

# Создаем директории для данных PostgreSQL
RUN mkdir -p /var/lib/postgresql/17/main \
    && chown -R postgres:postgres /var/lib/postgresql \
    && chown -R postgres:postgres /var/log/postgresql \
    && chown -R postgres:postgres /var/run/postgresql

# Создаем рабочую директорию
WORKDIR /workspace

# Копируем requirements.txt для установки Python пакетов
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Копируем конфиг supervisord
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Открываем порты
EXPOSE 8080 5432 6379 8000

# Запускаем supervisord
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]