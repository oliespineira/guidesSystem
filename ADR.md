## 1. Backend language and framework: Python with FastAPI
Date: 2026-09-19


Status: Decided


Context: The assignment specifies that the app must run as one process on SQLite. In my case, the app is for an association of about 20 volunteers (the Kraal). I had to choose a language, Java (which I know better) or Python (which is what we have seen in class), and then a framework: Flask, FastAPI or Django.


Decision: I chose Python, because SQLite is built into its standard library and there is no compile or build step, and FastAPI, because it validates request bodies from type hints with Pydantic, injects the database connection with Depends(get_db) and generates /docs automatically. There is also a lot of online documentation to learn from.


Alternatives considered: Java (for example Spring Boot) was the most familiar syntax for me, but it needs more setup and boilerplate for a small app and a heavier build and deployment step, which did not fit a simple single-process project. Flask was very similar and lighter, but I would have written the validation and connection handling by hand. Django I had used in class, and it provides an ORM, migrations, an admin panel and a login system, but my app uses none of them: I wrote my own SQL in schema.sql, the tables are created on startup without a migration step, I built my own interface and I chose not to build login, so Django would only have added files and setup I did not use.


Consequences: My route functions are very small because FastAPI checks the incoming data and, through Depends, opens the database connection for me, which means less repeated code and dependencies that are easy to swap in tests; the API documentation page is also built automatically from the code. The cost was learning Pydantic, Depends and uvicorn (the server that listens for requests), which I had never actively worked with before, and getting as confident explaining Python as I am with Java.

## 2. Domain boundary: Kraal & Rama Management vs. Meeting & Decision Log
Date: 2026-09-19


Status: Decided


Context: The assignment asks to have 2 feature domains that will later become separate servicces, so I had to decide how to split my success criteria in 2 inside one SQLite schema. The 2 domains are: Kral and Rama management(it focuses on who is in the team) and then Meetings, Decision Logs and Actas(what is discussed and decided).



Decision: Domain 1 encapsulates rondas, volunteers, roles, ramas and rama_assignments whilst Domain 2 owns meetings, agenda_items, decisions and calendar_events. The only link between them is the ronda_id on the meetings and calendar_events. The code checks this in a single function: require_ronda.

Alternatives considered: I could have made volunteers and ramas two separate domains, but the roster and the continuity report always need both, so almost every use would cross the boundary. I could've also added an attendees table linking meetings to volunteers, which would provide real attendance data but it would add foreign keys from Domain 2 ito Domain1 thus spreading the coupling, so assigned_volunteer stays free text.

Consequences: In the case where the domains were split into two services, ronda_id would become a plain number and require_ronda would ask Domain 1over HTTP instead of querying the database. Since now these attributes would be seen as free test, there could be typos and no per-volunteer queries on events.


Revised 2026-10-04: At first the app only had this scope. After feedback in class that the project should be more ambitious, I added a treasury (budgets, requests, approvals and payments), named votes on decisions and "albergue" bookings. I put all of them in Domain 2 because they are about what the kraal decides and does with its resources in a ronda and they link to each other (a booking can point to the request that paid for it); a separate treasury domain would have needed its own seam to both other domains. Votes and the rule that only the treasurer can approve or pay need to know who is in the kraal and who holds a role, so the two domains now connect in three clearly separated ways:
1. In the code, through one file: src/actas/seam.py is the only file in Domain 2 that imports Domain 1. It answers three kinds of question: does this ronda exist (require_ronda), who is in the kraal this ronda (electorate, require_voter) and who holds a role (role_holders, require_role). No other file in src/actas touches Domain 1's tables.
2. In the database, through ronda_id: meetings, calendar_events and budgets keep a foreign key to rondas. votes.volunteer_id deliberately has no foreign key, because it is checked through the seam, like an id that would come from another service.
3. Through notices, by name only: notices live in src/messaging, shared infrastructure that belongs to neither domain. Domain 2 publishes to a topic such as ronda.5.rama.guias without knowing who is in that rama; Domain 1 decides who listens (topics_for_volunteer).
The cost is that the seam grew from one function to five, so Domain 2 depends more on Domain 1 than at the start. In a split, I would only rewrite seam.py (each function becomes one HTTP call), the ronda_id foreign keys would become plain numbers, and the topic names would stay the same.


## 3. Data model: ronda_id as anchor, with a denormalised copy on rama_assignments

**Status:** Superseded by [7]
Date: 2026-09-20


Status: Decided


Context: Everything the group does happens within a specific Guiding year, so both domains needed a common anchor. I also wanted the database itself to enforce that a volunteer is in at most one rama per ronda, because the continuity report gives a wrong answer if someone appears in two ramas in the same year.


Decision: The contents of each table are different for the different years: roles, ramas, meetings and calendar events change every year, so every one of these tables has a ronda_id as a foreign key to rondas. A UNIQUE rule can only look at columns in its own table, so rama_assignments repeats ronda_id and has UNIQUE (ronda_id, volunteer_id), which makes SQLite enforce the one-rama rule. Dates are stored as ISO YYYY-MM-DD text.


Alternatives considered: I could have made sure there is only one rama per person in the Python code instead of in the database schema, which would have avoided storing ronda_id twice. Still, I thought this was not as safe, since every function would have to remember to check this rule, and it could easily be forgotten. Another thing to think about was whether a date should be stored as a number (an epoch integer, the seconds since 1970). I chose ISO text (the international standard) because it is readable when I inspect the database, and it already sorts and compares correctly as text: the format goes from the biggest unit to the smallest and every part always has the same number of digits, so sorting the text alphabetically gives the dates in the right order. Impossible dates are rejected with date.fromisoformat before they are saved.



Consequences: The database guarantees the rule, so _volunteer_rama_map can safely map each volunteer to exactly one rama. The cost is that ronda_id is stored twice and the two copies could disagree, so assign_to_rama never asks the caller for the year: it only takes the rama and the volunteer, looks up the rama and copies the year from it.
Revised 2026-10-04: After the conversation with my professor (who thought my first design was too simple), the schema grew from 9 to 16 tables: budgets, budget_requests and request_events (treasury), votings and votes (named votes), bookings (albergues) and notices (live notices). I kept the same two principles (ronda_id as the anchor and rules enforced by the database, not only by Python) and made five new decisions:
1. Only new tables, never altering the ones that already exist. For example, "a vote is open on this decision" is a separate votings table instead of new columns on decisions. Because every table uses CREATE TABLE IF NOT EXISTS, an existing database gets the new tables automatically when the app starts, with no migration step (§7.4).
2. One-to-one rules through primary keys. A primary key is the column that identifies each row and can never be repeated, so making decision_id the primary key of votings means a decision can have at most one vote, and making event_id the primary key of bookings means an outing has at most one booking. UNIQUE (decision_id, volunteer_id) on votes means one vote per person.
3. Money is stored in integers (cents), so we always store whole numbers and not decimals, to avoid floating point operations that can make the amounts inexact (0.1 + 0.2 is not exactly 0.3).
4. Append-only history: rows in request_events are never deleted or changed, only new rows are added. Since nobody can edit or erase them, the history is trustworthy, so it works as the payment receipt and leaves a record of everything that is approved and paid.
5. Deliberate missing links: some columns don't have foreign keys on purpose. votes.volunteer_id has none because volunteers belong to Domain 1, so instead of linking the tables, Domain 2 checks the person through seam.py. budget_requests.rama is free text for the same reason, and notices has no foreign keys at all because it belongs to neither domain.
The cost of never altering tables is that a fix to an existing table does not reach databases that were already created: when I fixed the typo NNOT NULL in budget_requests, my old local database kept the broken column until I deleted it. The database diagram in the README shows all 16 tables and matches schema.sql.


## 4. Testing Approach
Date: 2026-09-25
Status: Decided
Context: The assignment specifies that at least 70% of the business logic should be covered, measured with a standard tool and that routing or framework glue does not count toward that bar.



Decision: Coverage was scoped out of the two service files, and wrote one test for every rule I could find. For example duplicate labels,  to the two service files(python -m pytest --cov=src.kraal.service --cov=src.actas.service --cov-report=term-missing), which hold every business rule, and wrote one test per rule I could find: duplicate labels, blank names, duplicate roles, invalid availability, one-rama-per-ronda, invalid and out-of-range dates, and the continuity report's join/leave/stay/move logic including its not-found guards. Measured result: 91% overall (Kraal 95%, Actas 85%), both above the 70% bar. I also kept a handful of API-level tests (test_api.py) that exercise the same rules through real HTTP, to prove the central DomainError handler maps each error to the right status code.

Alternatives considered: I could have tested every route directly with FastAPI's TestClient in detail, but that would mostly test that FastAPI itself works rather than my own logic, and the assignment says routing does not count toward the bar. The database could've been mocked instead of using a real in-memory SQLite connection per test, but a real connection tests the actual SQL and constraints, not just my Python, at a negligible extra cost given SQLite's :memory: mode.


Consequences: The remaining uncovered lines are mostly single validation branches and one sqlite3.IntegrityError catch block that is hard to trigger honestly, since the Python-level check in front of it already rejects the same bad input. Coverage also caught a real bug: continuity_report and _volunteer_rama_map had been accidentally duplicated in the file, and the first copy was silently shadowed and never executed; removing it raised Kraal's coverage from 74% to 95% by deleting 36 lines of dead code rather than adding tests.

Revised 2026-10-04: As the app grew, I kept the same approach (one test per rule, a real in-memory database, no mocks of SQLite) and applied it to the new modules, so coverage now spans ten business-logic files: 99% overall with 137 tests, using the full command in the README. The new features needed four new techniques:
1. Boundary values: rules are tested exactly at the limit and one step past it, for example a request for exactly the remaining budget, one cent over it, or an availability of 0 and 100.
2. Injected time: votes take now= and bookings take today=, so "you cannot vote after the closing time" or "remind once a day" are tested with fixed dates instead of waiting.
3. Fakes instead of the real broker: RecordingNotifier and FakeBroker record what would have been sent, so treasury and notice rules are tested without a running event loop.
4. Test data that tells cases apart: the test treasurer is called Marta, not "Tesorera", so a test can prove the history records the person and not the role.
What I deliberately left thinner: the live notice stream and the booking reminder loop are thin wrappers around tested functions (notices_since, the broker, send_reminders), so I checked them by running the server instead of unit-testing them, and the web page is checked by hand. This had a cost: a review of the whole app found a duplicated submit_request route that silently replaced the one that sent notices, which my service tests could not see because it was in the routing; I fixed it and added API tests that check the notifications through HTTP.


## 5. Deliberately not built: login and user accounts
Date: 2026-10-04


Status: Decided


Context: This app would have about 20 users who all know each other and it runs as a single process on one machine. In our kraal there is full transparency over who does what: roles are shared and no individual person has more power than the rest; a role just means someone generally takes care of that task. Some features now depend on who is acting, for example the named votes and the rule that only the treasurer is allowed to approve or pay requests.


Decision: I didn't build login or user accounts. Each person chooses who they are, and the server still makes sure the business rules are applied to that volunteer id: only the treasurer of the ronda can approve, reject or pay (403 otherwise), each person votes once, and only kraal members can vote. What we need is a system that keeps track of decisions and of who is responsible for each task, not one that stops people from acting.


Alternatives considered: Real accounts with passwords would make identity trustworthy, but they need password storage, sessions, password resets and a login page, which is a lot of work and security risk for 20 people and not what this assignment is about. Logging in with Google accounts would avoid storing passwords, but it would make the app depend on an external service at runtime, which the deployment contract (§7.6) does not allow. A single shared password in an environment variable would keep strangers out, but it would not tell the volunteers apart, so it would not protect the votes or the treasurer rule. A personal access link for each volunteer (a random code in the link) is the cheapest real step, and it is what I would add first. In the future I will outsource this, but I personally believe that manually coding a login page is not essential.


Consequences: Anyone who can open the page can act as anyone (approve as the treasurer, vote as another person or read another rama's notices), so the rules protect against mistakes, not against someone pretending to be someone else; but the nature of the people using the app (a group of friends who need to coordinate things) this really not that big of a deal. Before the app is deployed beyond a local network in Assignment 2, authentication has to be added first.


# Assignment 2

## ADR-6: Split into two services

**Date:** 2026-11-12
**Status:** Accepted

### Context
Assignment 2 requires that I containerise the application in 2 containers: 2 services, each inside its own container with its own database, that communicate over HTTP.

In the first assignment, seam.py was the only file in Actas that imported Kraal, and ADR-2 predicted that if the app was split, only that file would change into HTTP calls. Messaging was not as well defined: it was a shared package (src/messaging) that belonged to neither domain. Two containers cannot share a package, and a third container is not allowed, so it had to go into one of the two services.

When I split the code, I also found that Kraal itself used the messaging package: topics_for_volunteer built the notice topics, and role_holder_ids used slug to compare role names. I had not noticed this in the first assignment because everything ran in one process.

### Decision
I created 2 services, kraal and actas, split along seam.py.

Messaging goes in actas because that is where messages are sent from: the treasury, the votes and the hostel reminders all publish notices, and they are all in Actas. This way sending a notice is still a normal function call inside the same service. If messaging was in kraal, every notice would become an HTTP call across the seam.

To make kraal stop depending on messaging, I copied slug into kraal and removed topics_for_volunteer. Actas will build the topics itself, using the volunteer's rama and roles that it asks kraal for over HTTP.

db.py, errors.py and validation.py are copied into each service, because each container only contains its own folder and cannot import code from the other one.

Only actas calls kraal. Kraal never calls actas.

### Alternatives considered
- Messaging in kraal: every notice published by Actas would have to cross the seam over HTTP, so the calls would go in both directions and notices would fail whenever kraal is down.
- Messaging as a third service: the assignment allows exactly 2 service containers.
- A shared Python package used by both services: each image is built only from its own service folder, so it cannot reach a package outside it. It would also tie the two services together, since a change to the package would affect both.
- Moving the seam somewhere else: seam.py already worked as the boundary, and the only problem was messaging, so moving messaging was enough.

### Consequences
This has allowed me to deploy the two services independently and to establish a one-way dependency, meaning that kraal works even if actas is down.

The costs are that the copied code (slug, errors, db helpers) can drift apart if I change it in one service and forget the other, and that what used to be function calls through seam.py are now network calls, which can be slow or fail. That is why every call to kraal needs a timeout and a clear error when kraal is unavailable.

ADR-2 almost held: seam.py was still the only file in Actas that needed Kraal, but Kraal depended on the shared messaging package, which I only discovered when splitting.



## ADR-7: Data and Migrations

**Date:** 2026-11-16
**Status:** Accepted


### Context
In the first assignment all the data lived in one SQLite file and the schema was created on every start with CREATE TABLE IF NOT EXISTS (ADR-3). That only allowed adding new tables, never changing existing ones. Assignment 2 requires one SQL Server database per service, each with its own login that cannot access the other database and versioned migrations that change the schema without losing data.

### Decision
**One database per service.** Kraal owns rondas, volunteers, roles, ramas and rama_assignments. Actas owns the other 11 tables (meetings, agenda, decisions, calendar, the treasury tables, votes, bookings and notices). Locally both databases live in one SQL Server container; on Azure they are two serverless databases on one logical server. Each service has its own login (kraal_app, actas_app) with db_owner rights only on its own database. I checked this with sqlcmd: kraal_app can open kraal but gets "Cannot open database actas".

**Integrity lost at the seam.** Three foreign keys pointed to Kraal's rondas table: meetings.ronda_id, calendar_events.ronda_id and budgets.ronda_id. A database cannot check a foreign key against a table in another database, so they became plain ids, like votes.volunteer_id already was. The treasury also read the volunteer's name directly from Kraal's volunteers table; it now gets it from the membership endpoint. I compensate in code: writes check the ronda over HTTP before saving (require_ronda), so a new row never gets a ronda_id that does not exist. Reads only check it when Kraal answers. Nothing re-checks the ids afterwards, but the app has no operation to delete a ronda, so a row cannot lose its ronda later.

**No data moved.** The SQLite database from the first assignment only had demo data, so both services start with empty databases instead of using an export/import script.

**Migrations with my own runner.** Each service has a migrations/ folder with numbered SQL files (001_init.sql, ...). At startup, migrate.py creates a schema_migrations table if it is missing, compares it with the files, and applies only the missing ones in order. Each migration runs in one transaction together with the row that records it, so it is applied completely or not at all. If it fails, it is rolled back and the service refuses to start. It logs "Applied migration 001_init" the first time and "No pending migrations" on every start after that. Applied migrations are never edited: a correction is a new file.

**Porting from SQLite to SQL Server.** I kept the code's sqlite3 style (conn.execute with ? placeholders) with a small adapter in db.py, so only the SQL dialect had to change. The main changes were: INT IDENTITY instead of AUTOINCREMENT; NVARCHAR with a bounded length for every column in a UNIQUE (SQL Server cannot index NVARCHAR(MAX)); dates kept as ISO text and booleans as INT so the API returns the same values as before; CONVERT(NVARCHAR(19), SYSUTCDATETIME(), 120) instead of datetime('now'); [rule] in brackets because RULE is a reserved word; every selected column listed in GROUP BY; and the new id read with SCOPE_IDENTITY() in the same batch as the INSERT, because pymssql's lastrowid returned the wrong id. The tests on SQL Server found that last bug.

### Alternatives considered
- Alembic or an ORM: they would hide the SQL differences, but I would have to explain a much larger tool line by line. My runner is about 40 lines and I can explain all of it.
- Keeping the ronda foreign keys by copying the rondas table into actas: the two copies could disagree, and actas would be reading data it does not own.
- Moving the old SQLite data with a script: not worth it for demo data.
- Using DATE and BIT types: more correct for SQL Server, but they change what the API returns and how dates are compared, and this assignment asks for no new features.

### Consequences
Referential integrity across the seam is now enforced in code at write time, not by the database. If someone deleted a ronda directly in Kraal's database, actas rows could point to a ronda that no longer exists.

SQL Server's default collation is case-insensitive, so UNIQUE (ronda_id, role_name) now treats "Tesorera" and "tesorera" as the same role. This fixes half of defect 2 from my review; accents are still compared exactly.

Recovery plan for a bad migration: because each migration runs in a transaction, a migration that fails leaves the database unchanged, and the service does not start, so the post-deploy health check fails. I fix it with a new corrective migration, never by editing the applied one. If a migration succeeds but damages data, I restore the database from Azure SQL's automatic point-in-time backup into a new database and point DATABASE_URL at it.

## ADR-8: Serverless hosting on Azure

**Date:** 2026-11-19
**Status:** Accepted

### Context
Assignment 2 requires deploying both services and the UI to Azure on resources billed per use, scaling to zero when idle, with the deployment done only by the pipeline. On 17 November the professor moved Assignment 2 to each student's own Azure for Students subscription and published an A2 deployment guide, which changes several details of section 7 of the assignment (listed under "Deviations" below).

### Decision
**Resources**, all in my own resource group rg-oespineira-ieu2024, in swedencentral (one of the five regions my subscription's policy allows; spaincentral does not have the SQL free offer):
- a Storage account (oespineiraieu2024ui) serving the UI as a static website. Its address is the system's public URL and the only origin CORS accepts;
- a Container Apps environment (Consumption) with one Container App per service, external HTTPS ingress, 0 to 1 replicas, 0.25 vCPU and 0.5 GiB;
- one logical SQL server with two serverless databases on the free offer (0.5 to 1 vCore, 32 GB, locally redundant backups, auto-pause after 60 minutes), each with one contained user that has only db_ddladmin, db_datareader and db_datawriter;
- a user-assigned managed identity for the pipeline, with Contributor on this resource group only, trusted through OIDC for pushes to main. No Azure password is stored anywhere;
- images on GHCR, tagged with the commit SHA.
Every setup command is in infra/setup.sh. After the setup, only the pipeline changes anything.
- the GHCR packages are public (they inherited the public repository's visibility), so Container Apps pull the images without registry credentials. The guide's expected first-deploy failure ("Authentication failed when pulling container image") did not happen.

**Cost model.** Container Apps on Consumption bill per second while a replica runs, and nothing at zero replicas. The databases use the free offer, and auto-pause when idle. The storage account costs cents. An idle system uses almost none of the credit.

**Scale to zero and cold starts.** After a period without requests, Container Apps stops the replica, and after 60 minutes without connections the database pauses. The first request after that has to start the container and may find the database resuming, which takes up to about a minute, with connections failing meanwhile (error 40613; I saw it while creating the users). So:
- at startup, wait_for_db retries with backoff for up to 90 seconds, then runs the migrations;
- every request's connection retries a few times with backoff;
- while the container starts, Azure answers 503 "App port is not ready"; the UI recognises that 503 (it has no detail field) and shows "El servicio está arrancando", retrying twice;
- the CD health check waits up to five minutes per service.

**Migrations at startup, with one replica.** Each service runs its migrations when it starts. Max replicas is 1, so two copies can never run the same migration at the same time.

**Load balancing, routing, DNS, TLS and firewalls.** I did not build these myself, because the assignment rules out VMs and a third container. Azure provides them: the Container Apps ingress terminates HTTPS and routes each request to a healthy replica (with one replica it has a single target, but it would balance across many); each app gets a DNS name in the environment's domain (politeforest-d654a89b.swedencentral.azurecontainerapps.io); the SQL firewall only allows Azure services, plus my own IP while I set up the users. CORS is set in the services' code (as the guide says), and only protects against browsers, not other clients.

**Deployment strategy.** Each deploy updates the Container App to the new image, which creates a new revision that replaces the old one. The pipeline only passes if both /health endpoints report the new commit; if not, it puts the previous images back (an automatic rollback). Because the old revision can still run for a moment after the new one has migrated the database, every migration must stay backward-compatible with the previous code.

**Public without login.** The live system is public and has no authentication, which ADR-5 said should come before going beyond a trusted network. I accept this because it only holds demo data. Real data would need authentication first (see ADR-10 for what was not built).

**Deviations from the assignment text** (following the A2 deployment guide and the announcement of 17 November): my own resource group instead of rg-sdd-3a; a managed identity with OIDC instead of the class service principal; a Storage static website instead of a Static Web App; the SQL free offer (60-minute auto-pause, 32 GB) instead of the shortest auto-pause and 2 GB.

### Alternatives considered
- A Static Web App for the UI (the assignment text): replaced by the guide's Storage static website.
- A service principal with a stored secret: IE accounts cannot create one, and OIDC stores no secret that could leak.
- Terraform instead of an az CLI script: credited as IaC, but the guide asks for the commands in the README, and on deployment day the CLI was the lower-risk way to get the migration evidence on time.
- A Log Analytics workspace for the logs: an extra resource billed per GB. I read the logs with az containerapp logs show instead.
- Blue/green or canary releases with two active revisions and traffic splitting: they would need two replicas running against the same database, against the one-replica rule, and migrations compatible with both versions at once. The automatic rollback gives a safe way back without them.
- Ansible to configure servers: there are no servers to configure; the containers are built from Dockerfiles.

### Consequences
The first request after an idle period is slow (up to about a minute when the database is also paused). That is accepted by the assignment, and the UI shows a clear message.

The live notices stream is an open HTTP connection, so while any browser tab has it open, the actas replica cannot scale to zero, and costs credit. The hostel reminder loop only runs while the actas replica is awake, so reminders are best effort.

The in-memory broker only works because there is exactly one actas replica.

At 100x traffic, I would need: more replicas behind the ingress, which needs an external broker for the notices (or polling) and sticky sessions or polling for the stream; the migrations as a separate pipeline step, not at startup, so several replicas don't race; connection pooling; a provisioned database instead of serverless, to avoid pauses; and a scheduled job for the reminders.

ADR-5 is superseded by this ADR.

## ADR-9: Pipelining and Testing

**Date:** 2026-11-17
**Status:** Accepted


### Context
In the first assignment the tests ran on an in-memory SQLite database (ADR-4). Assignment 2 requires CI on every push and pull request: lint, unit tests per service, at least 70% coverage per service, validation of system.yaml and the OpenAPI documents and a build of every image. The tests must run against a SQL Server container, never Azure SQL and at least one integration test must cross the seam between the two services.

### Decision
**One workflow** (.github/workflows/ci-cd.yml) this runw on every push and pull request, with three jobs:
- **test**, once per service: ruff lint and format check, the tests on SQL Server with a coverage gate that fails under 70% and a docker build of the image.
- **validate**: system.yaml against system.schema.json, and both openapi.json files against the OpenAPI specification.
- **integration**: only after both test jobs pass. It starts the whole system with docker compose and runs the communication seam tests against the real services.

Every job has a time limit. The actions and the tools are pinned to a version, so runs are reproducible. main is protected: changes arrive only through pull requests and all four checks must pass before merging.

**Tests run on SQL Server, not SQLite.** CI starts SQL Server with the same docker-compose.yml and db/init.sql I use locally. The tests use separate databases (kraal_test, actas_test) and refuse to run unless the name ends in _test, because they empty every table before each test. The migrations run once per test session, so every run also proves them. The passwords in CI are the dev-only defaults from docker-compose.yml, for a container that only lives a few minutes on GitHub's runner, so they are not secrets.

**How the cross-seam tests work, at three levels:**

1. Unit tests with a fake kraal:
   - actas tests don't call the real kraal: a FakeKraal in conftest.py replaces _kraal_get with monkeypatch
   - the fake has the same method names as kraal's service (create_ronda, add_volunteer...), so the tests barely changed
   - it returns the same shapes as the real kraal endpoints (I fixed /roles to include volunteer_name to match)
   - autouse=True: every actas test gets the fake automatically, so no test can make a real network call by accident (this happened: a test without the fake tried to reach http://kraal:8000)
   - kraal.down = True simulates kraal being unavailable: test_kraal_down_writes_fail_with_503_but_reads_still_work
2. The real HTTP code: test_seam.py tests the real _kraal_get with only httpx.get replaced: it uses KRAAL_URL and KRAAL_TIMEOUT_S, a 404 stays a 404, and a timeout, a refused connection or a 500 become a 503.
3. The real system: the integration job starts everything with compose. One test creates kraal data over HTTP and checks that actas builds the right notice topics from it, which only works if actas really called kraal. The other stops the kraal container and checks that actas's /health stays 200, the cross-seam flow returns the 503 message, and actas's own data still reads.

Each service also has a test that fails if its committed openapi.json no longer matches the code.

### Alternatives considered
- Keeping SQLite for the tests: faster, but it hid real differences. Testing on SQL Server found three bugs: pymssql's lastrowid returning another table's id, a GROUP BY that SQL Server rejects, and a too-long value giving a 500 instead of a clear error.
- A GitHub Actions service container for SQL Server: it works, but then CI would set up the database differently from my laptop. Reusing docker-compose.yml means one setup, tested everywhere.
- Only the fake, or only the compose stack: the fake is fast but never tests real HTTP or the containers; the compose stack is realistic but slower and cannot easily simulate a timeout. I use both.

### Consequences
Running the tests now needs Docker, and each test job takes about a minute in CI. Coverage is 92% for kraal and 94% for actas.

The fake has to stay in step with kraal's real API. If they drift apart, the unit tests could still pass, but the integration job would fail, so the mismatch is caught before merging.

The schema used for system.yaml is a stand-in written from section 8a, because the provided one was not available.

**Deliberately not tested:**
- Azure-specific behaviour (cold starts, the database resuming from pause, real secrets and ingress): the post-deploy health check covers these after each deployment.
- The browser UI: checked by hand, including the banner when kraal is down.
- The live notice stream over a real browser connection: the broker, topics and backlog are unit-tested.
- The reminder loop's timing: send_reminders is tested with an injected date, but not the hourly loop.
- Load and performance.

ADR-4 is superseded by this ADR.

To keep actas working when kraal is down, I separated two kinds of ronda checks. Writes (creating a meeting, a calendar event, a budget or a notice) use a strict check: if kraal does not answer, they fail with a 503, because saving a ronda_id that might not exist would store bad data. Reads (listing meetings, the calendar, budgets, requests and bookings) use a best-effort check: they check the ronda when kraal answers, but if kraal is down they still return actas's own data, because a read cannot corrupt anything. treasury_info stays strict even though it is a read, because its whole answer (who the treasurer is) comes from kraal.

The notice stream degrades instead of failing: if kraal is down, actas cannot know the volunteer's rama and roles, so it only subscribes them to the whole-kraal notices.

The seam kept the same function names and parameters as in the first assignment, including the conn parameter, which is not used anymore. Because of this, none of the files that call the seam had to change, which is what ADR-2 promised.

- actas tests don't call the real kraal: a FakeKraal in conftest.py replaces _kraal_get with monkeypatch
- the fake has the same method names as kraal's service (create_ronda, add_volunteer...), so the tests barely changed
- it returns the same shapes as the real kraal endpoints (I fixed /roles to include volunteer_name to match)
- autouse=True: every actas test gets the fake automatically, so no test can make a real network call by accident (this happened: a test without the fake tried to reach http://kraal:8000)
- kraal.down = True simulates kraal being unavailable: test_kraal_down_writes_fail_with_503_but_reads_still_work
- what the fake doesn't test: the real HTTP call in _kraal_get (timeouts, real 404s) → integration test on Friday