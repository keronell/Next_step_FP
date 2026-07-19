# Build context is services/ (needs common/ + matching/).
FROM python:3.12-slim
WORKDIR /srv
COPY matching/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Bake the embedding model into the image: deterministic, offline-safe startup
# (no Hugging Face download on first boot). ~100MB layer.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
COPY common ./common
COPY matching/app ./app
ENV PYTHONPATH=/srv
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
