# Agentic task set (dispatch-time routing)

This is the task set for `exp05_dispatch` (see
[`docs/experiments/dispatch-routing.md`](../../docs/experiments/dispatch-routing.md)).
Each task is a self-contained "task chip" of the kind a coding session
spawns to a fresh agent session, run inside a throwaway sandbox copy of a
small fixture repo, and graded deterministically once the agent is done.

## Layout

```
tasks/agentic/
  tasks.jsonl          # one AgentTask per line
  repos/<name>/         # fixture repos (invoicing, notes, logproc)
  hidden/<task-id>/     # hidden tests, copied in only after the agent finishes
  solutions/<task-id>/  # a correct reference fix, proves the task is solvable
  setup/<task-id>/      # optional: files overlaid onto the repo before the run
  mutants/<task-id>/    # optional: known-buggy overlay for "missing test" tasks
```

`private/` (git-ignored) is where the harness may write scratch sandboxes;
nothing under it is part of the task set itself.

## Fixture repos

Three small, stdlib-only Python projects under `repos/`:

- **`invoicing`** - a billing library and CLI (customers, line items,
  invoices, CSV import/export, a buffered JSON store, a summary report, a
  simulated remote sync).
- **`notes`** - a CLI notes/to-do tool (tags, due dates, search/pagination,
  CSV export, a simulated remote sync).
- **`logproc`** - a log/CSV processing package (line parsing, per-level
  aggregation, CSV export, a buffered report pipeline, a simulated remote
  metrics push).

Each has its own `pyproject.toml` (no runtime dependencies), a `README.md`,
and a `tests/` directory runnable with `python -m pytest -q` from inside the
repo. Every fixture repo's `tests/conftest.py` puts `src/` on `sys.path` so
the suite runs without an install step - the grader always invokes
`sys.executable -m pytest`, never `pip install -e .`.

The fixture repos are deliberately a little messy: a couple of duplicated
helper functions, a buffered writer whose caller sometimes calls things in
the wrong order, hand-rolled CSV instead of the `csv` module, a dead CLI
flag, a stale README badge. The *visible* test suite in each repo only
covers the happy path - real coverage gaps, not artificial ones - so an
agent has to actually read the code to find what's wrong, the same way it
would in a real handoff.

## Tasks (`tasks.jsonl`)

Two generations of tasks, spread across all three repos:

- **`-01` tasks (30):** the original set across six categories (bugfix,
  feature, refactor, tests, docs, config). Their briefs name the fix, and the
  2026-09-22 pilot found the cheapest model passes them all, so they carry
  no routing headroom on their own.
- **`-02` tasks (24):** authored 2026-09-23 against issue #11 to need real
  investigation: multi-file changes with hidden coupling, underspecified
  briefs where intent must be inferred from code and tests, cross-module and
  ordering bugs, performance fixes checked by a deterministic budget (call
  counters, never wall-clock), migrations across many call sites, and named
  spec compliance. Each has a *trap*: an obvious local fix passes the visible
  suite but fails the hidden tests. Most inject their situation through a
  `setup/<id>/` overlay so the shared fixture repos stay untouched.

Each line is one `AgentTask` (see `src/model_routing/dispatch/types.py` -
**do not** change that contract from this task set):

| field | meaning |
|---|---|
| `id` | unique, `<repo-prefix>-<slug>-<NN>` |
| `title` | short chip title |
| `brief` | the full self-contained chip prompt (goal, files, acceptance, constraints) |
| `brief_terse` | a title-level, one-sentence version, for the brief-quality hypothesis (H-D6) |
| `parent_context` | an ~800-2500 word "prior session" narrative that seeds a resumed-parent policy (A / A_switch / C1) |
| `repo` | fixture repo dir name under `repos/` |
| `grader` | at minimum `{"allowed_paths": [...]}`; see below |
| `difficulty`, `category`, `max_turns`, `tags` | as in the contract |
| `measured` (optional) | written by `make dispatch-calibration ... WRITE=1`: per-candidate pass rates and trial counts from a calibration run, with the date. When present, `difficulty` is the **measured** label (easy = cheapest model passed every trial, medium = some, hard = only the strongest passed) and the original human guess moves to `difficulty_human`. |

`max_turns` is a human guess and is not applied by the runner (the config's
`max_turns` is); it is kept as documentation of the expected size.

`grader["allowed_paths"]` is a list of `fnmatch` globs (repo-relative) the
scope check compares every changed file against. Keep it tight - only the
files the brief actually calls out, plus `tests/*.py` for tasks that require
adding a test.

Every full `brief` ends with a scope line naming exactly those globs
(`Scope: change only ...; leave every other file untouched ...`). The scope
check is only fair if the agent was told the scope: in the 2026-09-22 pilot,
Opus and Sonnet both fixed a bug correctly and then updated a docstring the
fix had made stale in a file outside `allowed_paths`, which failed them on
scope and biased the comparison toward cheaper, less thorough models.
`brief_terse` deliberately omits it (it is the low-quality brief).

## Overlay conventions

`src/model_routing/dispatch/tasks.py` (`load_agent_tasks`) resolves these by
convention, relative to the JSONL's directory, and injects the resolved path
into the task's `grader` dict - a task's own `grader` can also name one
explicitly (e.g. to share an overlay across two tasks) and that wins over the
convention:

- `hidden/<id>/` -> `grader["hidden_tests"]`. Copied onto the sandbox *after*
  the agent's session ends, then run on their own (not mixed with the
  visible suite). Must be decisive: fail on the untouched repo, pass once the
  task is correctly solved. A task with no `hidden/<id>/` directory has no
  hidden-test check (used for the "add a missing test" tasks, which are
  graded by mutation instead - see below).
- `setup/<id>/` -> `grader["setup_overlay"]`. Copied onto the repo *before*
  the sandbox's initial commit, i.e. before the agent ever sees it - for a
  task that needs a bug injected on top of an otherwise-shared fixture repo.
  Unused by the `-01` tasks (their bugs/gaps are baked into the fixture
  repos directly); used by most of
  the `-02` tasks, which use it to inject a bug or a larger module.
- `mutants/<id>/` -> `grader["mutation_overlay"]`. Used only by "add a
  missing test" tasks (`inv-test-01`, `notes-test-01`, `log-test-01`): a
  known-buggy version of the file(s) the test should exercise. The grader
  copies the agent's own new test file(s) into a *copy* of the sandbox with
  the mutant applied and requires them to fail there (and to already have
  passed against the agent's correct code) - see `grading.py`. If a task's
  new test doesn't actually exercise the bug, this fails it even though the
  test technically "passes" on the real code.
- `solutions/<id>/` -> `grader["solution_overlay"]`. **Required** for every
  task. A correct reference fix, applied as a repo-relative file overlay.
  Two consumers: `scripts/validate_agentic_tasks.py` / `tests/
  test_dispatch_tasks.py` (proves the task is solvable and the grader isn't
  too strict or too loose), and `Sandbox.create(task, root, simulate=True)`
  (copies it into `<workdir>/.fake_solution/` for the fake provider to apply
  probabilistically for free, no-network simulated runs - see
  `sandbox.py`). `.fake_solution/` is excluded from scope checks and is
  never present in a real run.

Every overlay is a set of repo-relative files copied on top of the sandbox
(`dirs_exist_ok=True`) - e.g. `solutions/inv-page-01/src/invoicing/query.py`
overwrites that one file; you don't need to restate the whole repo.

## Adding a new task

1. Pick (or add to) a fixture repo under `repos/`. If the task needs a bug
   that isn't already latent in the shared fixture, either bake it into the
   repo directly (if it's a generally-useful defect for other tasks too) or
   add a `setup/<id>/` overlay that injects it just for this task.
2. Write the `tasks.jsonl` line. The `brief` must be self-contained (no
   reference to "the conversation above") and must **not** describe or hint
   at the exact hidden-test assertions - describe the observable behavior
   the fix should have, not the test that will check it. `parent_context`
   should read like an actual prior session: what was being worked on, a
   couple of unrelated things that got fixed along the way, a test run, and
   a natural reason to spin this off as a chip instead of doing it inline.
3. Add `hidden/<id>/tests/test_*.py` (or `mutants/<id>/...` for a
   missing-test task) - it must fail on the untouched repo and pass once the
   task is correctly solved.
4. Add `solutions/<id>/...` - the minimal correct fix, respecting
   `grader["allowed_paths"]`.
5. Run `uv run python scripts/validate_agentic_tasks.py` (or `make test`,
   which runs the same checks via `tests/test_dispatch_tasks.py`). It fails
   loudly if the untouched repo already passes, if the solution doesn't, or
   if the visible suite isn't green on the untouched repo.
6. Run `make check` - fixture/hidden/solution/mutant code must stay
   ruff-clean (`select = ["E", "F", "I", "UP", "B", "SIM"]`, line length
   100) and pyright-clean where it's imported from `tests/`.

## What makes a task hard but fair

A `-02` task must satisfy all of: the brief states symptoms and acceptance
criteria in outcome terms and never names the fix; every hidden assertion is
derivable from the brief plus the repo's existing docstrings (each hidden
test carries a comment naming the brief sentence it checks); an obvious
local fix passes the visible suite but fails the hidden tests; and solving
it needs investigation across files, modules or call order. Difficulty is
then *measured* by running every task on every static candidate
(`experiments/agentic/exp05_calibrate.toml`) rather than asserted.

## Why task text must not reveal hidden tests

The whole point of the experiment is measuring how well a *model*, from a
brief alone, does the work a hidden test will check. A brief that quotes or
closely paraphrases the hidden assertions turns the task into "make this
literal test pass" rather than "fix this problem," which would inflate pass
rates for every policy equally and make the cost-per-completed-task
comparison meaningless. Describe the *symptom* and the *acceptance
criteria* in outcome terms (e.g. "every invoice must appear on exactly one
page" - not "assert `paginate(items, 1, 3) == items[:3]`").

## Notes for other workstreams

- Nothing under `tasks/agentic/` is collected by the top-level `pytest` run:
  `pyproject.toml`'s `[tool.pytest.ini_options]` sets `testpaths = ["tests"]`,
  which already excludes it, so no `conftest.py`/`collect_ignore` was needed
  under `tasks/`. `tests/test_dispatch_tasks.py` explicitly loads and grades
  the task set instead.
- `results/` (git-ignored, per the top-level convention) is where a real
  dispatch run's sandboxes/outputs should land - fixture-repo sandboxes
  created by `Sandbox.create` default to wherever the caller passes as
  `root`; nothing in this task set writes there itself.
