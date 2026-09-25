# Projects — Requirements

## 1. Overview

The Projects functional area defines how Pychestrate catalogs the software products it
builds and the source repositories those products are assembled from. It is the entry
point for every CI workflow: before Pychestrate can clone code, watch branches, or trigger
builds, a product and its source topology must be registered here.

The area is implemented by five SQLAlchemy entities in
`source/packages/ccai/pychestrate/core/storage/orm.py`:

- **Product** (`orm.py:186`) — a named, uniquely-identified product composed of one or more
  components, with relationships to its components, product-scoped repositories, and releases.
- **ProductComponent** (`orm.py:217`) — a named child of a product that maps to exactly one
  source repository (`repo_id` NOT NULL), unique per `(prod_id, comp_name)`.
- **ProductToRepository** (`orm.py:241`) — a thin association attaching product-scoped
  repositories (for example documentation) to a product, unique per `(prod_id, repo_id)`.
- **Repository** (`orm.py:413`) — the richest entity: `name`, unique `url`, `repotype`
  (CODE/DOCUMENTATION), `scope` (PRODUCT/LOCAL), and an unstructured `repoconf` JSON blob.
- **Branch** (`orm.py:433`) — `name`, a free-text `owner` VARCHAR, and a `repo_id` FK, unique
  per `(repo_id, branch_name)`.

The current model is adequate to enumerate *which repositories make up a product* but is thin
on provisioning, security, lifecycle, and ownership semantics expected of a CI service. This
specification captures both the existing capabilities and the gaps that must be closed for the
area to drive credentialed cloning, webhook-driven CI, branch governance, and ownership-based
access control. Requirements are intentionally traceable to the entities above so they can be
referenced during design and implementation.

## 2. Personas

- **Release/Build Engineer (onboarding)** — registers a new product, its component
  repositories, and SCM connectivity so CI can clone, watch branches, and run builds.
- **Platform/DevOps Engineer (SCM integration)** — connects SCM providers and webhooks so
  Pychestrate auto-discovers branches and triggers builds on push/PR events from GitHub/GitLab.
- **Engineering Manager / Repository Owner (governance)** — needs to see who owns each
  product/component, enforce branch protection, and clean up stale branches and deprecated
  components.

## 3. User Workflows

### Workflow A — Onboard a new product (Release/Build Engineer)

1. Create a Product with name and description.
2. Register each component's Repository (URL, type CODE/DOCUMENTATION).
3. Create a ProductComponent linking the product to each repository.
4. Attach product-scoped repositories (for example docs) via ProductToRepository.
5. Provide credentials so the system can clone the repositories.
6. Configure which branches CI should watch, including the default branch.

Current pain points: no structured place for credentials except the free-form `repoconf` JSON
blob (plaintext-secret risk); a monorepo cannot be registered once and split into several
components by sub-path — each component must be a whole repository; there is no default-branch
concept; there is no owner field on Product/Component/Repository.

### Workflow B — Integrate SCM webhooks (Platform/DevOps Engineer)

1. Connect a provider (GitHub App / deploy key / PAT) to a repository.
2. Register a webhook endpoint and signing secret.
3. Receive push/PR events and reconcile Branch rows.
4. Update each branch's head SHA and last-activity on every event.
5. Trigger BuildJob for the affected components.

Current pain points: no fields for provider identity (host/org/slug), webhook URL, or webhook
secret — webhook integration has no schema; Branch has no head-SHA or last-seen column, so
reconciliation against provider state cannot be persisted; no path scoping means a webhook on a
monorepo cannot map a changed path to the right component; no provider auth-type field exists to
decide between SSH deploy key and HTTPS token clone.

### Workflow C — Govern ownership and branch hygiene (Engineering Manager / Owner)

1. List products and components with their owning team/user.
2. Identify default and protected branches per repository.
3. Review branch protection (required reviews / required status checks).
4. Find branches with no recent activity.
5. Decommission stale branches and deprecated components.

Current pain points: ownership is unqueryable (Branch.owner is free text; Product/Component/
Repository have no owner FK); no branch-protection or default-branch metadata to govern; no
lifecycle/status to mark deprecated/archived (deletion is a hard cascade with no soft-delete);
no timestamps anywhere in the Projects area, so stale-branch and audit reporting is impossible.

## 4. Functional Requirements

Priority key: P0 = blocks core CI workflows / security-critical; P1 = governance and
reconciliation; P2 = maturity and structural modeling; P3 = nice-to-have.

### Existing capabilities (must be preserved)

| ID | Statement | Priority | Acceptance Criteria |
|----|-----------|----------|---------------------|
| PROJ-001 | A Product is uniquely identified by name and carries a description. | P0 | Creating two products with the same `prod_name` fails on the unique constraint; a product persists `id`, `name`, `description`. |
| PROJ-002 | A Product aggregates components, product-scoped repositories, and releases. | P0 | Product exposes `components`, `product_repositories`, and `releases` relationships; deleting a product cascades to its `ProductComponent` and `ProductToRepository` rows. |
| PROJ-003 | A ProductComponent is a named child of a product mapped to exactly one repository. | P0 | A component requires a non-null `prod_id` and `repo_id`; `(prod_id, comp_name)` is unique (`uq_component_product_name`); two components in the same product cannot share a name. |
| PROJ-004 | A ProductToRepository attaches a product-scoped repository to a product. | P1 | `(prod_id, repo_id)` is unique (`uq_product_repository`); the same repository cannot be attached to the same product twice. |
| PROJ-005 | A Repository records name, unique URL, content type, and scope. | P0 | `url` is unique; `repotype` accepts only CODE/DOCUMENTATION; `scope` accepts only PRODUCT/LOCAL; `(repo_name, repo_repository)` unique constraint is enforced. |
| PROJ-006 | A Branch belongs to a repository and is unique by name within it. | P0 | `(repo_id, branch_name)` is unique (`uq_branch_repo_name`); a branch requires a non-null `repo_id`; deleting a repository cascades to its branches. |

### Secrets and provider identity (gap closure)

| ID | Statement | Priority | Acceptance Criteria |
|----|-----------|----------|---------------------|
| PROJ-010 | Repository SHALL persist structured SCM provider identity decomposed from the URL. | P0 | Repository gains `provider` (enum: github/gitlab/bitbucket/other), `provider_host`, `org_namespace`, and `repo_slug`; given a registered URL the four fields are populated and queryable; a repository can be looked up by `(provider, org_namespace, repo_slug)`. |
| PROJ-011 | Repository SHALL declare its SCM auth mechanism. | P0 | Repository gains `auth_type` (enum: github_app/deploy_key/pat/ssh); the value drives whether clone uses SSH or HTTPS; a repository with `auth_type=deploy_key` is treated as single-repo, read-only. |
| PROJ-012 | SCM credentials SHALL be referenced via an external secret store, never stored inline. | P0 | Repository gains a `credential_ref` pointing to an external secret entry (Vault/cloud secret manager/platform secret); no plaintext secret is accepted into `repoconf` or any column; a schema validator rejects `repoconf` payloads containing secret-shaped keys (token/password/private_key). |
| PROJ-013 | `repoconf` SHALL be constrained to non-secret configuration with a validated schema. | P1 | `repoconf` writes are validated against a published schema; unknown or secret-bearing keys are rejected with a descriptive error; existing non-secret config continues to load. |

### Webhook and event integration (gap closure)

| ID | Statement | Priority | Acceptance Criteria |
|----|-----------|----------|---------------------|
| PROJ-020 | The system SHALL model webhook registration per repository. | P0 | A `RepositoryWebhook` entity (or equivalent columns) persists `webhook_url`, a `secret_ref` (external secret), subscribed `event_types` (push/pull_request/tag), `provider_webhook_id`, `is_active`, and `last_delivery_at`; a repository can have its webhook registered and toggled active/inactive. |
| PROJ-021 | The system SHALL reconcile Branch rows from received SCM events. | P0 | On a push/PR event a matching Branch is created if absent and updated if present; reconciliation is idempotent for repeated deliveries of the same event. |
| PROJ-022 | A webhook secret SHALL be verifiable and referenced, not stored plaintext. | P0 | `secret_ref` resolves to an external secret used to verify provider signatures; an event failing signature verification is rejected and logged; no plaintext webhook secret is persisted in a column. |

### Branch lifecycle and SCM state (gap closure)

| ID | Statement | Priority | Acceptance Criteria |
|----|-----------|----------|---------------------|
| PROJ-030 | A Branch SHALL record whether it is the repository default branch. | P1 | Branch gains `is_default` (bool); at most one branch per repository may be default; the default branch is selectable by query. |
| PROJ-031 | A Branch SHALL record protection state and rules. | P1 | Branch gains `is_protected` (bool) and `protection_rules` (JSON: required reviews, required status checks, deletion protection); protected branches are distinguishable in queries. |
| PROJ-032 | A Branch SHALL record its current head commit SHA. | P1 | Branch gains `head_sha` (VARCHAR); after reconciliation `head_sha` matches the provider's latest commit for that branch. |
| PROJ-033 | A Branch SHALL record activity and sync timestamps for staleness detection. | P1 | Branch gains `last_activity_at` and `last_synced_at`; a query can list branches whose `last_activity_at` is older than a configurable threshold. |

### Ownership references (gap closure)

| ID | Statement | Priority | Acceptance Criteria |
|----|-----------|----------|---------------------|
| PROJ-040 | Product, ProductComponent, and Repository SHALL each carry a resolvable owner reference. | P1 | Each entity gains an `owner_id` FK to User (and/or a Team entity); the owner of any product/component/repository is queryable; an owned-by query returns all entities owned by a given user/team. |
| PROJ-041 | Branch ownership SHALL be a resolvable reference rather than free text. | P1 | `Branch.owner` (free-text VARCHAR at `orm.py:444`) is replaced/augmented by an `owner_id` FK to User; existing free-text values are migrated; branch owner is resolvable to a real user. |
| PROJ-042 | Ownership SHALL support RBAC and notification routing. | P2 | A responsible party can be resolved for any repository/component to authorize actions and route notifications; absence of an owner is reportable. |

### Monorepo path scoping and hierarchy (gap closure)

| ID | Statement | Priority | Acceptance Criteria |
|----|-----------|----------|---------------------|
| PROJ-050 | A ProductComponent SHALL optionally map to a sub-path within a repository. | P2 | ProductComponent gains an optional `source_path` column; multiple components may reference the same `repo_id` with distinct `source_path` values; CI can scope a build to the component's subtree. |
| PROJ-051 | A ProductComponent SHALL support a self-referential parent for nested components. | P2 | ProductComponent gains an optional `parent_id` FK to ProductComponent (mirroring `ReleaseTrainBranch.parent_id` at `orm.py:320`); a component may declare a sub-component-of relationship; cycles are prevented. |
| PROJ-052 | CI SHALL support path-based filtering so a change to one component does not trigger unrelated component pipelines. | P2 | Given a changed path in a monorepo event, only components whose `source_path` is a prefix of the changed path are scheduled. |

### Type, lifecycle, status, and audit (gap closure)

| ID | Statement | Priority | Acceptance Criteria |
|----|-----------|----------|---------------------|
| PROJ-060 | Product and ProductComponent SHALL carry a type classification. | P2 | Each gains a `type` enum (for example product/service/feature-set for Product; service/library/website for Component); the type is required on create and queryable. |
| PROJ-061 | Product and ProductComponent SHALL carry a lifecycle classification. | P2 | Each gains a `lifecycle` enum (experimental/production/deprecated); maturity is queryable and reportable. |
| PROJ-062 | Projects entities SHALL support soft-delete instead of hard cascade as the only removal path. | P2 | Product and ProductComponent gain a `status`/soft-delete flag (for example active/archived); archiving hides an entity from active queries without physically deleting it and its dependents. |
| PROJ-063 | All five Projects entities SHALL carry audit timestamps. | P2 | Product, ProductComponent, ProductToRepository, Repository, and Branch each gain `created_at` and `updated_at` (consistent with `OauthUser` at `orm.py:724-725`); both are populated on insert and `updated_at` advances on every update. |
| PROJ-064 | Cataloged entities SHALL record provenance to their source of truth. | P3 | Repository (and optionally Component) gains `source_location` and a `managed_by`/ingestion-source field; provenance enables drift reconciliation and registration auditing. |

## 5. Non-Functional Requirements

- **Security (P0).** No SCM credential or webhook secret is ever persisted in plaintext or in a
  config blob; all secrets are referenced from an external secret store and access follows
  least privilege (PROJ-012, PROJ-022). Provider identity and auth-type fields must allow
  auditing credential blast radius per repository.
- **Reliability.** Branch reconciliation from SCM events must be idempotent and tolerant of
  duplicate/out-of-order deliveries (PROJ-021); webhook delivery failures must be observable via
  `last_delivery_at` and structured logs, never silently dropped.
- **Debuggability.** Per the project standards, errors in this area must never pass silently:
  validation failures (schema, uniqueness, signature) raise descriptive, multi-line error
  messages with contextual data and are assigned to a variable before raising. Reconciliation
  and webhook handling must log enough state (provider id, repo slug, branch, SHA) to diagnose
  drift without re-deriving it.
- **Scalability/Maintainability.** Provider identity is decomposed into indexed structured
  columns so repositories scale to lookups by `(provider, org, slug)` rather than URL string
  matching. Behavior (clone, sync, webhook re-registration) must be controlled by caller
  parameters / an Aspects-style object, not behavior-modifying decorators.
- **Auditability.** Audit timestamps on all five entities (PROJ-063) plus provenance (PROJ-064)
  make every registration and change traceable and reconcilable against the SCM source of truth.
- **Data integrity.** Existing uniqueness constraints (PROJ-001, PROJ-003, PROJ-004, PROJ-005,
  PROJ-006) must be preserved; new constraints (single default branch per repo, no path-scoping
  collisions, no component cycles) must be enforced at the database level where feasible.

## 6. Best Practices Adopted

- Model products/components with explicit type, lifecycle, owner, and optional `subcomponentOf`
  parent so maturity and component hierarchies are first-class — Backstage software catalog
  descriptor format (https://backstage.io/docs/features/software-catalog/descriptor-format/).
- Support monorepo and multi-repo products via sub-path component mapping and path-based CI
  filtering so unrelated component pipelines are not triggered — Buildkite monorepo CI best
  practices (https://buildkite.com/resources/blog/monorepo-ci-best-practices/).
- Never store SCM secrets in plaintext config; reference an external secret store and decompose
  provider identity and credential reference into structured, least-privilege fields — OWASP
  CI/CD Security Cheat Sheet
  (https://cheatsheetseries.owasp.org/cheatsheets/CI_CD_Security_Cheat_Sheet.html).
- Choose the right SCM auth mechanism per integration (GitHub App for org-wide, deploy keys for
  single-repo read-only, PAT as fallback) and persist which mechanism and scope is in use —
  GitHub deploy-key / App guidance
  (https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys).
- Track branch lifecycle and protection state: default designation, protection rules, head SHA,
  and last-activity timestamps for stale-branch detection — GitHub protected branches docs
  (https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).
- Anchor ownership to teams/users via structured references rather than free text and surface
  owned-by relations for RBAC and notifications — Roadie catalog ownership
  (https://roadie.io/docs/catalog/ownership/).
- Record source location, managed-by/ingestion source, and created/updated audit timestamps so
  the catalog is traceable and auditable — Backstage software catalog descriptor format
  (https://backstage.io/docs/features/software-catalog/descriptor-format/).

## 7. Data Model Traceability

| Entity (`orm.py`) | Requirements |
|-------------------|--------------|
| **Product** (`186`) | PROJ-001, PROJ-002, PROJ-040, PROJ-060, PROJ-061, PROJ-062, PROJ-063 |
| **ProductComponent** (`217`) | PROJ-003, PROJ-040, PROJ-050, PROJ-051, PROJ-052, PROJ-060, PROJ-061, PROJ-062, PROJ-063 |
| **ProductToRepository** (`241`) | PROJ-004, PROJ-063 |
| **Repository** (`413`) | PROJ-005, PROJ-010, PROJ-011, PROJ-012, PROJ-013, PROJ-020, PROJ-022, PROJ-040, PROJ-063, PROJ-064 |
| **Branch** (`433`) | PROJ-006, PROJ-021, PROJ-030, PROJ-031, PROJ-032, PROJ-033, PROJ-041, PROJ-063 |
| **New: RepositoryWebhook** | PROJ-020, PROJ-022 |
| **Cross-entity / User-team link** | PROJ-040, PROJ-041, PROJ-042, PROJ-052 |

## 8. Open Questions

- **Team entity vs. User-only ownership.** PROJ-040/041 reference an owner FK to User (`orm.py`
  has a User model) and/or a new Team entity. Does the Projects area introduce a Team entity, or
  reuse an existing identity model from another area? This is a cross-area dependency on the
  Identity/RBAC area.
- **External secret store of record.** PROJ-012/022 require a `credential_ref`/`secret_ref` to an
  external store. Which store is canonical (Vault, cloud secret manager, platform secret), and is
  the reference a URI, an opaque handle, or both?
- **Webhook modeling: entity vs. columns.** PROJ-020 allows a `RepositoryWebhook` entity or
  columns on Repository. Multiple webhooks per repository argue for a separate entity — is that
  required, and does it depend on the Build/CI area's trigger design?
- **Path-filtering ownership.** PROJ-052 path-based filtering interacts with the Build/CI
  scheduling area; where does the prefix-matching logic live, and how does it interact with
  `ReleaseTrain`/`Release` branch assignments?
- **Migration of `Branch.owner` free text.** PROJ-041 replaces a free-text VARCHAR with an FK;
  what is the mapping strategy for legacy values that do not resolve to a known user?
- **`repoconf` schema authority.** PROJ-013 constrains `repoconf` to non-secret config — who owns
  the canonical schema, and is it versioned alongside the ORM?
- **Provider coverage.** PROJ-010 enumerates github/gitlab/bitbucket/other; are additional
  providers (Azure DevOps, self-hosted Gitea) in scope for the initial implementation?
