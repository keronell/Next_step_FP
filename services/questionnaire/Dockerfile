# Build context is services/ (needs common/ + questionnaire/).
FROM python:3.12-slim
WORKDIR /srv
COPY questionnaire/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common ./common
COPY questionnaire/app ./app
ENV PYTHONPATH=/srv
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
