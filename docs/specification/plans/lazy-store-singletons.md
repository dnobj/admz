# Plan: stores must resolve their DB path at call time (GH #258)

## Context

Seventeen SQLite-backed stores share one shape: a module-level singleton whose `__init__` resolves
`_default_db_path()`, caches it in `self._db_path`, and immediately calls `_ensure_table()` — which
connects. Two consequences follow, and #254 fixed only the first:

- **Import does I/O.** On a machine with no `ADMZ_HOME`, thirteen of them connected at import and the
  first one imported killed the process (`unable to open database file`). #254 stopped the crash by
  making every site call `paths.ensure_admz_home()` / `ensure_parent_dir()`. It did not stop the I/O.
- **The path is frozen.** Once resolved, it never changes, so an environment set afterwards is
  ignored. This is why `tests/conftest.py` has to redirect `ADMZ_HOME` *before* pytest collects
  anything (#257), and why `CLAUDE.md`'s instruction — *"if you add a writer, prove it cannot reach a
  real DB from a test run"* — cannot currently be satisfied structurally.

#258 proposed extending the H-2 lazy-singleton idiom (`session_store.py:209`: *"importing a module
must not create `~/.admz/admz.db` as a side effect"*) to the remaining stores, at ~110 module-level
import sites, and picking a winner between the two in-repo lazy idioms.

**The exploration pass disproved the premise.** Laziness does not fix the second consequence, the
~110 call sites are not required at all, and the two idioms the issue asks us to choose between are
both answers to the wrong question. This plan carries that diagnosis forward.

## Exploration verified (against `plan/lazy-store-singletons`, cut from master @ b011472)

Every claim below was measured this pass, in clean subprocesses.

**Lazy construction does not deliver isolation — it only moves the binding.** Point `ADMZ_DB_PATH` at
A, use the store, point it at B, use it again:

| store | idiom | A created | B created |
|---|---|---|---|
| `demo_store` (`get_store()`) | **lazy** | yes | **no** |
| `session_store` (`get_session_store()`) | **lazy** | yes | **no** |
| `fleet_settings` | eager | yes | **no** |
| a freshly constructed `FleetSettings()` each time | — | yes | **yes** |

The four "already lazy" stores behave *identically to the eager ones* once used. The control proves
path resolution itself is call-time (ADR-0042 holds); it is the **caching in `__init__`** that
freezes it. So converting 110 call sites to `get_fleet_settings()` would buy "import does no I/O" and
would still leave the frozen path in place.

**The structural facts that make a cheaper fix possible:**

- 17 store modules total — 13 eager singletons, 4 lazy (`session_store`, `demos/store`,
  `demos/inference/proposals`, `demos/inference/runs`).
- `_connect()` is the **sole** choke point: every `sqlite3.connect(self._db_path)` in `admz/` lives
  inside a `def _connect`, with no bypasses.
- Each store references `_db_path` about **four** times — assignment, `_connect`, and a couple more.
- `_ensure_table()` is called from `__init__` **only**, in all 17.
- Ten-plus tests read `store._db_path` externally and hand it to `sqlite3.connect()`
  (`test_confirm_store.py:144`, `test_github_app.py:229`, `test_fleet_drift.py:95`, …), so it must
  remain a string attribute.

**A prototype on the worst-case store (`fleet_settings`, 76 import sites) was built and measured, then
reverted.** Making `_db_path` a property and moving schema-ensure into `_connect()`:

```
after import,     ADMZ_HOME exists: False      <- import does no I/O
after first USE,  ADMZ_HOME exists: True       <- created on demand
A exists: True    B exists: True               <- rebinding now honoured
229 passed  (only the 3 known pre-existing mcp-1.26.0 failures)
```

**Zero call sites changed.** The module-level singleton object stays exactly as it is, so
`from admz.fleet_settings import fleet_settings` keeps working everywhere.

---

## D1 — Which idiom wins?

**Neither. The question is mis-framed, and answering it as asked would buy the smaller half of the
benefit at fifty times the cost.**

Both candidate idioms — `session_store`'s `get_x()`/`set_x()` and `demos/store.py`'s
`DemoStore.__new__(DemoStore)` + `hasattr` — are *lazy construction*. Measured above: lazy
construction does not make a store honour its environment. It defers the freeze; it does not thaw it.

**Decision: a `_db_path` property that resolves at call time, with schema-ensure moved into
`_connect()`, and the module-level singleton object retained.**

Why this and not accessors:

- It delivers **both** properties (no import-time I/O *and* call-time resolution); accessors deliver
  one.
- It costs **0 call-site changes** against ~110.
- It is what ADR-0042 already says should happen — *"Every resolver here is call-time … an env var
  set between import and use, as tests and service wrappers do, must be honored."* The stores opted
  out of that contract by caching. This is enforcement, not a new direction.
- The `set_x()` test seam becomes unnecessary: with call-time resolution, `monkeypatch.setenv` works,
  which is what ~100 tests already expect.

**Still retire `demos/store.py`'s `DemoStore.__new__(DemoStore)` + `hasattr` hack.** It constructs an
uninitialised instance to keep a module-level name bound, then reconstructs on first access. Under
this design nothing needs to be deferred that way, so it becomes a plain singleton like the rest.

**Leave `session_store`'s and the demo stores' existing `get_x()` accessors in place.** They are
harmless once the underlying store resolves at call time, and churning their call sites buys nothing.
Do not propagate the pattern to new stores.

> **PEP 562 module `__getattr__` is not a shortcut, and is now moot.** It was raised as a way to keep
> `from admz.fleet_settings import fleet_settings` working while deferring construction. It does not
> work: the sampled importers are module-level, so `from … import …` in `api/routes/web.py` still
> fires at that module's import, which is import time for the web process. Under this plan the point
> never arises, because no call site changes. Recorded so nobody re-proposes it.

## D2 — Is ~110 call sites the right unit of work?

**No. The right unit is 17 modules and 0 call sites.**

The 110 figure is the cost of the accessor conversion, which this plan does not do. The real work is
~30 lines per store module, mechanical and near-identical across all 17.

This also dissolves the issue's framing of `fleet_settings` as "the worst" at 76 sites. Under this
design `fleet_settings` is the *same size* as every other store. What makes it special is **blast
radius**, not cost — it is the most depended-upon store in the codebase, so a defect in it surfaces
everywhere at once. That distinction drives D3.

## D3 — One PR or staged, and where does `fleet_settings` go?

**Staged, in four PRs.** The change is mechanical but touches every persistence path in the product;
a single 17-module PR is unreviewable in the way that matters (nobody checks the 17th store as
carefully as the first).

The ordering question ("`fleet_settings` first as proving ground or last as victory lap") changes
shape once cost is equal across stores. It goes **second** — neither.

| stage | contents | why |
|---|---|---|
| **1** | The test harness (D4) + **one** low-blast-radius store: `admz/chatbot/usage.py` | Proves the pattern end-to-end against real tests before anything depended-upon moves. `usage.py` is self-contained, has no cross-store callers, and its failure mode is a chat token counter rather than the fleet. |
| **2** | `fleet_settings` | Highest blast radius, so the coexistence window where it uses the *old* idiom while others use the new one should be as short as possible. Going last would mean 16 stores land, then the one everything depends on changes at the end — the worst time to discover an interaction. |
| **3** | The remaining 11 eager stores | Mechanical repetition; the pattern is proven twice by now. Group by subsystem (events, demos-adjacent, fleet/snapshot) so each PR has a coherent reviewer. |
| **4** | The 4 lazy stores + retire the `__new__` hack + delete the `PENDING` set | Finishes the inventory; the completeness guard becomes total. |

**Not first:** validating a new persistence idiom on the store that 76 modules import means every
early mistake is a whole-suite failure, and the signal about *the pattern* is buried in noise about
*that store*.
**Not last:** it leaves the highest-traffic store on the old idiom through the entire conversion,
which is the longest possible window for a two-idiom interaction bug.

## D4 — What does "done" look like, and the vacuity trap

The goal is a test that proves **no store reaches a real database**. The trap in this specific shape:

> *"No store connected"* is trivially true if nothing imported a store.

A subprocess that imports nothing and asserts no DB appeared would pass forever, prove nothing, and
look like coverage. This is the same failure mode as #207's skipped ACL test and #250's
"no broad principal can read it" — satisfied by a file nobody can read.

**The test closes it in three parts, all of which must hold together:**

```python
# tests/test_store_import_purity.py  (subprocess; ADMZ_HOME points at a NON-EXISTENT path)

STORE_MODULES = [...]        # explicit inventory, 17 entries
CONVERTED     = {...}        # grows each stage
PENDING       = {...}        # shrinks each stage; deleted in stage 4

def test_inventory_is_complete():
    """Closes the escape hatch: store #18 cannot appear without being listed."""
    discovered = _discover_store_modules(Path("admz"))   # AST: _default_db_path + __init__(db_path=
    assert discovered == set(STORE_MODULES)
    assert CONVERTED | PENDING == set(STORE_MODULES)

@pytest.mark.parametrize("module", sorted(CONVERTED))
def test_importing_a_store_creates_nothing(module, tmp_path):
    home = tmp_path / "never-created"
    assert not home.exists()                      # anti-vacuity: it must be absent FIRST
    r = _run(f"import {module}", home)
    assert r.returncode == 0
    assert not home.exists()                      # <- the structural guarantee

def test_importing_every_converted_store_at_once_creates_nothing(tmp_path):
    """The one that cannot be satisfied by importing nothing."""
    home = tmp_path / "never-created"
    assert not home.exists()
    stmt = "; ".join(f"import {m}" for m in sorted(CONVERTED))
    r = _run(stmt + f"; import sys; print('LOADED', len([m for m in sys.modules if m.startswith('admz')]))", home)
    assert r.returncode == 0
    assert "LOADED" in r.stdout
    assert int(r.stdout.split("LOADED")[1]) > 20   # proves the import surface was real
    assert not home.exists()

def test_first_use_still_works(tmp_path):
    """The mechanism is deferred, not broken."""
    ...assert home.is_dir() and the value round-trips...

def test_a_store_honours_a_rebind(tmp_path):
    """The property NO current test asserts, and the one laziness cannot give.
    Nothing in the suite catches a regression to caching in __init__ today."""
    ...set ADMZ_DB_PATH=A, use, set ADMZ_DB_PATH=B, use, assert BOTH exist...
```

The `assert int(...) > 20` is the anti-vacuity latch: it fails if the import statement silently
stopped importing anything. `test_inventory_is_complete` is the "file 168" latch, and it runs from
**stage 1**, with `CONVERTED | PENDING` covering the full set — so at no point during the conversion
can a store be missing from the inventory, even while most of them are still unconverted.

**Done is:** `PENDING` is empty, `test_inventory_is_complete` passes with `CONVERTED` covering all 17,
and importing the entire store surface on a machine with no `ADMZ_HOME` creates nothing.

---

## Design — what changes, per store

```python
class FleetSettings:
    def __init__(self, db_path: Optional[str] = None):
        self._explicit_db_path = str(db_path) if db_path else None
        self._ready: set[str] = set()
        self._ready_lock = threading.Lock()
        # NO I/O.

    @property
    def _db_path(self) -> str:
        """Resolved at CALL time. Stays a str: 10+ tests read this attribute
        and pass it to sqlite3.connect()."""
        return self._explicit_db_path or str(_default_db_path())

    def _connect(self) -> sqlite3.Connection:
        path = self._db_path
        if path not in self._ready:                      # fast path, no lock
            with self._ready_lock:
                if path not in self._ready:              # double-checked
                    from admz.paths import ensure_parent_dir
                    ensure_parent_dir(path)
                    self._create_schema(path)
                    self._ready.add(path)
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn
```

Notes that matter:

- **`_ready` is keyed by path**, not a boolean. A rebind must re-run the schema against the new file,
  or the first operation after a switch hits a missing table.
- **Double-checked locking**, because `_connect()` is on every read path and these stores are used
  from the FastAPI event loop, the scheduler thread and the MCP subprocess pool.
- **Schema-ensure must not use `_connect()`** (infinite recursion). A private `_create_schema(path)`
  opens its own connection.
- `_ensure_table()` is retained as a thin wrapper (`self._connect().close()`) — it is referenced by
  name in a few tests and costs nothing to keep.
- `ensure_parent_dir` rather than `ensure_admz_home`, for the #254 reason: `ADMZ_DB_PATH` may point
  outside `ADMZ_HOME`.

## ADR — amend ADR-0042, do not write a new one

**Recommendation: extend [ADR-0042](../decisions/0042-machine-level-data-directory.md) with a section
"Call-time resolution extends through the stores".**

ADR-0042 already states the rule this plan enforces — *"Every resolver here is call-time; nothing may
read the environment at import time"* — and scopes it to `admz/paths.py`. The stores defeat it one
layer up by caching the resolved value. That is a **gap in an existing decision**, not a new one, and
a new ADR would imply the project is deciding something it already decided.

The counter-argument, recorded because it is not weak: *"a store's `__init__` must perform no I/O"*
is a genuinely new architectural rule, it comes from the H-2 review finding rather than from
ADR-0042, and it constrains code that has nothing to do with path resolution. If the reviewer prefers
ADR-0059 on that basis, that is defensible — but then ADR-0042 must gain a forward pointer, because
the two halves are one rule and splitting them across documents is how the next person finds only one.

## What this does **not** fix

Name these in the PRs; each is a place someone could reasonably assume more was delivered.

1. **It does not remove `ensure_parent_dir()` from the runtime path — it moves it.** #254 put the
   call in `__init__`; this puts it in `_connect()`. A fresh install still gets its directory created,
   just at first *use* rather than first *import*. That is the intended behaviour, not a leftover.
2. **It does not make `SQLiteDeviceRegistry` lazy.** That class is constructed explicitly by callers,
   not as a module singleton, so I/O in its `__init__` is correct and stays.
3. **It does not remove the need for #260's conftest redirect.** That guard is what makes the *default*
   safe; this change makes the default *honourable*. Both, permanently. #260's guard must keep passing
   at every stage — it will, and it gets stronger: with call-time resolution the redirect works even if
   a module is re-imported later.
4. **It does not fix the twelve import-time `ensure_admz_home()` calls in non-store modules** — there
   are none left after #254 except inside the stores themselves, which this converts. `git_repo.py`'s
   `ensure_admz_home()` is inside a function, not at import.
5. **It does not address #250.** Windows `ADMZ_HOME` permissions remain `setup-admz-service.ps1`'s job.

## Risks

| risk | mitigation |
|---|---|
| A store operation runs before the schema exists, because ensure moved later | `_ready` check is inside `_connect()`, which every operation goes through — verified as the sole choke point |
| Rebinding mid-process silently splits data across two DBs | Only reachable if `ADMZ_HOME`/`ADMZ_DB_PATH` changes at runtime, which production never does. It is the *desired* behaviour in tests |
| Thread race on `_ready` | Double-checked locking; the store objects are already shared across the event loop, scheduler and MCP pool |
| Per-connect `getenv` + `Path` cost | Negligible against opening a SQLite connection; measure in stage 1 if anyone objects |
| Two idioms coexist during stages 1–3 | Bounded by D3's ordering; `test_inventory_is_complete` asserts `CONVERTED \| PENDING` covers all 17 at every stage |
| A new store lands mid-conversion and misses the pattern | `test_inventory_is_complete` fails on any undiscovered module from stage 1 onward |

## Out of scope (follow-up issues)

- **The venv no longer satisfies its own floor** — `mcp 1.26.0` installed against
  `requirements.txt`'s `mcp>=2.0,<3`, so ~4 MCP-surface tests fail on the operator's box and pass in
  CI. Surfaced repeatedly across #250/#254/#257. **Already recorded**: it is the live contradiction
  ADR-0054 was written around ("mcp 2.x code, mcp 1.26 venv"), tracked by #173/#235 and the
  `dev-prod-split` plan. Noted here only so the next person running this suite locally recognises the
  failures as known and unrelated.
- Converting the existing `get_x()` accessors back to plain singletons — harmless as-is, no value in
  the churn.
- `admz/tasks/migrate.py:91`, which connects to a path handed to it directly. Not a store.

## Outcome (all stages merged, #258 closed)

Shipped as **five** stages, not four. Stage 3's eleven stores were split
because moving `_ensure_table` into `_connect()` also moves **when a column
migration runs** — a materially different review from moving a bare
`CREATE TABLE IF NOT EXISTS` — so 3a took the six with schema only and 3b the
five carrying a migration.

| stage | PR | stores |
|---|---|---|
| 1 | #267 | `chatbot.usage` + the harness |
| 2 | #269 | `fleet_settings` |
| 3a | #271 | `api.capture`, `api_keys`, `events.detections`, `events.store`, `events.watched`, `tasks.store` |
| 3b | #284 | `api.confirm_store`, `audit`, `chatbot.sessions`, `fleet.health`, `snapshot.drift_alerts` |
| 4 | this | `demos.store`, `demos.inference.proposals`, `demos.inference.runs`, `session_store`; `__new__` hack retired; `PENDING` deleted |

**All 17 stores resolve their DB path at call time**, and
`tests/test_store_import_purity.py` proves it for each: construction does no
I/O, a changed `ADMZ_DB_PATH` is honoured, and importing the module creates
nothing. `test_every_store_in_the_tree_is_converted` rediscovers stores from
source, so the claim stays true rather than being a snapshot.

Corrections the build made to this plan, recorded because the plan was wrong
about them:

- **D4's import-purity assertion was not reachable in stage 1.** A module is
  import-pure only once its whole *transitive* store graph is converted;
  `chatbot.usage` pulls in `chatbot.sessions` via the package `__init__`, which
  was stage 3b. Handled with a characterisation tripwire that fired on
  schedule.
- **`audit` has no column migration at all.** It sat in 3b only because
  #270/#276 was in flight against it.
- **`chatbot.sessions` carries a DATA migration**, not just a schema one:
  `_backfill_conversations` calls `_connect()`, so the setup path re-enters the
  object and needs its own marker set plus an `RLock`.
- **Zero call sites changed**, as predicted — the count held across all 17.

## Critical files

| file | role |
|---|---|
| `admz/fleet_settings.py` | Stage 2. Prototyped and measured this pass; highest blast radius |
| `admz/chatbot/usage.py` | Stage 1 proving ground — self-contained, low blast radius |
| `admz/demos/store.py` | Stage 4; retires the `__new__` + `hasattr` hack |
| `admz/paths.py` | `ensure_parent_dir` — unchanged, called from `_connect()` instead of `__init__` |
| `tests/test_store_import_purity.py` | New. The D4 harness; lands in stage 1 |
| `tests/conftest.py` | #260's redirect must keep passing at every stage |
| `docs/specification/decisions/0042-machine-level-data-directory.md` | Amended per the ADR section |
