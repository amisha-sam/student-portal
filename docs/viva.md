# Viva Q&A Guide — Student Marks & Performance Portal

This document prepares the project owner for jury questions during the viva examination. Each section explains the technical choices, alternatives, and practical reasoning behind every phase of the project in clear, plain language.

---

## Phase A: Application and Containers

### 1. What does the application do, and what problem does it solve?
- **What it does:** The portal automates marks entry, calculates subject and overall grades, generates downloadable PDF report cards and CSV exports, and detects students who fall below performance benchmarks (any subject < 40% or overall < 50%).
- **Why this architecture:** We used Flask with PostgreSQL and SQLAlchemy ORM because it is lightweight, fast to run, and easy to deploy in containers with low memory consumption (under 100 MB RAM), ideal for free-tier AWS compute.
- **Alternatives considered:** Django or FastAPI. Django is heavier and includes unnecessary batteries (admin site, heavy ORM), while FastAPI is async-focused and adds complexity for server-rendered HTML templates. Flask provides the best balance of simplicity, readability, and performance for a Jinja + Chart.js web app.

### 2. Why run Gunicorn with 1 worker and multiple threads instead of multiple worker processes?
- **What it does:** Gunicorn runs with `--workers 1 --threads 4`.
- **Why this choice:** Prometheus metrics are stored in process memory. If Gunicorn spawns multiple worker processes, scraping `/metrics` will hit different workers alternately, resulting in counters jumping backwards and inconsistent gauge readings unless multiprocess directory mode is configured. 1 worker with 4 threads handles concurrent requests cleanly while keeping Prometheus metrics completely consistent.
- **Alternatives considered:** Gunicorn multiprocess mode with shared tmpfs directory. This requires file locks, complex setup, and consumes more RAM on small instances.

### 3. Why use Docker and Docker Compose for local development?
- **What it does:** Packages the Flask application and PostgreSQL 16 database into isolated, reproducible containers.
- **Why this choice:** Ensures that the app runs identically on the developer's laptop and on EC2 in AWS without "it worked on my machine" issues. `docker-compose.yml` allows one-command startup (`docker compose up --build`).
- **Alternatives considered:** Running PostgreSQL locally on the host machine. This risks version mismatches, requires manual database installation, and pollutes the developer's system.

### 4. Why pin `SQLAlchemy==2.0.36` and specify `postgresql+psycopg2://`?
- **What it does:** Explicitly pins the SQLAlchemy version and database driver URL scheme.
- **Why this choice:** Unpinned SQLAlchemy on newer releases attempted to load `psycopg` (v3) instead of `psycopg2`, crashing the application container upon connection. Specifying `postgresql+psycopg2://` guarantees the tested, rock-solid psycopg2-binary driver is used every time.
- **Alternatives considered:** Unpinned driver strings (`postgresql://`). These can silently select incompatible drivers depending on environment packages.
