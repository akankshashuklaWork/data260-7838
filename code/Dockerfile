FROM python:3.12-slim

WORKDIR /app
COPY code/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY code/web_application ./web_application

EXPOSE 8638
CMD ["uvicorn", "web_application.app:app", "--host", "0.0.0.0", "--port", "8638"]
