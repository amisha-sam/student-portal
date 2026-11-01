# Student Marks & Performance Portal
Flask + PostgreSQL portal that records marks, calculates grades and flags students who need support.

## Run locally
    cd docker && docker compose up --build
    docker compose exec app flask --app app seed
Open http://localhost:8000  (admin/admin123, teacher/teacher123, student R001/student123)

## Endpoints
/health, /metrics (Prometheus), /at-risk, /export.csv, /report/<id>.pdf

## Tests
    cd app && pip install -r requirements.txt -r requirements-dev.txt && pytest
