# Releases — Requirements

## 1. Overview

The Releases area of Pychestrate models how a product is cut, stabilized, promoted, and
shipped from a **release train**. A release train describes a reusable, symbolic branch
topology (team → integration → mainline → support lines); individual **releases** bind that
topology to literal repository branches, builds, and ship dates for a specific product.

The area is implemented today by five entities in
`source/packages/automojo/pychestrate/core/storage/orm.py`:

- `ReleaseTrain` (orm.py:262) — named, product-agnostic container for a symbolic branch topology and its releases.
- `ReleaseTrainBranchType` (orm.py:285) — enum: `TEAM`, `INTEGRATION`, `MAINLINE`, `SUPPORT`, `OTHER`.
- `ReleaseTrainBranch` (orm.py:295) — a symbolic branch with `branch_type`, `display_order`, `is_terminal`, JSON `metadata_payload`, and a self-referential `parent_id` tree.
- `Release` (orm.py:348) — a product release: `name`, `description`, `documentation_url`, `start_date`, `release_date`, required `product_id`, optional `release_train_id`.
- `ReleaseBranchAssignment` (orm.py:382) — maps one symbolic branch to a single `literal_branch_name` string per release.

The current schema can answer *"which symbolic branches exist in a train and what are they
called for a given release."* It **cannot** answer the operational questions a CI release
product must answer: what version is this, what is its lifecycle state, which commit/build/tag
is it pinned to, which environments has it been promoted to, what gates/approvals were
satisfied, and which fixes were cherry-picked between branches. This document specifies the
requirements to close those gaps while preserving the existing topology model.

## 2. Personas

- **Release Manager** — cuts, stabilizes, and ships a release from a train with full traceability of its contents.
- **Developer / Tech Lead** — ports a bug fix from trunk into an active release branch and proves it landed there.
- **Release Approver / QA / Compliance** — reviews evidence and signs off that a release may promote to a protected environment.
- **Product Owner / Stakeholder** — views the status, version, schedule, and contents of upcoming and past releases across a train.

## 3. User Workflows

### Workflow A — Release Manager: cut, stabilize, ship (REL-related: REL-001..REL-014)

1. Create a `Release` tied to a `Product` and `ReleaseTrain`, and assign a target **version**.
2. Cut a literal release branch from the mainline symbolic branch a few days before ship.
3. Record a `ReleaseBranchAssignment` mapping each symbolic branch to its literal branch.
4. **Pin the exact commit/build** the release is built from and tag it.
5. Open a **freeze / stabilization window** on the release line.
6. Promote the build through staging then production once gates pass.
7. Mark the release **released** with the **actual** ship date and publish release notes.

Current pain points: `Release` has no version, status, or commit/tag pointer ("what exactly
shipped" is unrecordable); no freeze flag exists; `ReleaseBranchAssignment` stores only a
branch-name string with no link to the real `Branch`, build, or commit.

### Workflow B — Developer / Tech Lead: port a fix (REL-related: REL-015..REL-018)

1. Reproduce and fix the bug on the trunk/mainline symbolic branch.
2. Flag the fix PR as **needing to be ported** to the release line.
3. Cherry-pick (or back-merge) the fix onto the literal release branch.
4. Verify a build on the release branch confirms the fix.
5. Confirm parity so the fix is not lost on the next release.

Current pain points: no entity records a cherry-pick/back-merge between branches or releases;
assignments carry no commit SHA, so you cannot tell whether a given fix commit is present;
there is no way to flag "this change must be ported."

### Workflow C — Approver / QA / Compliance: sign off (REL-related: REL-019..REL-023)

1. Inspect the release's pinned build, test results, and changelog.
2. Confirm required **automatic gates** (tests, scans) passed.
3. Provide a **manual approval** for promotion to staging, then production.
4. Have the approval and approver recorded for audit.

Current pain points: no approval/gate/reviewer entity; no per-environment promotion records to
gate each stage independently; no `created_at`/`updated_at` so state-change history is lost.

### Workflow D — Product Owner / Stakeholder: view status (REL-related: REL-024..REL-027)

1. Open the release train and list its releases and lifecycle states.
2. View each release's version, **target vs actual** ship date, and changelog.
3. See which environments each release currently occupies.

Current pain points: a single `release_date` with no target-vs-actual and no status enum;
no structured changelog; `ReleaseTrain` has no cadence or owner.

## 4. Functional Requirements

Priorities: **P0** foundational identity/traceability, **P1** lifecycle/promotion/approval,
**P2** fix propagation, **P3** governance/audit baselines.

| ID | Statement | Priority | Acceptance Criteria |
|----|-----------|----------|---------------------|
| REL-001 | A `Release` SHALL retain its existing required `product_id` FK and optional `release_train_id` FK and unique `(prod_id, release_name)` constraint. | P0 | Creating two releases with the same name under one product is rejected; the same name under different products is allowed; a release may be created with a null train. |
| REL-002 | A `Release` SHALL carry a required semantic version (`release_version`, `MAJOR.MINOR.PATCH` with optional pre-release/build metadata). | P0 | Persisting a release without a valid SemVer string is rejected with a descriptive error; `1.2.3`, `1.2.3-rc.1`, `1.2.3+build.5` are accepted; `1.2` is rejected. |
| REL-003 | Release version SHALL be unique within a product: uniqueness on `(prod_id, release_version)`. | P0 | Two releases with version `2.0.0` under the same product are rejected; identical versions under different products are allowed. |
| REL-004 | A `Release` SHALL store structured release notes / changelog (Text or JSON), distinct from the existing free-text `documentation_url`. | P0 | A release can be saved and retrieved with a multi-entry changelog payload; `documentation_url` remains independently settable. |
| REL-005 | The release version and changelog fields SHALL be populatable by conventional-commit automation (e.g. semantic-release) without schema change. | P0 | An automated writer can set version + changelog via the standard create/update API; round-trip read returns identical content. |
| REL-006 | A `Release` SHALL be pinnable to an immutable commit SHA and a tag. | P0 | A release records a 40-char (or provider-native) commit SHA and a tag string; both are retrievable and immutable once the release reaches `RELEASED` (REL-008). |
| REL-007 | `ReleaseBranchAssignment` SHALL reference the real `Branch` entity via FK (denormalized `literal_branch_name` MAY be retained) and MAY pin a per-assignment commit SHA and an optional `BuildResult` FK. | P0 | An assignment can be created with a `Branch` FK; an assignment with an orphan/non-existent branch reference is rejected; the existing unique `(release_id, rtbranch_id)` constraint is preserved; build/commit, when set, round-trips. |
| REL-008 | A `Release` SHALL have a lifecycle status enum `ReleaseStatus` = {`PLANNED`, `IN_DEVELOPMENT`, `STABILIZING`, `FROZEN`, `RELEASED`, `DEPRECATED`}, defaulting to `PLANNED`. | P1 | A new release reads back as `PLANNED`; status can transition through the enum values; an invalid status value is rejected. |
| REL-009 | Lifecycle transitions SHALL be constrained so that `RELEASED` requires a non-null pinned commit (REL-006) and a non-null actual ship date (REL-012). | P1 | Attempting to mark a release `RELEASED` without a pinned commit or actual ship date raises a `SemanticError`-class validation error and is not persisted. |
| REL-010 | A stabilization/freeze window SHALL be representable: a `frozen` boolean plus freeze-window start/end timestamps on the release (or on its stabilization `ReleaseTrainBranch`). | P1 | A release can be marked frozen with a window; querying returns the freeze state and window; clearing the freeze restores an unfrozen state. |
| REL-011 | An `Environment` entity (e.g. `dev`, `staging`, `production`) SHALL exist as a first-class, named, orderable record. | P1 | Environments can be created, named uniquely, and ordered; a release promotion can reference an environment by FK. |
| REL-012 | A `ReleasePromotion` entity SHALL record `(release, environment, build/commit, promoted_at, promoted_by, status)`. The production promotion's `promoted_at` SHALL serve as the **actual** ship date; `Release.release_date` SHALL be retained as the **target** date. | P1 | A release can record multiple promotions across environments; each promotion stores who/when/what; the actual production promotion is distinguishable from the target `release_date`. |
| REL-013 | Each `ReleasePromotion` SHALL carry a status (e.g. `PENDING`, `SUCCEEDED`, `FAILED`, `ROLLED_BACK`). | P1 | Promotion status is settable and queryable; an invalid status is rejected. |
| REL-014 | The promotion model SHALL support building an artifact once and promoting the same immutable commit/build across environments (no per-environment recompute requirement). | P1 | Two promotions for one release to different environments can reference the identical commit SHA / `BuildResult`. |
| REL-015 | A `ChangePropagation` entity SHALL record `(source_branch/commit, destination ReleaseTrainBranch/release, propagation_type, status, optional approver)`. | P2 | A cherry-pick record links a source commit/branch to a destination release branch; it round-trips with type and status. |
| REL-016 | `ChangePropagation.propagation_type` SHALL be an enum {`CHERRY_PICK`, `BACK_MERGE`}. | P2 | Only the two valid types are accepted; any other value is rejected. |
| REL-017 | `ChangePropagation.status` SHALL be an enum {`REQUESTED`, `APPLIED`, `VERIFIED`}; a `REQUESTED` record represents an outstanding (forgotten-port) obligation. | P2 | Outstanding ports are queryable by status `REQUESTED`; status can advance to `APPLIED` then `VERIFIED`. |
| REL-018 | The system SHALL allow flagging a change/PR against a release as "must be ported" so unported fixes surface. | P2 | A fix can be flagged against a release; the flag appears as an outstanding `ChangePropagation` (`REQUESTED`) until applied/verified. |
| REL-019 | A `ReleaseApproval` (deployment-gate) entity SHALL link a release/promotion to an approver (`User`), a gate type, a decision, an evidence reference, and a timestamp. | P1 | An approval record references a `User`, stores decision + evidence + timestamp, and round-trips. |
| REL-020 | `ReleaseApproval.gate_type` SHALL distinguish automatic gates (tests, security scans) from manual gates (required reviewer). | P1 | Both gate types are representable; the type is queryable. |
| REL-021 | Promotion to a protected environment SHALL be blockable until its required approvals/gates are satisfied. | P1 | A protected-environment promotion with an unsatisfied required gate cannot reach `SUCCEEDED`; once gates pass, it may proceed. |
| REL-022 | Required-reviewer rules SHALL be configurable per environment. | P1 | An environment can declare required approvers; a promotion to it is gated until those approvals exist. |
| REL-023 | Every approval decision SHALL be auditable: who, what evidence, when. | P1 | Each approval exposes approver identity, evidence reference, and a UTC timestamp. |
| REL-024 | A `ReleaseTrain` SHALL retain its unique `name` and SHALL gain an optional `Product` FK so trains can be scoped per product (a null product keeps the existing global behavior). | P3 | A train can be created globally (null product) or scoped to a product; existing unique name constraint preserved. |
| REL-025 | A `ReleaseTrain` SHALL gain a cadence descriptor and an owner attribution. | P3 | A train can record cadence and an owner; both round-trip; absent values are permitted for legacy trains. |
| REL-026 | `ReleaseTrain`, `ReleaseTrainBranch`, `Release`, and `ReleaseBranchAssignment` SHALL each gain `created_at` and `updated_at` columns (UTC, `onupdate`), matching the `User` model pattern (orm.py:724-725). | P3 | Creating a row sets `created_at`; any update advances `updated_at`; both are timezone-aware UTC. |
| REL-027 | The above four entities SHALL gain an owner / `created_by` `User` FK for accountability. | P3 | Each entity records its creator; the creator is retrievable for audit. |
| REL-028 | `ReleaseTrainBranch` SHALL retain its existing topology fields (`branch_type`, `display_order`, `is_terminal`, `metadata_payload`, `parent_id` tree) and the unique `(rtrain_id, rtbranch_name)` constraint. | P0 | Existing topology behavior is unchanged; the parent/child tree and unique constraint still hold. |
| REL-029 | `ReleaseTrainBranch` SHALL be able to declare promotion direction and/or environment binding beyond raw parent hierarchy (e.g. a `promotes_to` reference or environment column). | P3 | A symbolic branch can declare the branch it promotes to and/or a bound environment; code-flow direction becomes explicit and queryable. |

## 5. Non-Functional Requirements

- **Reliability / Data Integrity (NFR-1):** All new FKs (`Branch`, `BuildResult`, `User`, `Environment`, train `Product`) SHALL enforce referential integrity; orphaned references are rejected. Once a release is `RELEASED`, its pinned commit/tag SHALL be immutable.
- **Debuggability (NFR-2):** Validation failures (bad SemVer, illegal lifecycle transition, missing gate) SHALL raise descriptive, multi-line error messages naming the offending field/value, per the project error-message standard. API misuse SHALL raise `SemanticError` (must bubble); environment/config issues SHALL raise `ConfigurationError`.
- **Scalability (NFR-3):** Promotion, approval, and change-propagation tables SHALL be indexed on their `release_id` (and `environment_id` where applicable) so a release's full history is retrievable without table scans, consistent with existing `index=True` usage on FKs in this area.
- **Auditability / Security (NFR-4):** Every state-changing entity SHALL record `created_at`/`updated_at` and a `created_by`/approver `User` reference; approval and promotion records SHALL be append-style audit trails (no silent overwrite of who/when).
- **Backward Compatibility (NFR-5):** New columns SHALL be additive and nullable or defaulted so existing `ReleaseTrain`/`Release` rows remain valid; the existing unique constraints `uq_release_product_name`, `uq_release_train_branch`, and `uq_release_branch_assignment` SHALL be preserved.

## 6. Best Practices Adopted

- Cut release branches just-in-time from trunk, keep the branch short-lived, and tag the exact released commit (drives REL-006, REL-010) — https://trunkbaseddevelopment.com/branch-for-release/
- Standardize fix propagation (cherry-pick first, then back-merge) and track which commits landed on which branch (drives REL-015..REL-018) — https://www.runway.team/blog/cherry-picks-vs-backmerges-whats-the-right-way-to-get-fixes-into-your-release-branch
- Build the artifact once and promote the same immutable artifact through dev → staging → production (drives REL-011..REL-014) — https://gearset.com/blog/release-branches-in-cicd/
- Gate promotions with explicit automatic and manual deployment-protection rules (drives REL-019..REL-023) — https://docs.gitlab.com/ci/environments/deployment_approvals/
- Automate SemVer versioning and changelog generation from conventional commits (drives REL-002..REL-005) — https://github.com/semantic-release/semantic-release
- Model an explicit release lifecycle with freeze/code-slush windows (drives REL-008..REL-010) — https://trunkbaseddevelopment.com/branch-for-release/
- Use a parent/child topology with explicit promotion direction per line (drives REL-028, REL-029) — https://knowledgebase.autorabit.com/product-guides/arm/troubleshoot/best-practices/branching-strategy-and-ci-cd-pipeline
- Attach standardized metadata and audit trails (timestamps, owner, immutable tags) to every release and promotion (drives REL-024..REL-027) — https://gearset.com/blog/release-branches-in-cicd/

## 7. Data Model Traceability

| Entity (orm.py) | Requirements | Notes |
|-----------------|-------------|-------|
| `ReleaseTrain` (262) | REL-024, REL-025, REL-026, REL-027 | Gains optional `Product` FK, cadence, owner, audit columns; keeps unique name. |
| `ReleaseTrainBranch` (295) | REL-010, REL-026, REL-027, REL-028, REL-029 | Keeps topology + unique `(rtrain_id, rtbranch_name)`; gains freeze fields, audit columns, promotion direction/environment binding. |
| `ReleaseTrainBranchType` (285) | REL-029 | Role enum retained; promotion direction expressed on the branch, not the type. |
| `Release` (348) | REL-001..REL-014, REL-019, REL-026, REL-027 | Gains version, changelog, status, commit/tag, freeze; `release_date` becomes the target date with actual via production promotion. |
| `ReleaseBranchAssignment` (382) | REL-007 | Gains `Branch` FK, optional commit SHA, optional `BuildResult` FK; keeps unique `(release_id, rtbranch_id)`. |
| New: `Environment` | REL-011, REL-022 | First-class named/orderable stage; carries required-reviewer rules. |
| New: `ReleasePromotion` | REL-012, REL-013, REL-014, REL-021 | Per-stage promotion record; production promotion supplies actual ship date. |
| New: `ReleaseApproval` / DeploymentGate | REL-019, REL-020, REL-021, REL-022, REL-023 | Links release/promotion to approver `User`, gate type, decision, evidence. |
| New: `ChangePropagation` | REL-015, REL-016, REL-017, REL-018 | Cherry-pick / back-merge tracking between branches/releases. |

Cross-area references: `Product` (existing), `Branch` (orm.py:433), `BuildResult` (orm.py:474),
`User` (orm.py:724-725).

## 8. Open Questions

1. **Version source of truth** — Should `release_version` be writable only by the semantic-release automation, or also editable by the Release Manager? Need a write-authority decision (REL-002, REL-005).
2. **Commit pin location** — Pin the commit/tag on `Release` only, on each `ReleaseBranchAssignment`, or both? A release spanning multiple repos may need per-assignment pins (REL-006, REL-007).
3. **Changelog representation** — Free Text vs structured JSON (entries, categories, breaking-change flags)? Structured form enables publishing but adds schema cost (REL-004).
4. **`Branch` entity coupling** — Confirm `Branch` (orm.py:433) carries repository scoping sufficient to replace `literal_branch_name`; whether to keep the denormalized name for branches not yet ingested (REL-007).
5. **`BuildResult` linkage** — `BuildResult` (orm.py:474) has a `change` field but no `Release` link; decide direction of the FK and whether it is on `Release`, `ReleaseBranchAssignment`, or `ReleasePromotion` (REL-007, REL-012, REL-014).
6. **Lifecycle transition engine** — Are transitions enforced in the ORM layer, a service layer, or via DB constraints/triggers? Affects where REL-009 validation lives.
7. **Freeze placement** — Freeze window on `Release` vs on the stabilization `ReleaseTrainBranch` (a branch may be reused across releases) (REL-010).
8. **Gate evidence model** — Is "evidence reference" a URL, an FK to a test/scan result entity, or both? Depends on whether CI results are modeled elsewhere (REL-019, REL-020).
9. **Protected-environment policy ownership** — Where do required-reviewer rules live: on `Environment`, on `ReleaseTrain`, or per `Product`? (REL-022).
10. **Train product scoping migration** — Making `ReleaseTrain` product-scoped (REL-024) changes its global semantics; need a migration/back-compat plan for existing global trains.
