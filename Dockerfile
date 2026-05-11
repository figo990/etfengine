FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e "." 2>/dev/null || pip install --no-cache-dir .

COPY . .

RUN mkdir -p data/db data/cache data/logs data/reports

EXPOSE 8501 8000

ENV PYTHONPATH=/app
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_PORT=8501

CMD ["streamlit", "run", "src/dashboard/app.py", "--server.address=0.0.0.0"]
