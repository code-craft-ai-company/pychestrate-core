# Testing — Requirements

## 1. Overview

The Testing functional area of Pychestrate is the part of the CI data model that
captures *what test work was defined, how it was executed, and what it produced*.
It is realized today by five entities in
`source/packages/ccai/pychestrate/core/storage/orm.py`:

- **TestJobTemplate** (lines 172-182) — a reusable, named definition of a test job
  with an opaque JSON `specification`.
- **TestJob** (lines 598-615) — an instantiated test job titled and owned by a
  `FeatureGroup`.
- **TestJobRun** (lines 618-645) — a single execution of a TestJob against a
  branch/build/flavor, with start/stop and an opaque JSON `detail`.
- **TestResult** (lines 648-666) — a node in a test result tree carrying
  `name`, `monikers`, `pivots`, `rtype`, `result`, start/stop, and JSON `detail`.
- **TestResultContainer** (lines 669-685) — a grouping node in the result tree with
  a self-referencing `parent` UUID and `rtype`.

The model maps almost field-for-field onto the JSOS result stream described in
`AGENTS.md` (name/monikers/pivots/instance/parent/rtype/result/start/stop/detail).
It can store a single run's result tree as opaque blobs, but it cannot natively
support test selection/sharding, retries and flaky detection, rich result
reporting, quality gates, or cross-run historical trend analysis without parsing
JSON `detail` blobs. The purpose of this specification is to define the
requirements that take Testing from "stores one run as blobs" to "a queryable,
auditable, gateable, trend-capable test system" — reusing patterns already proven
elsewhere in the same ORM (the `WorkPacketStatus` enum, the `Branch`/`BuildResult`
foreign keys, and the `BuildByProduct.result_url` artifact pattern).

## 2. Personas

- **Release Engineer / CI pipeline owner** — instantiates test jobs for a specific
  build and branch, shards them across workers for speed, aggregates a single
  pass/fail verdict, and gates releases on it.
- **Test owner / QA engineer triaging failures** — opens a failing result, reads
  message/trace, views logs and screenshots, judges flakiness from history, and
  retries or quarantines as appropriate.
- **Engineering manager / quality lead** — tracks pass-rate and flakiness trends
  per branch and per feature group, correlates regressions to the commit/build that
  introduced them, and assigns triage against an MTTR target.

## 3. User Workflows

### 3.1 Sharded run with a gated verdict (Release Engineer)

1. Select a TestJobTemplate and instantiate a TestJob bound to a product/branch/build.
2. Split the suite into N shards using historical per-test timing.
3. Dispatch shards as work items across qualified worker sites.
4. Aggregate the N shard executions into one logical TestJobRun with summary counts.
5. Evaluate a quality gate (pass-rate / required-suite threshold) to allow or block
   the release.

**Current pain points:** no template-to-job linkage (origin and spec version are not
auditable); no shard index/total or attempt model on TestJobRun (a sharded run cannot
be represented or aggregated); no run-level status or summary roll-up (the gate
verdict must be recomputed by parsing JSON `detail`); branch/build/flavor are free
strings, not typed references to `Branch`/`BuildResult`, so a run cannot be reliably
joined to the build it tested.

### 3.2 Triage a failure and quarantine if flaky (Test owner / QA)

1. Open the failing TestResult and read the message and stack trace.
2. View attached logs, screenshots, and trace artifacts.
3. Check the test's recent pass/fail history to judge flakiness.
4. Mark the test flaky and quarantine it with an owner and fix-by date, or trigger a
   guarded retry.
5. Confirm the quarantined test runs in a separate non-blocking suite.

**Current pain points:** `result` is a free `String(50)` with no flaky flag, retry
count, or attempt history; no attachment/artifact relation (logs and screenshots have
nowhere structured to live); no file/line/owner fields (routing is manual); no
quarantine state/owner/fix-by columns (quarantine cannot be tracked and becomes
permanent); no stable cross-run test identity (per-test history cannot be assembled
efficiently).

### 3.3 Track trends and correlate regressions (Engineering manager)

1. Open a dashboard filtered by branch and feature group.
2. View the pass-rate trend line over a rolling window.
3. Drill into newly failing or newly flaky tests.
4. Correlate regressions to the commit/build that introduced them.
5. Assign triage with an MTTR target.

**Current pain points:** no commit SHA or typed build/environment context on
TestJobRun (trends cannot be correlated to the causing change); no run-level or
per-test summary counts (every trend query parses opaque JSON `detail`); no durable
flaky/quarantine/retry history (flakiness rate and MTTR cannot be computed);
TestResultContainer links to TestJob rather than TestJobRun (per-run hierarchy
aggregation across history is unreliable).

## 4. Functional Requirements

Priority key: **P0** must-have (correctness/integrity foundation), **P1**
high-value, **P2** valuable, **P3** nice-to-have.

| ID | Statement | Priority | Acceptance Criteria |
|----|-----------|----------|---------------------|
| TEST-001 | A TestJobTemplate stores a named, reusable test job definition. | P0 | TestJobTemplate persists `name` (unique, non-null), optional `description`, and a `specification` (JSON, non-null); duplicate names are rejected by a unique constraint. |
| TEST-002 | A TestJob is an instantiated test job owned by a FeatureGroup. | P0 | TestJob persists `title`, `description`, and a nullable FK `owner_fg_id` to `feature_group.fg_id`; deleting a TestJob cascades to its runs and result containers. |
| TEST-003 | A TestJob is provably derived from a specific TestJobTemplate version. | P1 | TestJob carries a non-null `template_id` FK to `testjob_template.id` and a `template_version` (or template spec hash) recorded at instantiation; a query can return the exact template+version that produced any TestJob. |
| TEST-004 | TestJobTemplate.specification is versioned and immutable per version. | P2 | Editing a template's specification produces a new version row rather than mutating the in-use spec; existing TestJobs continue to reference the version they were created from. |
| TEST-005 | A TestJobRun records a single execution of a TestJob. | P0 | TestJobRun persists `instance` (PK UUID), `start` (non-null, indexed), `stop` (nullable), `ownertag`, non-null FK `job_id` to `test_job.tj_id`, FK `user_id`, and optional FK `fg_id`. |
| TEST-006 | A TestJobRun has a constrained overall status. | P0 | TestJobRun gains a `status` column typed as an Enum (e.g. QUEUED/RUNNING/PASSED/FAILED/ERROR/CANCELED), `native_enum=False`, default QUEUED, reusing the `WorkPacketStatus`-style pattern; status is filterable in SQL without parsing JSON. |
| TEST-007 | A TestJobRun references the branch and build it tested via typed FKs, not free strings. | P1 | The free `branch`/`build`/`flavor` VARCHAR(1024) columns are replaced (or supplemented and deprecated) by FKs to `branch.branch_id` and `build_result.build_id`; a run can be joined to the exact build it tested. Free-string columns, if retained for migration, are documented as deprecated. |
| TEST-008 | A TestJobRun records commit/trigger/environment metadata for regression correlation. | P1 | TestJobRun persists `commit_sha`, `trigger`, `environment`, `build_url`, and optional OS/platform context; trend queries can be filtered by commit and environment without parsing `detail`. |
| TEST-009 | A TestJobRun stores denormalized summary roll-up counts. | P1 | TestJobRun persists `tests_total`, `passed`, `failed`, `error`, `skipped`, `flaky`, and aggregate `duration`; the gate verdict and dashboards read these columns directly. Counts equal the aggregation of the run's TestResults. |
| TEST-010 | A logical TestJobRun can be decomposed into shards and re-aggregated. | P1 | The model represents `shard_index`/`shard_total` and a worker assignment (either on TestJobRun or a child TestJobShard entity); N shard executions aggregate into one logical run verdict and one summary roll-up. |
| TEST-011 | Per-test historical timing is persisted to enable timing-based shard balancing. | P2 | Each TestResult's duration is durable and queryable by stable test identity (see TEST-016) so a balancer can split the suite by historical timing. |
| TEST-012 | A TestResult node stores the JSOS-aligned fields of a result tree node. | P0 | TestResult persists `instance` (PK UUID), `name`, `monikers` (JSON), `pivots` (JSON), `start`, `stop`, `detail` (JSON), and FK `testrun` to `test_job_run.tjr_instance`; these map field-for-field onto the JSOS stream in AGENTS.md. |
| TEST-013 | A TestResult node type and result status are constrained enums, not free strings. | P0 | `rtype` and `result` (currently `String(50)`) are replaced with Enums; `TestResultStatus` covers at least PASSED, FAILED, ERROR, SKIPPED, UNSET/RUNNING, and QUARANTINED, distinguishing FAILED (assertion) from ERROR (unexpected). Invalid values are rejected. |
| TEST-014 | A TestResult records retries and attempts. | P0 | TestResult persists `attempt_number` and `retries` (count); a guarded retry creates/updates attempt records such that the final verdict and the retry count are both queryable. |
| TEST-015 | A TestResult carries an explicit flaky flag. | P0 | TestResult persists a non-null boolean `flaky` (default false); a test that passed only after retry within the same commit can be marked flaky and counted in the run's `flaky` roll-up. |
| TEST-016 | The same logical test has a stable identity across runs. | P0 | TestResult persists a durable `test_key` (stable hash of `name` plus monikers/pivots) that is identical for the same logical test across TestJobRuns, enabling per-test history, flakiness rate, and MTTR computation. |
| TEST-017 | A flaky test can be quarantined with accountability. | P1 | A quarantine record (state, `owner_user_id` FK, `fix_by` date, `reason`) is persisted for a test; a quarantined test is excluded from the blocking verdict and surfaced in a separate non-blocking suite. Quarantine without an owner and fix-by date is rejected. |
| TEST-018 | A TestResult carries triage and failure-classification data. | P2 | TestResult (or a related triage record) persists `failure_category` (regression/flaky/environment/performance), optional `ticket_url`, `assignee`, and MTTR timestamps; MTTR per failure category is computable. |
| TEST-019 | A TestResult records message, trace, and source location. | P1 | TestResult persists `message`, `trace`, `file`, `line`, and `owner`; a triage user can read the failure reason and route it to an owner without opening the raw `detail` blob. |
| TEST-020 | A TestResult records its own duration. | P1 | TestResult persists a `duration` column derived from or independent of start/stop; duration is queryable without computing stop-minus-start at read time. |
| TEST-021 | Test artifacts are stored in a dedicated related table, not inline. | P1 | A `TestResultArtifact` entity persists `type` (log/screenshot/trace/coverage), `url`, and `size`, with an FK to the owning TestResult, mirroring the `BuildByProduct.result_url` pattern; the result row stays small. |
| TEST-022 | A TestResultContainer groups result nodes within a tree. | P0 | TestResultContainer persists `id`, `name`, `instance` (UUID), `rtype`, and a `parent` reference; it serves as a parent/container for individual result nodes. |
| TEST-023 | TestResultContainer is scoped to a TestJobRun, not a TestJob. | P1 | TestResultContainer's `testjob_id` FK (to `test_job.tj_id`) is re-pointed to `test_job_run.tjr_instance` (containers are inherently per-run); per-run hierarchy aggregation across history is reliable. |
| TEST-024 | The result tree uses enforced foreign keys, not bare UUIDs. | P1 | TestResultContainer's `parent` self-reference and the TestResult-to-container linkage are declared as `ForeignKey` constraints; orphan/dangling tree nodes are prevented at the database level. |
| TEST-025 | TestResult node type (`rtype`) is a constrained enum. | P1 | TestResultContainer.`rtype` and TestResult.`rtype` use a shared `ResultNodeType` enum rather than `String(50)`; node types are queryable with integrity. |
| TEST-026 | A quality gate is configurable on the template/job and its outcome is persisted on the run. | P2 | TestJobTemplate/TestJob carry gate configuration (required pass-rate, required suites, coverage thresholds); TestJobRun persists the computed gate outcome (allow/block) and the inputs that produced it. The release decision reads the stored outcome. |
| TEST-027 | Per-test pass-rate and stability trends are queryable over a configurable window. | P2 | Given a `test_key`, branch, and feature group, the system returns a pass-rate trend over a rolling window from durable per-test records without parsing JSON `detail`; newly failing/flaky tests are surfaceable. |
| TEST-028 | Intelligent retries are guarded and bounded. | P3 | One guarded retry is permitted for an infrastructure/environment-classified failure; when retries exceed a configured threshold a triage record/ticket linkage is created and the test is not silently masked as a pass. |

## 5. Non-Functional Requirements

| ID | Statement | Priority | Acceptance Criteria |
|----|-----------|----------|---------------------|
| TEST-NFR-001 | **Integrity** — status, result, and node-type values are constrained at the schema level. | P0 | All status/result/type columns use SQLAlchemy `Enum(..., native_enum=False)`; no Testing status value is stored as a free-form `String`. |
| TEST-NFR-002 | **Debuggability** — failure context is first-class, not buried in opaque blobs. | P0 | message/trace/file/line/duration/artifacts are queryable columns/relations; a triager can diagnose a failure without parsing `detail` JSON. Per the project standard, errors are not silently swallowed and FAILED (assertion) is distinguished from ERROR (unexpected). |
| TEST-NFR-003 | **Queryability for trends** — common dashboard queries avoid JSON parsing. | P1 | Pass-rate, flakiness, and roll-up queries run against indexed typed columns (`status`, `test_key`, `branch_id`, `commit_sha`, summary counts); no trend query requires deserializing a `detail` blob. |
| TEST-NFR-004 | **Scale** — sharded, parallel execution is representable and aggregatable. | P1 | A run split across N shards/workers is stored as N records aggregating to one verdict; the model supports timing-based balancing inputs. |
| TEST-NFR-005 | **Reliability of history** — per-test identity is stable across runs. | P0 | `test_key` is deterministic for a given name+monikers+pivots so historical metrics (flakiness rate, MTTR) are computable across arbitrary run counts. |
| TEST-NFR-006 | **Security / accountability** — quarantine and triage carry an owner. | P1 | Quarantine and triage records reference a real `User` FK and a `fix_by` date; ownerless or open-ended quarantine is not permitted. |
| TEST-NFR-007 | **Migration safety** — schema changes are backward-traceable. | P2 | Replacing free-string columns (branch/build/flavor, result/rtype) is delivered with a migration that preserves or maps existing data; deprecated columns are clearly marked. |

## 6. Best Practices Adopted

- **Constrained, first-class result status enum** distinguishing PASSED/FAILED/ERROR/
  SKIPPED plus an UNSET/RUNNING preview state, separating assertion failure from
  unexpected error per the JUnit XML de-facto standard and the JSOS preview/result
  lifecycle. Source: https://github.com/testmoapp/junitxml
- **Rich per-result schema** with retries, attempts, flaky flag, duration, message,
  trace, file/line, suite, tags, and attachments, modeled on the CTRF JSON schema
  rather than only name+status. Source: https://ctrf.io/docs/full-schema
- **Flaky detection and temporary quarantine** with a per-test flakiness rate over a
  rolling window and a required named owner and fix-by date for every quarantined
  test. Source: https://www.atlassian.com/blog/atlassian-engineering/taming-test-flakiness-how-we-built-a-scalable-tool-to-detect-and-manage-flaky-tests
- **First-class horizontal sharding and parallel workers**, splitting tests by
  historical timing and recording shard index/total and worker assignment so a logical
  run aggregates N shard executions. Source: https://playwright.dev/docs/test-sharding
- **Automatic failure classification and guarded intelligent retries**, with triage
  ticketing above a retry threshold and MTTR tracking per failure. Source:
  https://docs.datadoghq.com/tests/flaky_test_management/auto_test_retries
- **Run-level summary roll-ups and build/environment/commit context** (commit SHA,
  branch, build number/URL, environment, OS/platform, trigger) on every run to enable
  quality gates and time-series trend analysis. Source: https://ctrf.io/docs/full-schema
- **First-class test artifacts/attachments** (logs, screenshots, traces, coverage) as
  a related table referenced from results rather than inline blobs, mirroring the
  existing `BuildByProduct.result_url` pattern. Source: https://github.com/jenkinsci/pipeline-model-definition-plugin/wiki/Reporting-test-results-and-storing-artifacts
- **Pass-rate and stability trend tracking per test** over a configurable window,
  keyed by a stable cross-run test identity. Source: https://reportportal.io/blog/test-result-trends-how-to-analyze-regression-testing-results-over-time-in/

## 7. Data Model Traceability

| Entity (orm.py) | Requirements | Notes |
|-----------------|--------------|-------|
| **TestJobTemplate** (172-182) | TEST-001, TEST-003, TEST-004, TEST-026 | Add template versioning and gate configuration; spec stays JSON but becomes versioned/immutable per version. |
| **TestJob** (598-615) | TEST-002, TEST-003, TEST-026 | Add `template_id` FK + `template_version`; carry gate configuration. |
| **TestJobRun** (618-645) | TEST-005, TEST-006, TEST-007, TEST-008, TEST-009, TEST-010, TEST-026 | Add `status` enum, typed branch/build FKs, commit/trigger/environment metadata, summary roll-ups, shard/worker structure, and persisted gate outcome. |
| **TestResult** (648-666) | TEST-012, TEST-013, TEST-014, TEST-015, TEST-016, TEST-018, TEST-019, TEST-020, TEST-025, TEST-028 | Replace `result`/`rtype` String(50) with enums; add attempts/retries/flaky, `test_key`, message/trace/file/line/owner, duration, triage/failure-category. |
| **TestResultContainer** (669-685) | TEST-022, TEST-023, TEST-024, TEST-025 | Re-point FK from TestJob to TestJobRun; enforce FK on `parent` self-reference and child linkage; type `rtype` as enum. |
| **New: TestResultArtifact** | TEST-021 | FK to TestResult; `type`/`url`/`size`, mirroring `BuildByProduct`. |
| **New: TestQuarantine / triage** | TEST-017, TEST-018, TEST-028 | `owner_user_id` FK, `fix_by`, `reason`, `failure_category`, ticket/assignee/MTTR. |
| **New: TestJobShard (optional)** | TEST-010, TEST-011 | Per-shard execution records and timing if shards are not modeled inline on TestJobRun. |
| Reused: **Branch** (433), **BuildResult** (474) | TEST-007 | Existing FK targets for typed run context. |
| Reused: **WorkPacketStatus** (135-143), **BuildJob.status** (466) | TEST-006, TEST-NFR-001 | Established enum pattern to replicate for run/result status. |
| Reused: **BuildByProduct.result_url** (496-509) | TEST-021 | Established artifact-URL pattern. |

## 8. Open Questions

1. **Shards inline vs. child entity** — should `shard_index`/`shard_total`/worker live
   on TestJobRun, or should a logical run own N `TestJobShard` rows that aggregate into
   one verdict (TEST-010)? The latter is cleaner for retries-per-shard but is a larger
   schema change.
2. **branch/build/flavor migration** — do we hard-replace the free VARCHAR(1024)
   columns with FKs, or keep them as deprecated fallbacks during migration
   (TEST-007, TEST-NFR-007)? Depends on whether historical runs can be back-filled to
   `Branch`/`BuildResult`.
3. **test_key derivation** — exact hashing inputs and algorithm for stable cross-run
   identity (TEST-016): name only, name+monikers, or name+monikers+pivots? Affects how
   pivots (which may vary per run) interact with identity.
4. **Template versioning mechanism** — version column vs. spec-hash vs. separate
   version table (TEST-004); cross-area dependency on how BuildJobTemplate/BuildTemplate
   handle (or do not handle) versioning, for consistency across the ORM.
5. **Quality-gate ownership** — is gate evaluation a Testing-area responsibility that
   persists an outcome (TEST-026), or does an external release/orchestration area own
   evaluation and only read Testing's summary roll-ups? Cross-area dependency.
6. **Quarantine enforcement point** — does the model only *record* quarantine state, or
   must the execution/selection layer guarantee quarantined tests run in a separate
   non-blocking suite (TEST-017)? Cross-area dependency with the scheduler/work-queue.
7. **User identity for owner/assignee** — confirm the FK target table (`user.user_id`)
   and whether owners are individual users or FeatureGroups for routing (TEST-017,
   TEST-019).
8. **Retry policy source of truth** — per the Aspects pattern, retries/quarantine
   thresholds should be caller/config-driven, not decorator-driven (TEST-028); where
   does that configuration live — TestJobTemplate specification, gate config, or a
   separate policy entity?
