FROM python:3.11-slim
WORKDIR /app
RUN mkdir -p /app/data
ENV DATA_DIR=/app/data
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python", "src/main.py"]