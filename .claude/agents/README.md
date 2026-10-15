# Pychestrate Agent Team

Persistent Claude Code subagents for working on `pychestrate-core`. Each agent is a
markdown definition (YAML frontmatter + system prompt) in this directory and is
invokable via the Agent tool. All agents identify as **AutomationX** (per `AGENTS.md`)
and enforce the coding standards (kept once, in pychestrate-service: see `userguide/contributing.rst`).

## Roster

| Agent | Role | Owns |
|-------|------|------|
| `pychestrate-lead` | Lead / orchestrator | Planning, decomposition, delegation, review, integration. Delegates to the specialists below. |
| `pychestrate-ui` | UI / interface specialist | Public API surface & ergonomics, serialization shapes, CLI/UX, TypeScript/JS client code. |
| `pychestrate-projects` | Projects domain | `Product`, `ProductComponent`, `ProductToRepository`, `Repository`, `Branch`. |
| `pychestrate-builds` | Builds domain | `BuildJobTemplate`, `BuildTemplate`, `BuildJob`, `BuildResult`, `BuildByProduct`. |
| `pychestrate-testing` | Testing domain | `TestJobTemplate`, `TestJob`, `TestJobRun`, `TestResult`, `TestResultContainer`; `testbase` suite stewardship. |
| `pychestrate-resources` | Resources / execution domain | `WorkQueue`, `WorkPacket`, `FeatureGroup`(+Membership), `User`/accounts, queue/packet state machines. |
| `pychestrate-releases` | Releases domain | `ReleaseTrain`, `ReleaseTrainBranch`, `Release`, `ReleaseBranchAssignment`, train topology. |
| `pychestrate-storage` | Storage / persistence | `dbconnection`, `dbio`, ORM bases/mixins (`PychestrateModelBase`, `SerializableModel`), `defaults`. |

## Product Owners (requirements)

Per-area Product Owners own the *what/why* — requirements, user workflows, personas,
and acceptance criteria — and maintain the specs under `specs/`. Each pairs with the
code agent of the same area (the *how*).

| Agent | Area | Owns spec |
|-------|------|-----------|
| `po-projects` | Projects | `specs/projects-requirements.md` |
| `po-builds` | Builds | `specs/builds-requirements.md` |
| `po-testing` | Testing | `specs/testing-requirements.md` |
| `po-resources` | Resources / execution | `specs/resources-requirements.md` |
| `po-releases` | Releases | `specs/releases-requirements.md` |

## How to use

- For multi-area or unscoped work, start with **`pychestrate-lead`** — it plans and
  delegates to the right specialists.
- For a change confined to one domain, invoke that domain agent directly.
- **Shared/foundation rule:** changes to ORM base classes, serialization mechanics, or
  DB plumbing belong to **`pychestrate-storage`**; domain agents own their own entities.
- Anything client-facing (API surface, payload shape) routes through **`pychestrate-ui`**.

## Conventions every agent follows

- Standards: `../pychestrate-service/userguide/10-00-coding-standards.rst`, naming `10-02-naming-conventions.rst`,
  structure `10-01-code-organization.rst`, testing `10-03`/`10-04-03`.
- Single-host tests only for AI runs:
  ```
  source .venv/bin/activate
  testbase testing run --root source/testroots/ccai --includes=ccai.tests.pychestrate.singlehost --output=./.output
  ```
  Results stream: `<output>/testrun_results_stream.jsos`.
