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

## ADR-9

To keep actas working when kraal is down, I separated two kinds of ronda checks. Writes (creating a meeting, a calendar event, a budget or a notice) use a strict check: if kraal does not answer, they fail with a 503, because saving a ronda_id that might not exist would store bad data. Reads (listing meetings, the calendar, budgets, requests and bookings) use a best-effort check: they check the ronda when kraal answers, but if kraal is down they still return actas's own data, because a read cannot corrupt anything. treasury_info stays strict even though it is a read, because its whole answer (who the treasurer is) comes from kraal.

The notice stream degrades instead of failing: if kraal is down, actas cannot know the volunteer's rama and roles, so it only subscribes them to the whole-kraal notices.

The seam kept the same function names and parameters as in the first assignment, including the conn parameter, which is not used anymore. Because of this, none of the files that call the seam had to change, which is what ADR-2 promised.

- actas tests don't call the real kraal: a FakeKraal in conftest.py replaces _kraal_get with monkeypatch
- the fake has the same method names as kraal's service (create_ronda, add_volunteer...), so the tests barely changed
- it returns the same shapes as the real kraal endpoints (I fixed /roles to include volunteer_name to match)
- autouse=True: every actas test gets the fake automatically, so no test can make a real network call by accident (this happened: a test without the fake tried to reach http://kraal:8000)
- kraal.down = True simulates kraal being unavailable: test_kraal_down_writes_fail_with_503_but_reads_still_work
- what the fake doesn't test: the real HTTP call in _kraal_get (timeouts, real 404s) → integration test on Friday