FROM python:3.11-slim

WORKDIR /app
COPY src/generator/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY src/generator /app/src/generator
CMD ["python", "-m", "src.generator.generate_orders"]
