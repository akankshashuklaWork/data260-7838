FROM python:3.11-slim

WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn aiokafka
COPY config.py common.py ./
COPY app ./app
COPY worker ./worker

# The compose file chooses the command: the Kafka worker or the FastAPI wrapper.
CMD ["python", "-m", "worker.consumer"]
