## 1. Backend language and framework: Python with FastAPI
Date: 17-09-2026
Status: Decided
Context: The app has to run as one process with SQLite and two feature domains, and I have to be able to explain all of the code myself in a closed-book check. I first had to choose between Java, which I know best, and Python, and then between Flask, FastAPI and Django.
Decision: I chose Python with FastAPI. Python has SQLite built into its standard library, needs no compile or build step, and is simple to connect to external tools and to the later Azure deployment. FastAPI gives me request validation from type hints, a database connection opened and closed per request with Depends(get_db), and automatic /docs, and it has plenty of documentation and examples to learn from.
Alternatives considered: Java (for example Spring Boot) was the most familiar syntax for me, but it needs more setup and boilerplate for a small app and a heavier build and deployment step, which did not fit a simple single-process project. Flask was very similar and lighter, but I would have written the validation and connection handling by hand. Django I had used in class, but with a small schema I would have been paying for an ORM, admin and auth that this app does not need.
Consequences: I write less boilerplate and get the API docs for free, and FastAPI leaves room to grow without switching frameworks. The cost is that I have to learn Pydantic models, dependency injection and running the app with uvicorn, and I have to explain Python as confidently as I could Java.

## 2. Domain boundary: Kraal & Rama Management vs. Meeting & Decision Log
Date: 19-09-2026
Status: Decided
Context: The assignment requires two feature domains that could later become separate services, so I had to decide where to draw the line inside one SQLite schema. The domains are Kraal & Rama Management (who is on the team each year) and the Meeting & Decision Log (what was discussed and decided).
Decision: Domain 1 owns rondas, volunteers, roles, ramas and rama_assignments, and Domain 2 owns meetings, agenda_items, decisions and calendar_events. The only link between them is ronda_id on meetings and calendar_events, and the code checks it in a single function, _require_ronda.
Alternatives considered: I could have made volunteers and ramas two separate domains, but the roster and the continuity report always need both, so almost every use would cross the boundary. I could also have added an attendees table linking meetings to volunteers, which gives real attendance data, but it adds foreign keys from Domain 2 into Domain 1 and spreads the coupling, so assigned_volunteers stays free text.
Consequences: ronda_id is still a real dependency (a foreign key today); in a split it would become a plain number and _require_ronda would ask Domain 1 over HTTP instead of querying the database. Free text means typos and no per-volunteer queries on events, but no coupling to the volunteers table.

## 3. Data model: ronda_id as anchor, with a denormalized copy on rama_assignments
Date: 2026-09-20
Status: Decided
Context: Everything the group does happens within a specific Guiding year, so both domains needed a common anchor. I also wanted the database itself to enforce that a volunteer is in at most one rama per ronda, because the continuity report gives a wrong answer if someone appears in two ramas in the same year.
Decision: Every year-scoped table (roles, ramas, meetings, calendar_events) carries a ronda_id foreign key to rondas, and rama_assignments repeats ronda_id with UNIQUE (ronda_id, volunteer_id) so SQLite enforces the one-rama rule. Dates are stored as ISO YYYY-MM-DD text.
Alternatives considered: I could have enforced the one-rama rule only in Python and left the extra column out, which avoids duplicated data, but the rule would then hold only as long as every code path remembers to check it. I could also have stored dates as epoch integers, but ISO text is readable when I inspect the database, sorts and compares correctly as text, and is validated with date.fromisoformat.
Consequences: The database guarantees the rule, so _volunteer_rama_map can safely map each volunteer to exactly one rama. The cost is that ronda_id is stored twice and could disagree with ramas.ronda_id, so assign_to_rama copies it from the rama row instead of accepting it as a parameter.

## 4. Testing Approach
Date: 2026-09-23
Status: Decided
Context: The assignment requires at least 70% coverage on core business logic, measured with a standard tool and covering routing/framework glue was explicitly out of scope.
Decision: I scoped coverage to the two service files(python -m pytest --cov=src.kraal.service --cov=src.actas.service --cov-report=term-missing), which hold every business rule, and wrote one test per rule I could find: duplicate labels, blank names, duplicate roles, invalid availability, one-rama-per-ronda, invalid and out-of-range dates, and the continuity report's join/leave/stay/move logic including its not-found guards. Measured result: 91% overall (Kraal 95%, Actas 85%), both above the 70% bar. I also kept a handful of API-level tests (test_api.py) that exercise the same rules through real HTTP, to prove the central DomainError handler maps each error to the right status code.
Alternatives considered: I could have tested every route directly with FastAPI's TestClient in detail, but that would mostly test that FastAPI itself works rather than my own logic, and the assignment says routing does not count toward the bar. I could also have mocked the database instead of using a real in-memory SQLite connection per test, but a real connection tests the actual SQL and constraints, not just my Python, at negligible extra cost given SQLite's :memory: mode.
Consequences: The remaining uncovered lines are mostly single validation branches and one sqlite3.IntegrityError catch block that is hard to trigger honestly, since the Python-level check in front of it already rejects the same bad input. Coverage also caught a real bug: continuity_report and _volunteer_rama_map had been accidentally duplicated in the file, and the first copy was silently shadowed and never executed; removing it raised Kraal's coverage from 74% to 95% by deleting 36 lines of dead code rather than adding tests.


