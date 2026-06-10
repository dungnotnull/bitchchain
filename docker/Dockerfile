FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Pre-create directories
RUN mkdir -p logs models

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8333 8332

CMD ["python", "-m", "agent.main", "status"]
