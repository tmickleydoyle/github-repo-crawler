FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY crawler/ ./crawler/
COPY migrations/ ./migrations/

ENTRYPOINT ["python", "crawler/main.py"]
