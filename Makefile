# Quick commands (Linux / macOS / Git-Bash). Windows PowerShell users: see scripts/dev.ps1
PY ?= python

.PHONY: setup dev backend frontend docker test smoke train verify-db screenshots

setup:           ## install backend + frontend dependencies
	$(PY) -m venv .venv && . .venv/bin/activate && pip install -r backend/requirements-dev.txt
	cd frontend && npm install

dev:             ## run backend (direct mode, no Docker) and frontend together
	@echo "Backend  -> http://localhost:8000/docs"
	@echo "Frontend -> http://localhost:5173"
	@( cd backend && $(PY) -m uvicorn app.main:app --port 8000 --reload & cd frontend && npm run dev )

backend:
	cd backend && $(PY) -m uvicorn app.main:app --port 8000 --reload

frontend:
	cd frontend && npm run dev

docker:          ## full stack: mosquitto + simulator + backend + frontend
	docker compose up --build

test:            ## backend pytest + frontend typecheck/vitest/build
	cd backend && $(PY) -m pytest -q
	cd frontend && npm run build && npm test

smoke:           ## end-to-end smoke test (starts its own backend)
	$(PY) scripts/smoke_test.py

train:           ## retrain the Isolation Forest (writes backend/models/model.pkl)
	cd backend && $(PY) -m app.ml.train

verify-db:       ## check the manually created PostgreSQL + InfluxDB
	cd backend && $(PY) -m app.storage.verify
