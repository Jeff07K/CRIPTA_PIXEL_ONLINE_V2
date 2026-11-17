FROM python:3.12-slim
WORKDIR /app
COPY cloud_server.py server.py server_web.py protocol.py ./
COPY web/ ./web/
COPY assets/ ./assets/
ENV PORT=8080 DATA_DIR=/data PYTHONUNBUFFERED=1
EXPOSE 8080
VOLUME ["/data"]
CMD ["python", "cloud_server.py"]
