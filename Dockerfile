FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

WORKDIR /app/src
ENV PORT=8000
ENV PYTHONPATH=/app/src
EXPOSE 8000

CMD ["gunicorn","--workers","3","--threads","4","--bind","0.0.0.0:8000","app:app"]
