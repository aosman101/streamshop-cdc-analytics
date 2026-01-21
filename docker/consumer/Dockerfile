FROM python:3.11-slim

WORKDIR /app
COPY src/consumer/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY src/consumer /app/src/consumer
CMD ["python", "-m", "src.consumer.cdc_to_clickhouse"]
