# Build context = repository root (the backend imports the shared ``simulator`` package)
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv

COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend backend
COPY simulator simulator

WORKDIR /srv/backend
# train the Isolation Forest at build time (model.pkl is also auto-trained on first start if missing)
RUN python -m app.ml.train > /dev/null

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
