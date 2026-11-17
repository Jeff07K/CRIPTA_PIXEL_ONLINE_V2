FROM python:3.12-slim
WORKDIR /app
COPY requirements-cloud.txt ./
RUN pip install --no-cache-dir -r requirements-cloud.txt
COPY cloud_server.py server.py server_web.py protocol.py db_postgres.py ./
COPY web/ ./web/
COPY assets/ ./assets/
ENV PYTHONUNBUFFERED=1
EXPOSE 10000
CMD ["python", "cloud_server.py"]
