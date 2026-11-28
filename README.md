# Guías Torrelodones: kraal and actas services

An app for the Asociación Guías de Torrelodones (AGT): who is in the kraal each ronda (volunteers, ramas, roles), and what the kraal decides and does (meetings, votes, treasury, hostel bookings, live notices).

Assignment 1 built it as one FastAPI process with one SQLite file. Assignment 2 splits it into **two services, each with its own SQL Server database**, run locally with Docker Compose and deployed to Azure by a GitHub Actions pipeline.

**Live URL:** https://oespineiraieu2024ui.z1.web.core.windows.net (the first request after a quiet period can take up to a minute: the services and the databases start on demand, and the UI shows "El servicio está arrancando" meanwhile)

## Architecture

```mermaid
flowchart LR
  UI["UI (static files)<br/>nginx locally, Storage static website on Azure"] -->|HTTPS + CORS| K[kraal service]
  UI -->|HTTPS + CORS| A[actas service]
  A -->|"HTTP, 2 s timeout (seam.py)"| K
  K --> KDB[("kraal DB<br/>user kraal_app")]
  A --> ADB[("actas DB<br/>user actas_app")]
```

- **kraal** (`services/kraal`) owns rondas, volunteers, roles, ramas and rama assignments. It never calls actas.
- **actas** (`services/actas`) owns meetings, decisions, votes, the treasury, hostel bookings and the notices (messaging). It asks kraal about rondas and people over HTTP, only through `services/actas/app/actas/seam.py`.
- Each service connects to its own database with its own user, which cannot open the other database.
- If kraal is down, actas keeps serving its own data. Writes that need kraal return **503** with a clear message, and the notice stream degrades to whole-kraal notices. See ADR-6 and ADR-7.

More diagrams (before and after the split, the Azure deployment, the pipeline, and both databases) are in [docs/diagrams.md](docs/diagrams.md).

## Repository layout

```
services/
  kraal/   app/  migrations/  tests/  Dockerfile  requirements.txt  requirements-dev.txt  openapi.json
  actas/   app/  migrations/  tests/  Dockerfile  requirements.txt  requirements-dev.txt  openapi.json
ui/                    static UI (index.html, config.js)
db/init.sql            creates the databases and one user per service (local only)
integration/           cross-seam tests against the running system
infra/                 setup.sh (the initial Azure setup), create-user.sql, terraform/ (infrastructure as code)
docs/diagrams.md       architecture, deployment, pipeline and database diagrams
docker-compose.yml     the whole system locally
system.yaml            machine-readable description: services, env vars, calls, Azure names
system.schema.json     the official schema system.yaml is validated against (copied unchanged)
.github/               CI/CD workflows and Dependabot
ADR.md  AI_USAGE.md  ruff.toml
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

The first start takes a minute: SQL Server starts, `db-init` creates the databases and users, then each service applies its migrations (`Applied migration 001_init`, and so on).

**Passwords.** Without a `.env` file, compose uses **dev-only default passwords** written in `docker-compose.yml`. They only protect a database container on your own machine, and are never used on Azure. To use your own, copy `.env.example` to `.env` and change the values before the first start. `.env` is git-ignored.

Stop with `docker compose down`. Never use `down -v` on a database you care about: it deletes the data volume.

## Run a single service without Docker

Start only the database in compose (not the services, so ports 8001 and 8002 stay free):

```bash
docker compose up -d sqlserver db-init
```

Then, from the repository root, in its own terminal for each service:

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r services/kraal/requirements-dev.txt
cd services/kraal
DATABASE_URL="mssql://kraal_app:LocalDev_Kraal_2026@localhost:1433/kraal" PORT=8001 python -m app.main
```

actas, in a second terminal, also from the repository root (it needs to know where kraal is):

```bash
source venv/bin/activate
pip install -r services/actas/requirements-dev.txt
cd services/actas
DATABASE_URL="mssql://actas_app:LocalDev_Actas_2026@localhost:1433/actas" KRAAL_URL=http://localhost:8001 PORT=8002 python -m app.main
```

These are the dev-only default passwords from `docker-compose.yml`. If you created a `.env`, use its passwords instead: compose created the database users with them. Every environment variable each service reads, with its default, is listed in `system.yaml`.

## Database migrations

Each service applies the SQL files in its `migrations/` folder at startup, in order, each exactly once and inside one transaction, and records them in `schema_migrations`. A migration that fails rolls back completely and the service does not start. Applied migrations are never edited; a correction is a new file.

| Service | Migrations |
|---|---|
| kraal | `001_init`, `002_role_key` (role names unique ignoring accents and capitals; changes a table that already holds data), `003_roles_by_volunteer` (an index for the membership lookup) |
| actas | `001_init` |

Migration files must not contain question marks, not even in comments: `db.py` turns them into query placeholders. The runner also refuses an empty file.

## Tests and coverage

Tests run against **SQL Server test databases** (`kraal_test`, `actas_test`), never Azure SQL. The test suites empty every table before each test, so they refuse to run unless the database name ends in `_test`.

From the repository root, with the virtual environment active and both dev requirements installed:

```bash
docker compose up -d sqlserver db-init

cd services/kraal
TEST_DATABASE_URL="mssql://kraal_app:LocalDev_Kraal_2026@localhost:1433/kraal_test" \
  python -m pytest -q --cov=app --cov-report=term-missing

cd ../actas
TEST_DATABASE_URL="mssql://actas_app:LocalDev_Actas_2026@localhost:1433/actas_test" \
  python -m pytest -q --cov=app --cov-report=term-missing
cd ../..
```

| Service | Tests | Coverage (CI enforces at least 70%) |
|---|---|---|
| kraal | 30 | 93% |
| actas | 125 | 94% |

The actas unit tests replace kraal with an in-memory fake (`FakeKraal` in `services/actas/tests/conftest.py`), and `test_seam.py` tests the real HTTP calls with only the network replaced. The **cross-seam integration tests** use the real services instead:

```bash
docker compose up -d --build
python -m pytest -q integration
```

They check that actas builds a volunteer's notice topics from real kraal data over HTTP, and that with kraal stopped, the cross-seam flow returns 503 while actas keeps serving its own data.

**Lint:** `ruff check services/ integration/` and `ruff format --check services/ integration/` (rules in `ruff.toml`; ruff comes with the dev requirements).

**API documents:** each service's `openapi.json` is committed, and a test fails if it no longer matches the code. After changing a route, regenerate it from inside the service folder:

```bash
python -c "import json; from app.main import app; open('openapi.json','w',encoding='utf-8').write(json.dumps(app.openapi(), indent=2, ensure_ascii=False) + '\n')"
```

## CI/CD

Two workflows in `.github/workflows/`. Every action is pinned to a commit SHA, and every job has a time limit.

- **`ci.yml`** runs on every pull request and on pushes to every branch except `main`:
  - **test** (once per service): ruff lint; pip-audit on the pinned packages; the tests on a SQL Server container with a 70% coverage gate; a build of the Docker image; a Trivy scan of the image, failing on HIGH or CRITICAL vulnerabilities that have a fix;
  - **sast**: Semgrep on both services' code;
  - **validate**: `system.yaml` against `system.schema.json`, and both OpenAPI documents against the OpenAPI specification;
  - **iac**: `terraform fmt -check`, `terraform validate` and a Checkov scan of `infra/terraform` (never applies);
  - **integration**: starts the whole system with compose and runs the cross-seam tests.
- **`cd.yml`** runs on pushes to `main` (that is, after a pull request is merged):
  1. calls `ci.yml`, so nothing is deployed unless CI passed on the same commit;
  2. builds each image and pushes it to GHCR, tagged with the commit SHA (`ghcr.io/oliespineira/guidessystem-<service>:<sha>`);
  3. signs in to Azure with OIDC (no stored Azure password), sets the connection strings as Container Apps secrets and deploys both images, with `GIT_SHA` as an environment variable;
  4. waits up to 5 minutes until both `/health` endpoints answer `"status":"ok"` with this commit's SHA;
  5. writes `ui/config.js` with the services' addresses and uploads `ui/` to the storage static website;
  6. if any step fails, puts the previous images back;
  7. runs an OWASP ZAP baseline scan of the live system (report-only; the reports are saved as run artifacts).

Changes reach `main` only through pull requests, and branch protection requires the CI checks to pass. Dependabot proposes updates to the Python packages, the base images, the actions and the Terraform provider every week.

## Azure deployment and initial setup

Following the A2 deployment guide, the system runs in my own Azure for Students subscription, with nothing else in its resource group:

| Resource | Name |
|---|---|
| Resource group | `rg-oespineira-ieu2024` (swedencentral) |
| UI (Storage static website) | `oespineiraieu2024ui` |
| Container Apps environment (Consumption) | `oespineira-ieu2024-env` |
| Log Analytics workspace (the containers' logs, capped at 0.15 GB a day) | `oespineira-ieu2024-logs` |
| Container Apps (0 to 1 replicas) | `oespineira-ieu2024-kraal`, `oespineira-ieu2024-actas` |
| SQL server | `oespineira-ieu2024-sql` |
| Serverless databases (free offer) | `oespineira-ieu2024-kraal-db`, `oespineira-ieu2024-actas-db` |
| Pipeline identity (OIDC) | `oespineira-ieu2024-github`, Contributor on the resource group only |

The professors have the Reader role on the resource group.

### Reproducing the initial setup

Every command is in **`infra/setup.sh`**, in the order of the guide's steps 2–7 and 9. It needs `az`, `gh` and Docker (for `sqlcmd`), and must be run in **bash**, not zsh (zsh changes `:r` in the OIDC subject).

1. Activate Azure for Students and select it: `az login`, then `az account set --subscription <id>`.
2. List the regions your subscription allows, and use one of them (the SQL free offer is not available in spaincentral):
   `az policy assignment list --query "[].{name:displayName, regions:parameters.listOfAllowedLocations.value}" -o json`
3. In bash, type the three passwords without showing them, and keep them in a password manager:
   `read -s SQL_ADMIN_PASSWORD; read -s KRAAL_DB_PASSWORD; read -s ACTAS_DB_PASSWORD`
4. Run `infra/setup.sh` step by step, checking each result before the next.

After the setup, only the pipeline changes anything.

### Infrastructure as code (Terraform)

`infra/terraform` describes 12 Azure resources: the resource group, the storage account and its static website, the Log Analytics workspace, the Container Apps environment and both apps, the SQL server and its firewall rule, and the pipeline's identity and its two OIDC credentials. They were created by `infra/setup.sh` and taken over with `import` blocks, so Terraform never recreated them. Left out on purpose: the databases (no Terraform setting for the SQL free offer), the role assignments, and what CD changes on each deploy (images, environment variables, secrets).

```bash
cd infra/terraform
export ARM_SUBSCRIPTION_ID=$(az account show --query id -o tsv)
export TF_VAR_subscription_id=$ARM_SUBSCRIPTION_ID
read -s TF_VAR_sql_admin_password; export TF_VAR_sql_admin_password
terraform init
terraform plan        # must say "No changes"
```

CI runs `terraform fmt -check`, `terraform validate` and a Checkov scan on every change, but never applies. Each Checkov finding that is skipped has its reason written next to the resource. The state file stays local and git-ignored (it holds secret values).

### Logs

The Container Apps environment sends the containers' logs to the Log Analytics workspace `oespineira-ieu2024-logs` (30 days, capped at 0.15 GB a day). In the portal: the workspace → **Logs**, then for example:

```
ContainerAppConsoleLogs_CL
| where Log_s contains "migration"
| project TimeGenerated, ContainerAppName_s, Log_s
| order by TimeGenerated desc
```

Live, from the terminal:

```bash
az containerapp logs show --name oespineira-ieu2024-actas --resource-group rg-oespineira-ieu2024 --follow
```

### Rollback

CD rolls back automatically when the new version doesn't become healthy. To go back to an earlier version by hand, deploy its image by commit SHA:

```bash
az containerapp update --name oespineira-ieu2024-kraal --resource-group rg-oespineira-ieu2024 \
  --image ghcr.io/oliespineira/guidessystem-kraal:<earlier-sha>
```

## Secrets

Secrets are never committed: not in code, workflows, compose or history.

- **Locally:** a git-ignored `.env` (optional; compose has dev-only defaults that are never used on Azure).
- **GitHub Actions secrets:** `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `KRAAL_DB_PASSWORD`, `ACTAS_DB_PASSWORD`. Variables: `PREFIX`, `RESOURCE_GROUP`, `UI_STORAGE`.
- **On Azure:** each database connection string is a Container Apps secret, passed to the app by `secretref`, never as a plain environment variable. The pipeline signs in with OIDC, so no Azure password is stored at all.
- **On GitHub:** secret scanning and push protection are on.

**If a secret is ever pushed,** within 24 hours: change it (for a database user: `ALTER USER ... WITH PASSWORD` as the server admin, then update the GitHub secret and redeploy), remove it from the code, and record it below.

**Incidents:** none.

## Documentation

- `ADR.md`: architecture decisions. ADR-1 to 5 from Assignment 1 (3, 4 and 5 superseded); ADR-6 the split, ADR-7 data and migrations, ADR-8 serverless hosting on Azure, ADR-9 pipeline and testing, ADR-10 self-managed infrastructure (not built).
- `AI_USAGE.md`: how AI was used, with my own explanation of each piece.
- `docs/diagrams.md`: before and after the split, the Azure deployment, the pipeline, and both databases.
- `system.yaml` and each service's `openapi.json`: the machine-readable description of the system, validated in CI.