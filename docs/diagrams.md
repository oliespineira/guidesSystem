# Diagrams

All diagrams match the code and the deployment as of 28 Nov 2026. They are written in Mermaid, so GitHub draws them and they change with the code.

## 1. Before: Assignment 1, one process, one database

```mermaid
flowchart LR
  B["Browser<br/>(web/index.html)"] -->|HTTP| APP
  subgraph APP["One FastAPI process (app.py)"]
    K["kraal module<br/>rondas, volunteers, ramas, roles"]
    A["actas module<br/>meetings, votes, treasury, bookings"]
    M["messaging<br/>broker + live stream"]
    A -->|"seam.py<br/>(function calls)"| K
    A --> M
  end
  APP --> DB[("SQLite app.db<br/>all 16 tables,<br/>FKs across both domains")]
```

## 2. After: Assignment 2, two services, two databases

```mermaid
flowchart LR
  B["Browser<br/>(UI: static files)"] -->|"HTTPS + CORS"| K
  B -->|"HTTPS + CORS"| A
  subgraph KS["kraal service"]
    K["FastAPI<br/>rondas, volunteers,<br/>ramas, roles"]
  end
  subgraph AS["actas service"]
    A["FastAPI<br/>meetings, votes, treasury,<br/>bookings, notices"]
  end
  A -->|"HTTP via seam.py<br/>2 s timeout, 503 if down"| K
  K --> KDB[("kraal DB<br/>user kraal_app")]
  A --> ADB[("actas DB<br/>user actas_app")]
```

What changed: the seam became HTTP; the three ronda_id foreign keys across the domains became plain ids checked over HTTP at write time; each service has its own database and user, which cannot open the other one; when kraal is down, actas keeps serving its own data and returns 503 only for flows that need kraal.

## 3. Deployment on Azure

```mermaid
flowchart TB
  U["User's browser"]
  subgraph GH["GitHub"]
    REPO["Repository<br/>main protected: PRs + CI checks"]
    CI["CI: lint, tests on SQL Server,<br/>coverage 70%, SAST, SCA, IaC scan,<br/>integration"]
    CD["CD on main: images by commit SHA,<br/>deploy, health check, rollback, DAST"]
    GHCR["GHCR<br/>guidessystem-kraal:sha<br/>guidessystem-actas:sha"]
    REPO --> CI --> CD --> GHCR
  end
  subgraph RG["Resource group rg-oespineira-ieu2024 (swedencentral)"]
    UI["Storage static website<br/>oespineiraieu2024ui<br/>(public URL)"]
    subgraph ENV["Container Apps environment oespineira-ieu2024-env (Consumption)"]
      ING["Ingress: HTTPS, routing,<br/>load balancing"]
      KA["oespineira-ieu2024-kraal<br/>0 to 1 replicas"]
      AA["oespineira-ieu2024-actas<br/>0 to 1 replicas"]
      ING --> KA
      ING --> AA
    end
    LAW["Log Analytics workspace oespineira-ieu2024-logs<br/>containers' logs, 0.15 GB/day cap"]
    ENV -->|"console and system logs"| LAW
    subgraph SQL["SQL server oespineira-ieu2024-sql<br/>firewall: Azure services only"]
      KDB[("kraal-db<br/>serverless, free offer")]
      ADB[("actas-db<br/>serverless, free offer")]
    end
    ID["Managed identity oespineira-ieu2024-github<br/>Contributor on this group only"]
  end
  U -->|"loads index.html + config.js"| UI
  U -->|"API calls (HTTPS)"| ING
  AA -->|"HTTPS to kraal's address"| ING
  KA -->|"encrypted, contained user kraal_app"| KDB
  AA -->|"encrypted, contained user actas_app"| ADB
  CD -->|"OIDC login, no stored password"| ID
  CD -->|"az containerapp update"| ENV
  CD -->|"upload ui/"| UI
  GHCR -->|"image pulled on deploy"| ENV
```

The resources are described in Terraform (infra/terraform), except the two databases, created by infra/setup.sh (the SQL free offer has no Terraform setting).

## 4. CI/CD pipeline

```mermaid
flowchart LR
  PR["Pull request"] --> T["test (kraal, actas)<br/>ruff, pip-audit, tests on SQL Server,<br/>coverage, image build, Trivy"]
  PR --> S["sast<br/>Semgrep"]
  PR --> V["validate<br/>system.yaml, OpenAPI"]
  PR --> I["iac<br/>terraform fmt/validate, Checkov"]
  T --> IN["integration<br/>compose + cross-seam tests"]
  IN --> M{"All green?<br/>merge to main"}
  S --> M
  V --> M
  I --> M
  M --> CI2["CD calls CI again<br/>on the merged commit"]
  CI2 --> IMG["images: build + push,<br/>tagged with the SHA"]
  IMG --> DEP["deploy: OIDC login, update both apps,<br/>wait for /health = this SHA"]
  DEP -->|ok| UIP["publish the UI"]
  DEP -->|fails| RB["roll back to the previous images"]
  UIP --> DAST["dast: ZAP baseline<br/>against the live system"]
```

## 5. Kraal's database

```mermaid
erDiagram
  rondas ||--o{ ramas : "has"
  rondas ||--o{ roles : "has"
  rondas ||--o{ rama_assignments : "for"
  volunteers ||--o{ roles : "holds"
  volunteers ||--o{ rama_assignments : "is placed"
  ramas ||--o{ rama_assignments : "contains"

  rondas {
    int id PK
    nvarchar year_label "UNIQUE, max 20"
    nvarchar start_date "ISO date"
    nvarchar status "active or closed"
  }
  volunteers {
    int id PK
    nvarchar name "max 100"
    nvarchar joined_date "ISO date, optional"
    int active "0 or 1"
  }
  ramas {
    int id PK
    int ronda_id FK
    nvarchar name "UNIQUE per ronda"
  }
  roles {
    int id PK
    int ronda_id FK
    int volunteer_id FK
    nvarchar role_name "max 100"
    nvarchar role_key "computed, no capitals or accents, UNIQUE per ronda (002)"
  }
  rama_assignments {
    int id PK
    int ronda_id FK "one rama per volunteer per ronda"
    int rama_id FK
    int volunteer_id FK
    int availability_pct "0 to 100"
    nvarchar notes "max 1000"
  }
```

Plus schema_migrations (version, applied_at), written by the migration runner.

## 6. Actas's database

ronda_id and volunteer_id are plain ids from kraal: checked over HTTP at write time, never foreign keys (ADR-7).

```mermaid
erDiagram
  meetings ||--o{ agenda_items : "has"
  agenda_items ||--o{ decisions : "has"
  decisions ||--o| votings : "may be voted"
  votings ||--o{ votes : "receives"
  budgets ||--o{ budget_requests : "receives"
  budget_requests ||--o{ request_events : "history"
  calendar_events ||--o| bookings : "may need"
  budget_requests |o--o{ bookings : "pays for"

  meetings {
    int id PK
    int ronda_id "kraal id, no FK"
    nvarchar date "ISO date"
    nvarchar title "max 200"
  }
  agenda_items {
    int id PK
    int meeting_id FK
    nvarchar section_title
    nvarchar content
    int position
  }
  decisions {
    int id PK
    int agenda_item_id FK
    nvarchar description
    nvarchar vote_result
  }
  votings {
    int decision_id PK,FK "one vote per decision"
    nvarchar closes_at "ISO datetime"
    nvarchar rule "reserved word, written [rule]"
    int closed "0 or 1"
  }
  votes {
    int id PK
    int decision_id FK
    int volunteer_id "kraal id, no FK"
    nvarchar choice "yes, no or abstain"
    nvarchar cast_at
  }
  calendar_events {
    int id PK
    int ronda_id "kraal id, no FK"
    nvarchar start_date
    nvarchar end_date "not before start_date"
    nvarchar activity_type
    nvarchar assigned_volunteers "free text"
  }
  bookings {
    int event_id PK,FK "one booking per outing"
    nvarchar book_by "deadline"
    nvarchar status "pending or booked"
    nvarchar venue
    int request_id FK "the payment"
    nvarchar last_reminded "once a day at most"
  }
  budgets {
    int id PK
    int ronda_id "kraal id, no FK"
    nvarchar category "UNIQUE per ronda"
    int allocated_cents ">= 0"
  }
  budget_requests {
    int id PK
    int budget_id FK
    nvarchar rama "free text"
    nvarchar item
    nvarchar item_key "for duplicate detection"
    int amount_cents "> 0"
    nvarchar status "pending, approved, rejected, paid"
  }
  request_events {
    int id PK
    int request_id FK
    nvarchar action
    nvarchar actor
    nvarchar note
    nvarchar payment_ref
    nvarchar created_at "UTC, append-only"
  }
  notices {
    int id PK
    nvarchar topic "e.g. ronda.3.rama.guias"
    nvarchar title
    nvarchar body
    nvarchar created_at
  }
```

Plus schema_migrations (version, applied_at).