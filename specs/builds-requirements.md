# Builds — Requirements

## 1. Overview

The Builds area of Pychestrate is responsible for defining, executing, and recording
software build activities and their produced artifacts. It is the system of record that
ties a unit of source (a `Branch` plus a changelist/commit) through a reusable build
definition (`BuildJobTemplate`, `BuildTemplate`), an execution (`BuildJob`), an outcome
(`BuildResult`), and the concrete artifacts a build emits (`BuildByProduct`).

Today the area is a minimal relational skeleton. Templates store a free-form, unversioned
JSON `specification`; runs have no traceable link back to the template that defined them;
results carry no status, log, or duration of their own; and byproducts are flat artifact
rows with a single URL and no integrity, provenance, SBOM, or lifecycle information. The
matrix dimensions (`arch`, `flavor`) are denormalized strings rather than a modeled build
matrix.

The purpose of this specification is to define the requirements that evolve the Builds area
into a traceable, verifiable, supply-chain-aware build system: reusable versioned templates,
runs linked to those templates, a first-class build matrix with per-cell results, and
content-addressable, immutable, attested artifacts carrying provenance and SBOMs. Each
requirement is testable and traceable to a concrete ORM entity so that current behavior and
the researched gaps are covered together.

## 2. Personas

- **Release Engineer** — produces multi-flavor product builds across all supported
  `os/arch/flavor` combinations from a release branch, collects all artifacts with traceable
  provenance, and promotes the matched build set to a release.
- **Build / Platform Engineer** — authors and reuses parameterized, versioned build
  templates across many products and branches with safe overrides, and audits which template
  version produced a given build.
- **Security / Compliance Engineer** — audits the supply chain: proves what source,
  dependencies, and toolchain produced a shipped artifact and that it is untampered, using
  digests, provenance attestations, SBOMs, and signatures.
- **Developer** — monitors CI feedback: pushes a change, is notified of build success or
  failure across the matrix, and drills into the specific failing matrix cell and its logs.

## 3. User Workflows

### 3.1 Release engineer producing a multi-flavor product build

1. Select a `BuildTemplate` and the target `Branch` / changelist.
2. Fan out a build matrix across `arch` x `flavor` (and `os`/`version`) dimensions.
3. Each matrix cell produces byproducts (installers, packages) uploaded to a registry.
4. Collect digests, sizes, and SBOMs per byproduct.
5. Promote the matched build set to a release with provenance intact.

**Current pain points:** matrix dimensions exist only as denormalized strings on
`BuildByProduct`, so there is no expected-vs-produced completeness check; there is no
digest/checksum on byproducts so promotion cannot guarantee the same artifact moved forward;
and there is no link from `BuildResult`/`BuildJob` back to the `BuildTemplate`, so the
produced set cannot be validated against the template's declared matrix.

### 3.2 Build/platform engineer authoring and reusing templates

1. Create a `BuildTemplate` with a JSON specification declaring steps and typed parameters.
2. Reference it from many `BuildJob`s supplying branch-specific inputs.
3. Version the template and roll forward without breaking existing jobs.
4. Audit which jobs ran which template version.

**Current pain points:** the JSON `specification` is schemaless and unversioned (no
`spec_version`, no input typing, no validation, no inheritance between `BuildJobTemplate` and
`BuildTemplate`); `BuildJob` has no FK to a template so reuse and "which template/version
produced this" auditing is impossible; and the two near-identical template tables invite
drift.

### 3.3 Security/compliance engineer auditing the supply chain

1. Look up a `BuildByProduct` by digest.
2. Retrieve its provenance attestation (builder, inputs, resolved dependencies).
3. Retrieve the SBOM for license/CVE analysis.
4. Verify the signature and that the digest matches what was deployed.

**Current pain points:** no provenance, SBOM, signature, or attestation fields exist anywhere
in the model; there is no digest to look an artifact up by (only a `result_url` string); and
resolved dependencies, builder identity, and environment are not captured, so the build is
neither reproducible nor auditable.

### 3.4 Developer monitoring CI feedback

1. Push a change to a branch.
2. A build job is triggered (or scheduled nightly).
3. Receive a notification on completion/failure.
4. Drill into the failing matrix cell and its logs.

**Current pain points:** there is no notification/subscription model and no triggered-by user
on `BuildJob`/`BuildResult`; `BuildResult` carries no status/conclusion (status lives only on
`BuildJob`) and no log URL or duration; and there is no per-matrix-cell result, so a failure
cannot be localized to a specific `arch`/`flavor`.

## 4. Functional Requirements

Priorities: P0 (foundational/blocking), P1 (high), P2 (medium), P3 (lower). Requirement IDs
are stable and may be referenced from other specs.

### Existing capabilities (baseline, must be preserved)

| ID | Statement | Priority | Acceptance Criteria |
|----|-----------|----------|---------------------|
| BLD-001 | The system shall persist reusable build job templates with a unique name, optional description, and a JSON specification. | P0 | A `BuildJobTemplate` row stores `name` (unique, non-null, <=128 chars), nullable `description`, and non-null JSON `specification`; inserting a duplicate `name` fails. |
| BLD-002 | The system shall persist reusable build templates with a unique name, optional description, and a JSON specification. | P0 | A `BuildTemplate` row stores `name` (unique, non-null), nullable `description`, non-null JSON `specification`; duplicate `name` rejected. |
| BLD-003 | The system shall record a build job with a name, start time, optional stop time, a change identifier, a status, and the branch it ran against. | P0 | A `BuildJob` persists `name`, `start` (defaults to now), nullable `stop`, non-null `change`, `status` from `WorkPacketStatus`, and a non-null `branch_id` FK; `status` defaults to `QUEUED`. |
| BLD-004 | The system shall record a build result linked 1:1 to a build job and to its branch. | P0 | A `BuildResult` persists `name`, `start`, optional `stop`, `change`, non-null `branch_id`, optional `job_id`; the `BuildJob.result` relationship returns at most one `BuildResult`. |
| BLD-005 | The system shall record build byproducts (artifacts) belonging to a build result, each with product, arch, build number, flavor, and a result URL. | P0 | A `BuildByProduct` persists `product`, `arch`, `buildno`, `flavor`, non-null `result_url`, and a non-null `build_id` FK; deleting the `BuildResult` cascades to its byproducts. |
| BLD-006 | Build job status shall use the shared `WorkPacketStatus` enumeration. | P1 | `BuildJob.status` accepts only `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELED`, `BLOCKED`; an invalid value is rejected. |

### Template versioning, typing, and traceability (Gap: traceability/schemaless templates)

| ID | Statement | Priority | Acceptance Criteria |
|----|-----------|----------|---------------------|
| BLD-010 | Each template specification shall carry an explicit, immutable spec version. | P1 | `BuildJobTemplate` and `BuildTemplate` each expose a non-null `spec_version`; once a template version is referenced by a `BuildJob`, mutating its `specification` requires a new version row rather than in-place edit. |
| BLD-011 | Template specifications shall declare typed, defaulted inputs (string/numeric/boolean) that can be validated. | P1 | A template `specification` validates against a published JSON schema; an input with a declared type and default is enforced; a job supplying a wrong-typed input value is rejected with a descriptive error. |
| BLD-012 | The relationship between `BuildJobTemplate` and `BuildTemplate` shall be explicitly defined (composition/inheritance) so the two tables do not drift. | P1 | The data model documents and enforces how a `BuildTemplate` references or composes one or more `BuildJobTemplate`s; the distinction is queryable (e.g., a FK or join table), not implicit. |
| BLD-013 | A `BuildJob` shall be traceable to the template and template version that defined it. | P1 | `BuildJob` carries a nullable FK to `BuildTemplate` (or `BuildJobTemplate`) plus the resolved `spec_version`; given a `BuildJob` the system can return the exact template version used. |
| BLD-014 | A `BuildJob` shall record the resolved input values used for the run. | P2 | `BuildJob` persists the concrete resolved inputs (JSON); auditing a job returns the exact parameter values applied, distinct from the template defaults. |

### Build matrix as first-class dimensions (Gap: denormalized matrix)

| ID | Statement | Priority | Acceptance Criteria |
|----|-----------|----------|---------------------|
| BLD-020 | The build matrix shall be modeled as explicit dimensions (e.g., os/arch/flavor/version) on the template/job rather than denormalized strings on byproducts. | P1 | A template/job declares matrix dimensions with values; the declared expected cell set is enumerable from the model. |
| BLD-021 | The matrix shall support include and exclude rules for specific combinations. | P2 | Adding an `exclude` removes the targeted cell from the expected set; an `include` adds an otherwise-absent combination; the resulting expected cell set reflects both. |
| BLD-022 | Each produced matrix cell shall have its own result with status/conclusion and identifying dimensions. | P1 | Each cell is represented (as a `BuildResult` or `BuildMatrixCell`) with its own `status`/`conclusion` and `os/arch/flavor/version`, and links to its byproducts; a failure is attributable to one specific cell. |
| BLD-023 | The system shall report expected-vs-produced matrix completeness before promotion. | P1 | Given a job, the system returns which expected cells succeeded, failed, or are missing; promotion of an incomplete matrix is flagged/blocked. |
| BLD-024 | The matrix shall support fail-fast and max-parallel controls. | P3 | A `fail_fast=true` matrix cancels remaining cells on first failure; `max_parallel=N` bounds concurrent cells to N. |

### Artifact integrity, immutability, and lifecycle (Gap: no digest/retention)

| ID | Statement | Priority | Acceptance Criteria |
|----|-----------|----------|---------------------|
| BLD-030 | Every byproduct shall be content-addressable via a SHA-256 digest. | P0 | `BuildByProduct` carries a non-null `digest` (sha256); the digest is indexed and unique per content; a byproduct can be looked up by digest. |
| BLD-031 | Every byproduct shall record size and content type. | P0 | `BuildByProduct` carries `size_bytes` (non-null, >=0) and `content_type`/mime; both are returned on lookup. |
| BLD-032 | Published byproducts shall be immutable; any change yields a new record preserving the original digest. | P0 | Attempting to alter the content referenced by an existing digest is rejected; a content change produces a new `BuildByProduct` with a new digest while the original remains retrievable. |
| BLD-033 | Byproducts shall carry retention/expiry metadata. | P1 | `BuildByProduct` carries `created_at` and `expires_at` (and/or `immutable` flag); a lifecycle process can identify byproducts past `expires_at` for cleanup. |
| BLD-034 | Promotion of a build set shall preserve digests and metadata unchanged. | P1 | Promoting a build set from one stage to another retains identical digests and labels for every byproduct; a mismatch fails the promotion. |

### Provenance, SBOM, and attestation (Gap: no supply-chain metadata)

| ID | Statement | Priority | Acceptance Criteria |
|----|-----------|----------|---------------------|
| BLD-040 | The system shall record signed build provenance for each build (SLSA buildDefinition + runDetails). | P0 | A provenance record (1:1 with `BuildResult` or `BuildByProduct`) captures `buildType`, builder identity, external/internal parameters, invocation metadata (start/finish/invocation-id), and a signature/attestation blob sufficient to satisfy SLSA Build L1. |
| BLD-041 | Provenance shall capture resolved dependencies. | P0 | The provenance record stores `resolvedDependencies` (with hashes) as JSON or a child table; an auditor can list every resolved input dependency and its hash. |
| BLD-042 | Each byproduct shall reference an SBOM. | P0 | `BuildByProduct` (or its provenance) carries an SBOM reference: URL + digest + format (SPDX or CycloneDX); the SBOM is retrievable and its digest verifiable. |
| BLD-043 | Byproduct signatures/attestations shall be verifiable. | P0 | Given a byproduct, the system returns a signature/attestation that verifies against the recorded digest; a tampered digest fails verification. |
| BLD-044 | An auditor shall, starting from a digest, retrieve provenance and SBOM in one traversal. | P1 | Looking up a `BuildByProduct` by digest yields its provenance (builder, inputs, resolved deps) and SBOM reference without additional unindexed scans. |

### Operational result fields (Gap: BuildResult lacks status/logs/duration)

| ID | Statement | Priority | Acceptance Criteria |
|----|-----------|----------|---------------------|
| BLD-050 | `BuildResult` shall carry its own status/conclusion. | P2 | `BuildResult` has a `conclusion`/`status` column independent of `BuildJob.status`; a result can be `SUCCEEDED` while sibling cells are `FAILED`. |
| BLD-051 | `BuildResult` shall record a log URL and a duration. | P2 | `BuildResult` carries `log_url` and a derived/stored `duration`; both are returned with the result. |
| BLD-052 | `BuildResult` shall capture the executing environment/agent. | P2 | `BuildResult` records `environment`/`agent` (e.g., runner identity, toolchain versions); the value is queryable for debugging. |
| BLD-053 | Redundant duplication of `change`/`branch` between `BuildJob` and `BuildResult` shall be removed where the job already carries it. | P3 | Where a `BuildResult` has a non-null `job_id`, `change`/`branch` are sourced from the `BuildJob`; the model does not require maintaining two copies in sync. |

### Triggers, scheduling, concurrency, notifications (Gap: no lifecycle controls)

| ID | Statement | Priority | Acceptance Criteria |
|----|-----------|----------|---------------------|
| BLD-060 | `BuildJob` shall record who/what triggered the run. | P2 | `BuildJob` carries `triggered_by` (FK to `User`) and `trigger_type` (e.g., on-push, scheduled, manual); both are populated and queryable. |
| BLD-061 | `BuildJob` shall record a queued/start/stop time breakdown. | P2 | `BuildJob` distinguishes queue time from execution start; queue duration and run duration are both derivable. |
| BLD-062 | The system shall support scheduled and triggered builds. | P3 | A schedule descriptor (cron/on-push) can be attached so that a build is created automatically at the scheduled cadence or on the configured event. |
| BLD-063 | The system shall enforce concurrency control per branch/group. | P3 | A `concurrency_group` on `BuildJob` permits at most one active build per group; a second concurrent start for the same group is queued or rejected. |
| BLD-064 | The system shall support notification subscriptions on build events. | P3 | A subscription entity stores a target channel and events (completed/failed/cancelled); on the corresponding event a notification is emitted to the subscribed channel. |

### Caching, hermeticity, reproducibility (Gap: no input pinning/cache)

| ID | Statement | Priority | Acceptance Criteria |
|----|-----------|----------|---------------------|
| BLD-070 | The system shall record pinned/resolved dependency hashes for a build. | P2 | A build (job or provenance) records each resolved dependency with its hash; rerunning with identical declared inputs resolves to identical hashes. |
| BLD-071 | The system shall record a deterministic cache key / input hash per build. | P2 | A `cache_key`/input-hash is stored on `BuildJob` or provenance; two builds with identical inputs produce the same key, enabling cache-hit matching. |
| BLD-072 | The system shall record toolchain/environment versions used. | P2 | Toolchain and environment versions are captured (on `BuildResult` or provenance) such that reproducibility of a past build can be assessed. |

## 5. Non-Functional Requirements

- **Reliability** — Result and byproduct records are the system of record; cascade deletes
  (`BuildResult` -> `BuildByProduct`) must be transactional so no orphaned or partial
  artifact rows remain. Promotion and provenance writes must be atomic with the artifact
  record.
- **Debuggability** — Failures must be localizable to a single matrix cell (BLD-022) with a
  retrievable `log_url`, `duration`, and `environment` (BLD-051, BLD-052). Status must be
  distinguishable per result, not only per job. Error messages on validation failures
  (typed inputs, completeness, signature mismatch) must be descriptive and built per the
  repository's multiline error-message convention.
- **Scale** — Byproduct lookup by `digest` must be indexed (BLD-030) for content-addressable
  retrieval at registry scale. Retention/expiry (BLD-033) must allow bounded storage growth.
  Matrix completeness queries must not require full-table scans of byproducts.
- **Security / Supply chain** — Every build must carry signed provenance (BLD-040), an SBOM
  (BLD-042), and a verifiable signature (BLD-043); published artifacts must be immutable
  (BLD-032). Build execution should be separable from source control so no single system
  controls both. Digests must use SHA-256.
- **Integrity** — Content addressing must guarantee that a given digest always refers to
  identical content; deduplication and promotion rely on this invariant.

## 6. Best Practices Adopted

- Generate signed build provenance (SLSA buildDefinition + runDetails: buildType, external
  parameters, resolved dependencies, builder identity, invocation metadata) for every build —
  https://slsa.dev/spec/v1.0/provenance (BLD-040, BLD-041).
- Address artifacts by content (sha256 digest), store metadata as labels, and treat published
  artifacts as immutable with checksum preserved through promotion —
  https://oneuptime.com/blog/post/2026-02-17-how-to-tag-and-manage-docker-image-versions-in-artifact-registry/view
  (BLD-030, BLD-032, BLD-034).
- Generate an SBOM for every build, store it alongside the artifact, and reference it from
  provenance — https://petronellatech.com/blog/from-sbom-to-slsa-securing-your-software-supply-chain/
  (BLD-042).
- Make builds hermetic and reproducible by declaring and hash-pinning all dependencies —
  https://beefed.ai/en/hermetic-build-playbook (BLD-070, BLD-071, BLD-072).
- Model the build matrix as first-class dimensions with include/exclude, fail-fast, and
  max-parallel — https://docs.github.com/actions/using-jobs/using-a-matrix-for-your-jobs
  (BLD-020, BLD-021, BLD-024).
- Define reusable, parameterized build templates as versioned specifications with typed
  inputs and composition — https://docs.gitlab.com/ci/yaml/ (BLD-010, BLD-011, BLD-012).
- Cache expensive inputs keyed deterministically and apply retention/TTL policies —
  https://depot.dev/docs/cache/overview (BLD-033, BLD-071).
- Run builds on a platform separated from source control, attach status/conclusion, and emit
  completion/failure/cancellation notifications —
  https://github.com/github/awesome-copilot/blob/main/instructions/github-actions-ci-cd-best-practices.instructions.md
  (BLD-050, BLD-064).
- Support scheduled/triggered builds and concurrency control with locking —
  https://circleci.com/docs/workflows (BLD-062, BLD-063).

## 7. Data Model Traceability

| Entity | Owned / Affected Requirements |
|--------|-------------------------------|
| `BuildJobTemplate` | BLD-001, BLD-010, BLD-011, BLD-012 |
| `BuildTemplate` | BLD-002, BLD-010, BLD-011, BLD-012, BLD-013, BLD-020, BLD-021 |
| `BuildJob` | BLD-003, BLD-006, BLD-013, BLD-014, BLD-020, BLD-024, BLD-060, BLD-061, BLD-062, BLD-063, BLD-070, BLD-071 |
| `BuildResult` | BLD-004, BLD-022, BLD-023, BLD-040, BLD-041, BLD-050, BLD-051, BLD-052, BLD-053, BLD-072 |
| `BuildByProduct` | BLD-005, BLD-030, BLD-031, BLD-032, BLD-033, BLD-034, BLD-042, BLD-043, BLD-044 |
| New / cross-cutting (provenance, matrix cell, subscription, schedule) | BLD-022 (BuildMatrixCell), BLD-040–044 (Provenance/Attestation), BLD-064 (Subscription), BLD-062–063 (Schedule/Concurrency) |
| Shared (`WorkPacketStatus`, `User`, `Branch`) | BLD-006 (status enum), BLD-060 (triggered_by → User), BLD-003/BLD-004 (branch_id → Branch) |

## 8. Open Questions

- **Template hierarchy** — Should `BuildTemplate` compose `BuildJobTemplate`s via a FK/join
  table, or should one inherit from the other? The current two undifferentiated tables must
  be reconciled before BLD-012/BLD-013 can be implemented.
- **Provenance ownership** — Should provenance/attestation attach 1:1 to `BuildResult` or per
  `BuildByProduct`? Per-byproduct gives finer granularity but more rows; per-result is
  simpler but less precise for multi-artifact results.
- **Matrix cell representation** — Reuse `BuildResult` as the per-cell record, or introduce a
  dedicated `BuildMatrixCell` entity? This affects BLD-022/BLD-023 and the `BuildResult`
  1:1-with-`BuildJob` relationship.
- **Digest uniqueness scope** — Is the digest globally unique (true content addressing across
  all products) or unique per product? Affects deduplication and the BLD-030 index/constraint.
- **Retention authority** — Does the Builds area own retention/expiry enforcement, or does a
  separate storage/lifecycle area act on `expires_at`? Cross-area dependency for BLD-033.
- **Notification transport** — Which channels (Slack/Teams/email) and which subsystem
  delivers them? BLD-064 needs a cross-area integration decision.
- **Status duplication** — If `BuildResult` gains its own status (BLD-050), what is the
  authoritative rollup rule from per-cell results to the parent `BuildJob.status`?
- **Cache backend** — Where do cache keys (BLD-071) resolve to actual cached content, and is
  that storage in scope for the Builds area or external?
