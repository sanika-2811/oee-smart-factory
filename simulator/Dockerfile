# Build context = repository root
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /srv
RUN pip install --no-cache-dir "paho-mqtt>=2.1,<3"
COPY simulator simulator
CMD ["python", "-m", "simulator.run"]
