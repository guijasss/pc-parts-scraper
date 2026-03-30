FROM python:3.13.2-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# lxml / psycopg may need build deps depending on wheel availability for the platform.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libxml2-dev \
    libxslt1-dev \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY agent.py /app/agent.py
COPY src /app/src
COPY config.example.json /app/config.example.json

CMD ["python", "-m", "src.agent"]

