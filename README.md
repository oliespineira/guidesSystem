# Guías Torrelodones: kraal and actas services

An app for the Asociación Guías de Torrelodones (AGT): who is in the kraal each ronda (volunteers, ramas, roles), and what the kraal decides and does (meetings, votes, treasury, hostel bookings, live notices).

Assignment 1 built it as one FastAPI process with one SQLite file. Assignment 2 splits it into **two services, each with its own SQL Server database**, run locally with Docker Compose and deployed to Azure by a GitHub Actions pipeline.

**Live URL:** _added after the first deployment_

## Architecture

```mermaid
flowchart LR
  UI["UI (static files)<br/>nginx locally, Static Web App on Azure"] -->|HTTPS + CORS| K[kraal service]
  UI -->|HTTPS + CORS| A[actas service]
  A -->|"HTTP, 2 s timeout (seam.py)"| K
  K --> KDB[("kraal DB<br/>login kraal_app")]
  A --> ADB[("actas DB<br/>login actas_app")]
```

- **kraal** (`services/kraal`) owns rondas, volunteers, roles, ramas and rama assignments. It never calls actas.
- **actas** (`services/actas`) owns meetings, decisions, votes, the treasury, hostel bookings and the notices (messaging). It asks kraal about rondas and people over HTTP, only through `services/actas/app/actas/seam.py`.
- Each service connects to its own database with its own login, which cannot open the other database.
- If kraal is down, actas keeps serving its own data. Writes that need kraal return **503** with a clear message, and the notice stream degrades to whole-kraal notices. See ADR-6 and ADR-7.

## Repository layout

```
services/
  kraal/   app/  migrations/  tests/  Dockerfile  requirements.txt  requirements-dev.txt  openapi.json
  actas/   app/  migrations/  tests/  Dockerfile  requirements.txt  requirements-dev.txt  openapi.json
ui/                    static UI (index.html, config.js)
db/init.sql            creates the databases and one login per service (local only)
integration/           cross-seam tests against the running system
docker-compose.yml     the whole system locally
system.yaml            machine-readable description: services, env vars, calls, Azure names
system.schema.json     schema system.yaml is validated against
.github/workflows/     CI/CD
ADR.md  AI_USAGE.md
```

## Run everything locally

Requires Docker Desktop (on Apple Silicon, enable "Use Rosetta for x86_64/amd64 emulation", because the SQL Server image is Intel-only).

```bash
git clone https://github.com/oliespineira/guidesSystem.git
cd guidesSystem
docker compose up --build
```

| What | Where |
|---|---|
| UI | http://localhost:8080 |
| kraal API and docs | http://localhost:8001/docs |
| actas API and docs | http://localhost:8002/docs |
| SQL Server | localhost:1433 |

The first start takes a minute: SQL Server starts, `db-init` creates the databases and logins, then each service applies its migrations (`Applied migration 001_init`).

**Passwords.** Without a `.env` file, compose uses **dev-only default passwords** written in `docker-compose.yml`. They only protect a database container on your own machine, and are never used on Azure. To use your own, copy `.env.example` to `.env` and change the values. `.env` is git-ignored.

Stop with `docker compose down`. Never use `down -v` on a database you care about: it deletes the data volume.

## Run a single service without Docker

The database still runs in compose: `docker compose up -d sqlserver db-init`.

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r services/kraal/requirements-dev.txt
cd services/kraal
DATABASE_URL="mssql://kraal_app:LocalDev_Kraal_2026@localhost:1433/kraal" PORT=8001 python -m app.main
```

actas also needs to know where kraal is:

```bash
cd services/actas
DATABASE_URL="mssql://actas_app:LocalDev_Actas_2026@localhost:1433/actas" KRAAL_URL=http://localhost:8001 PORT=8002 python -m app.main
```

(Use the passwords from your `.env` if you created one.) Every environment variable each service reads, with its default, is listed in `system.yaml`.

## Tests and coverage

Tests run against **SQL Server test databases** (`kraal_test`, `actas_test`), never Azure SQL. The test suites empty every table before each test, so they refuse to run unless the database name ends in `_test`.

```bash
docker compose up -d sqlserver db-init

cd services/kraal
TEST_DATABASE_URL="mssql://kraal_app:LocalDev_Kraal_2026@localhost:1433/kraal_test" \
  python -m pytest -q --cov=app --cov-report=term-missing

cd ../actas
TEST_DATABASE_URL="mssql://actas_app:LocalDev_Actas_2026@localhost:1433/actas_test" \
  python -m pytest -q --cov=app --cov-report=term-missing
```

| Service | Tests | Coverage |
|---|---|---|
| kraal | 26 | 92% |
| actas | 125 | 94% |

The actas unit tests replace kraal with an in-memory fake (`FakeKraal` in `services/actas/tests/conftest.py`). The **cross-seam integration tests** use the real services instead:

```bash
docker compose up -d --build
python -m pytest -q integration
```

They check that actas builds a volunteer's notice topics from real kraal data over HTTP, and that with kraal stopped, the cross-seam flow returns 503 while actas keeps serving its own data.

**Lint:** `ruff check services/ integration/` and `ruff format --check services/ integration/` (rules in `ruff.toml`).

**API documents:** each service's `openapi.json` is committed, and a test fails if it no longer matches the code. After changing a route, regenerate it from inside the service folder:

```bash
python -c "import json; from app.main import app; open('openapi.json','w',encoding='utf-8').write(json.dumps(app.openapi(), indent=2, ensure_ascii=False) + '\n')"
```

## CI/CD

`.github/workflows/ci-cd.yml` runs on every push and pull request:

- **test** (once per service): ruff lint, tests on a SQL Server container with a 70% coverage gate, and a build of the Docker image.
- **validate**: `system.yaml` against `system.schema.json`, and both OpenAPI documents against the OpenAPI specification.
- **integration**: starts the whole system with compose and runs the cross-seam tests.

Changes reach `main` only through pull requests, and branch protection requires all checks to pass.

_Deployment (CD) to Azure: added with the first deployment._

## Azure deployment and initial setup

_Added with the first deployment: the resources, how the initial setup is reproduced step by step, and how each push to `main` is deployed._

## Secrets

Secrets are never committed: not in code, workflows, compose or history. Locally they live in a git-ignored `.env`; on Azure they will be GitHub Actions secrets, passed to the Container Apps as secrets.

**If a secret is ever pushed,** within 24 hours: revoke or rotate it (or, for the class service principal, notify the professor), remove it from the code, and record it below.

**Incidents:** none.

## Documentation

- `ADR.md`: architecture decisions (ADR-6 the split, ADR-7 data and migrations).
- `AI_USAGE.md`: how AI was used, with my own explanation of each piece.