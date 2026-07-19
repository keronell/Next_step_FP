# Build context is services/ (needs common/ + roadmap/).
FROM python:3.12-slim
WORKDIR /srv
COPY roadmap/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common ./common
COPY roadmap/app ./app
ENV PYTHONPATH=/srv
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
