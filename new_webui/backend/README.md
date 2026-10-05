# AMR Backend

Fleet registry and persistence for the AMR control interface. FastAPI + SQLite.

Runs on **port 3002**, alongside the existing backend on 3001. The old service in
[`../../backend/`](../../backend/) is untouched and still serves the current web UI.

---

## Run it

First time only:

```bash
cd new_webui/backend
python3 -m venv .venv
./.venv/bin/pip install -e ".[dev]"
cp .env.example .env
./.venv/bin/python -m app create-admin <your-name>   # asks for a password
```

There is no default password and no sign-up page. The first super admin comes
from one of:

- **`.env` on a new server:** set `AMR_BOOTSTRAP_USER` and `AMR_BOOTSTRAP_PASSWORD`.
  On a database with no accounts, that account is created at startup and has to
  choose its own password at first sign-in. Once anyone exists the variables are
  ignored, so remove them after that first sign-in.
- **The CLI on the server:** `create-admin <name>`. `create-admin <name> --reset`
  makes an existing account an enabled super admin with a new password — the way
  back in when every super admin has forgotten theirs.

The super admin makes everyone else from the Users screen. Every password set
there is temporary: the person replaces it the first time they sign in, and until
then the API refuses everything but that (403, `code: password_change_required`).

Then, every time:

```bash
./.venv/bin/python -m app --reload
```

Or activate the venv once and drop the path prefix:

```bash
source .venv/bin/activate
python -m app --reload        # `amr-backend --reload` also works
```

Host and port come from `.env`; `--host` and `--port` override them.
Interactive API docs at `http://localhost:3002/docs`.

> `python app/main.py` does **not** start anything — `main.py` is the app
> factory, and running it directly used to exit 0 having done nothing, which
> looks exactly like success. It now refuses and points at the right command.

```bash
./.venv/bin/python -m pytest      # 32 tests
./.venv/bin/ruff check .
```

## Layout

```
app/
├── asgi.py          ASGI entry point — the only module that builds an app
├── main.py          create_app() factory; importing it has no side effects
├── config.py        settings, entirely from the environment
├── db.py            connection pragmas + the migration runner
├── migrations/      numbered .sql files, applied in order and recorded
├── api/             routers; deps.py holds the request-scoped connection
├── schemas/         pydantic request/response models
└── repositories/    all SQL lives here and nowhere else
```

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | Liveness only. Says nothing about the database. |
| GET | `/ready` | Readiness: the database answers and reports its schema version. |
| GET | `/api/robots` | Ordered by name, case-insensitively. |
| POST | `/api/robots` | 201 on success, **409** on a duplicate name or bridge. |
| GET | `/api/robots/{id}` | |
| PATCH | `/api/robots/{id}` | Partial. Omitted ≠ null — see below. |
| DELETE | `/api/robots/{id}` | 204. |

## Sign-in, roles and audit

Every endpoint except `/health` and `/ready` needs a signed-in person, through an
HttpOnly session cookie set by `POST /api/auth/login`. Four roles, each including
the one before:

| Role | May |
|---|---|
| viewer | read everything: fleet, maps, stations, zones, missions, run history |
| operator | + start, stop and cancel runs; switch a robot's mode |
| admin | + edit maps, stations, zones, missions and robots |
| super_admin | + manage accounts; read the audit trail |

Upgrading from the three-role version makes every existing admin a super admin
(migration 009), so nobody loses access to the Users screen.

The guard each route needs is declared on the route (`dependencies=[Admin]` …) or
its router, from `app/auth.py`; nothing checks a role inside a handler.

- A session ends after `AMR_SESSION_IDLE_MINUTES` without a request (12 h: one shift).
- Five wrong passwords for one name from one address pause that name for five minutes.
- "No such user" and "wrong password" get the same answer, in the same time.
- Every change made through the API, and every sign-in attempt, is written to
  `audit_log` with who, what, when, the result and the address (`GET /api/audit`,
  super admin). Agent progress reports are not: the run already records them.
- Runs record who pressed Run (`started_by`).

**Robot agents** do not sign in yet. While `AMR_AGENT_AUTH=optional` (the default),
the endpoints an agent uses answer without credentials — reads, `PUT /robots/{id}/mode`
and `/map`, `PATCH /runs/{id}`, `POST /maps` — and anything else is refused. That
is a known gap until agents carry a token; `required` closes it and stops agents.

**rosbridge is still unauthenticated.** Signing in to this API protects this API.
The browser talks to each robot's rosbridge directly, and anyone who can reach that
port can still publish to it; until it is proxied, keep robots on a network the
plant controls.

## What is deliberately different from the old backend

Each of these fixes a specific defect found in the old backend (since removed; its
audit is in git history as `docs/WEB_UI_REDESIGN_AUDIT.md`).

**Robots are a table, from the first migration.** The old schema had six tables and
not one robot reference; a robot was an implicit singleton defined by a build-time
`VITE_ROS_URL` in the frontend. Ids are UUID text rather than autoincrement integers,
because registries get merged across machines and two sites both holding "robot 3" is
a bad day.

**PATCH, not PUT — omitted is not null.** Omitting a field leaves it alone; sending
an explicit `null` clears it. The old API used PUT with a full model, so any field a
client forgot to resend was reset to its default. That is how changing a destination's
type silently wiped its orientation.

**Unknown fields are rejected, not dropped.** Pydantic ignores unknown keys by
default, which is why missions lost `station_id` and `dest_point` and docks lost their
entire approach pose — silently, on every write. `extra="forbid"` turns that into a
422 the client can see.

**Migrations are numbered, ordered and recorded.** The old code ran `ALTER TABLE`
statements inside `try/except Exception: pass`, so a migration that failed for a real
reason looked identical to one already applied. Each migration here runs in its own
transaction with its bookkeeping row, so it applies completely or not at all.

**Reads never mutate.** `GET /api/maps` used to scan the filesystem and delete rows
whose file was missing, which — through `ON DELETE CASCADE` — destroyed every keepout
zone, dock and destination attached to that map. An engineer renaming a `.yaml` lost
an operator's work. Scanning will be an explicit operation here.

**Uniqueness is enforced by the database.** Name is unique `COLLATE NOCASE`, bridge
URL is unique. Two robots sharing a name is how an operator ends up driving the wrong
one; it is not left to every caller to remember to check.

**CORS comes from the environment, and production refuses a wildcard.** The old
service shipped `allow_origins=["*"]` with no authentication, on a host-network
container next to an unauthenticated rosbridge — anyone with network reach could drive
the robot and delete its maps.

## Not built yet

Maps, missions, stations, keepout zones and alarms. The old backend still owns those;
its code is in [`../../backend/`](../../backend/) and is the reference for the ROS
contract those endpoints have to keep.

**Agent credentials and rosbridge.** People sign in (see above); robot agents and
rosbridge do not yet. Both are next.
