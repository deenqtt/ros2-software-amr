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
```

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

## What is deliberately different from the old backend

Each of these fixes a specific defect recorded in
[`docs/WEB_UI_REDESIGN_AUDIT.md`](../../docs/WEB_UI_REDESIGN_AUDIT.md).

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

**There is still no authentication.** Naming CORS origins narrows the blast radius but
does not close it. Before this leaves a trusted network it needs a real auth story,
and so does rosbridge.
