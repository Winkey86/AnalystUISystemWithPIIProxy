FROM python:3.12-slim

WORKDIR /app

# Системные зависимости для scipy/sklearn/statsmodels
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Дефолтные директории данных создаём при старте
RUN mkdir -p /data/uploads /data/artifacts /data/plots /data/metadata

EXPOSE 8082

HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=15s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8082/health', timeout=4)"

CMD ["python", "server.py"]
