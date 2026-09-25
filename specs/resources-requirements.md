# Resources / Execution — Requirements

## 1. Overview

The Resources / Execution area is the part of Pychestrate that turns submitted work
into scheduled, dispatched, and tracked execution across shared runner capacity. It
covers the queueing, scheduling, leasing, and lifecycle of units of work, the tenant
boundaries that allocate and isolate capacity, the identity records that authorize who
may submit and operate that work, and the observability needed to keep the execution
plane healthy.

The canonical data model for this area lives in
`source/packages/ccai/pychestrate/core/storage/orm.py` and is composed of the
following entities:

- **WorkQueue** (`orm.py:536-548`) — a named queue of work bound (today only loosely)
  to a job type and an enabled/disabled state.
- **WorkPacket** (`orm.py:551-578`) — an individual unit of work belonging to a queue
  and submitted by a user, carrying lifecycle status and progress.
- **FeatureGroup** (`orm.py:581-595`) — a descriptive grouping that today owns test
  entities but is intended to become a capacity-isolation / tenant boundary.
- **FeatureGroupMembership** (`orm.py:688-702`) — the temporal join between a
  FeatureGroup and a User.
- **User** (`orm.py:514-533`) and the enums **AccountStatus** (`orm.py:79-90`) and
  **AuthenticationType** (`orm.py:93-98`) — the identity record and the lifecycle /
  auth dimensions that are defined but currently unused on `User`.

The current implementation is a minimal, mostly-flat execution layer. It can store work
and report a coarse status, but it cannot cap dispatch, isolate tenants, prioritize,
lease work reliably, or model identity lifecycle. The requirements below cover both the
behavior that exists today and the gaps identified during research, so that the
execution plane becomes reliable, debuggable, observable, and multi-tenant-safe — in
line with the repository's stated priorities (debuggability over performance, errors
never passing silently, explicit over implicit).

## 2. Personas

1. **CI Platform / Release Engineer** — operates shared runner capacity and is
   responsible for keeping thousands of build/test work packets flowing across shared
   runner pools without one team starving others or exhausting the pool.
2. **Worker / Runner Agent** — the executing process that claims a work packet, runs
   it, reports progress and result, and must survive crashes without losing or
   double-running work.
3. **Tenant Administrator / FeatureGroup Owner** — governs a team's slice of execution
   capacity and access: allocates the group's quota/concurrency, manages who may submit
   work under it, and offboards departed users.

## 3. User Workflows

### Workflow A — Run shared capacity without starvation (CI Platform / Release Engineer)

1. Define WorkQueues bound to runner pools/sites, each with a concurrency limit.
2. Submit work packets carrying a priority and a fairness/tenant key.
3. The scheduler dispatches eligible packets to idle runners, respecting per-queue
   concurrency and per-tenant quota.
4. The autoscaler grows/shrinks the pool against queue depth.
5. Monitor queue depth, oldest-message age, and throughput to spot backlog.

**Current pain points:** WorkQueue has no concurrency limit or runner-pool binding, so
dispatch cannot be capped and pool exhaustion is silent; there is no priority on
WorkQueue or WorkPacket, so no preemption or fair ordering; there is no
FeatureGroup→WorkQueue link, so no per-tenant isolation; no oldest-age/wait metric is
derivable beyond raw `added`/`start` timestamps.

### Workflow B — Claim, run, and survive crashes (Worker / Runner Agent)

1. Lease the next eligible packet (under a visibility timeout) and record which runner
   claimed it.
2. Heartbeat while running and update progress.
3. On success or failure, record result, exit code, and error detail.
4. On crash, the lease expires and the packet is re-queued.
5. After max attempts the packet moves to a dead-letter state for triage.

**Current pain points:** no runner/worker assignment column (cannot tell which agent
owns a packet); no lease/visibility timeout or heartbeat (a dead worker leaves a packet
stuck in RUNNING forever); no attempt counter, max-attempts, backoff, or dead-letter
state; no structured error/result capture (only an opaque `packet` blob and a `progress`
float).

### Workflow C — Allocate and govern team capacity (Tenant Administrator / FeatureGroup Owner)

1. Create a FeatureGroup as a tenant boundary with a concurrency/quota allocation.
2. Add users as members with a role (admin vs submitter vs viewer).
3. Members submit work that counts against the group's quota.
4. The admin reviews utilization and adjusts the quota.
5. Offboarded users are deprovisioned, ending their membership.

**Current pain points:** FeatureGroup has no quota, concurrency cap, priority/weight, or
queue binding, so it cannot enforce isolation; FeatureGroupMembership has no role column,
so admin vs member cannot be distinguished; User has no status/authtype, so disabling a
departed user is not modeled on the canonical User; two user models (`User` vs
`OauthUser`/`users`) make membership and deprovisioning ambiguous.

## 4. Functional Requirements

Priorities: **P0** = reliability-critical, must ship first; **P1** = needed for
multi-tenant correctness; **P2** = governance/observability hardening; **P3** =
data-hygiene/cleanup.

### WorkPacket execution reliability

| ID | Statement | Priority | Acceptance Criteria |
|----|-----------|----------|---------------------|
| RES-001 | A WorkPacket SHALL record the runner/worker agent that currently owns it. | P0 | WorkPacket exposes a nullable `assigned_worker` identifier; it is set when a packet is leased and cleared when the packet returns to an unleased state; querying a packet returns the owning worker or null. |
| RES-002 | A WorkPacket SHALL be leased with a visibility timeout so only one worker executes it at a time. | P0 | WorkPacket exposes a `lease_expires` timestamp; while `now < lease_expires` and the packet is leased, no other worker can claim it; a claim attempt on an unexpired lease is rejected. |
| RES-003 | A running WorkPacket SHALL maintain a heartbeat that extends/refreshes its lease. | P0 | WorkPacket exposes a `last_heartbeat` timestamp; a heartbeat updates `last_heartbeat` and extends `lease_expires`; a packet whose lease has expired (no heartbeat within the window) is eligible for reclaim. |
| RES-004 | A WorkPacket whose lease expires SHALL be returned to an eligible state for re-dispatch (not left stuck in RUNNING). | P0 | After `lease_expires < now` with no heartbeat, a reclaim operation transitions the packet from RUNNING/LEASED back to a re-queued state and clears `assigned_worker`; the packet becomes dispatchable again. |
| RES-005 | A WorkPacket SHALL track attempt count and a max-attempts limit. | P0 | WorkPacket exposes `attempt_count` (default 0) and `max_attempts` (default >= 5); each dispatch increments `attempt_count`; when `attempt_count >= max_attempts` the packet is not re-dispatched. |
| RES-006 | A failed/expired WorkPacket SHALL be retried with backoff before its next eligibility. | P0 | WorkPacket exposes a `next_eligible_at` timestamp; after a failed attempt the scheduler sets `next_eligible_at = now + backoff(attempt_count)` using exponential backoff; the packet is not dispatched while `now < next_eligible_at`. |
| RES-007 | A WorkPacket that exhausts its attempts SHALL move to a dead-letter state. | P0 | WorkPacketStatus is extended with `DEAD_LETTER`; when `attempt_count >= max_attempts` the packet transitions to `DEAD_LETTER`; dead-lettered packets are excluded from dispatch and retrievable for triage/redrive. |
| RES-008 | A WorkPacket SHALL capture a structured result, error detail, and exit code on completion. | P0 | WorkPacket exposes `exit_code` (nullable int), `result` (structured/JSON, nullable), and `error_detail` (text/JSON, nullable); on SUCCEEDED these reflect the outcome; on FAILED `error_detail` and `exit_code` are populated; values are queryable without parsing the opaque `packet` blob. |
| RES-009 | WorkPacketStatus SHALL include states for leasing and retrying. | P0 | WorkPacketStatus is extended with `LEASED` and `RETRYING` in addition to the existing QUEUED/RUNNING/SUCCEEDED/FAILED/CANCELED/BLOCKED and the new DEAD_LETTER; each state is distinguishable in queries. |
| RES-010 | The existing BLOCKED status SHALL be actionable via a dependency / blocked-by linkage. | P1 | A WorkPacket can declare one or more `blocked_by` dependencies on other WorkPackets; a packet with unmet dependencies is held in BLOCKED and is not dispatched; when all dependencies reach a terminal success state the packet becomes eligible. |
| RES-011 | A WorkPacket SHALL carry a priority drawn from a small fixed set of levels. | P1 | WorkPacket exposes a `priority` enum with 3-5 levels (e.g. LOW/NORMAL/HIGH or 0-4); among eligible packets in a queue, higher-priority packets are dispatched before lower-priority ones. |
| RES-012 | A WorkPacket SHALL carry a fairness/tenant key so capacity can be shared fairly. | P1 | WorkPacket carries a fairness/tenant key (e.g. the owning FeatureGroup id); the scheduler uses the key for weighted fair-share so no single tenant monopolizes a queue at a given priority. |
| RES-013 | WorkPacket lifecycle transition timestamps SHALL be captured for latency/age metrics. | P2 | WorkPacket records `eligible_at`, `leased_at`, and `finished_at` (in addition to existing `added`/`start`/`stop`); oldest-message age and wait time are computable from these without inference. |

### WorkQueue dispatch control and binding

| ID | Statement | Priority | Acceptance Criteria |
|----|-----------|----------|---------------------|
| RES-014 | A WorkQueue SHALL retain its current identity, uniqueness, and enable/disable state. | P0 | WorkQueue continues to expose a unique `name`, a `qtype`, a `description`, and a `state` driven by WorkQueueState (Enabled/Disabled); a Disabled queue dispatches no work. |
| RES-015 | A WorkQueue SHALL enforce a maximum concurrency on simultaneously dispatched packets. | P0 | WorkQueue exposes `max_concurrency`; the scheduler dispatches at most `max_concurrency` packets in a non-terminal running/leased state from that queue; additional eligible packets wait in queue. |
| RES-016 | A WorkQueue SHALL be bindable to a runner pool / site. | P0 | WorkQueue carries a runner-pool/site binding (relationship or identifier); packets from the queue are dispatched only to runners in the bound pool; autoscaling can be keyed off the queue's depth. |
| RES-017 | A WorkQueue SHALL expose a soft capacity / queue-depth alarm threshold. | P2 | WorkQueue exposes a configurable depth threshold; when queued-packet count exceeds it, the condition is observable for alerting; exceeding the threshold does not silently drop work. |
| RES-018 | WorkQueue.qtype SHALL be constrained to the WorkQueueJobType enum. | P3 | `qtype` is typed as WorkQueueJobType (Local/Global) rather than a free-form String; persisting a value outside the enum is rejected. |
| RES-019 | A WorkQueue MAY define a default priority applied to packets lacking one. | P2 | WorkQueue exposes an optional default priority; a packet submitted without an explicit priority inherits the queue default; if neither is set, NORMAL is used. |

### FeatureGroup as tenant / capacity boundary

| ID | Statement | Priority | Acceptance Criteria |
|----|-----------|----------|---------------------|
| RES-020 | A FeatureGroup SHALL carry an enforceable quota and concurrency cap. | P1 | FeatureGroup exposes `quota` and `max_concurrency`; submitting work that would exceed the group's quota is rejected with a clear error; the group never has more than `max_concurrency` packets running concurrently. |
| RES-021 | A FeatureGroup SHALL carry a priority/weight for weighted fair-share. | P1 | FeatureGroup exposes a `priority`/`weight`; the scheduler uses it to apportion shared capacity across groups; higher-weight groups receive a larger fair share under contention. |
| RES-022 | A FeatureGroup SHALL be linked to the execution path (WorkQueue and/or WorkPacket). | P1 | A FeatureGroup is associated with one or more WorkQueues and/or stamps its id as the fairness/tenant key on submitted WorkPackets; work can be scheduled and counted against the group's allocation. |
| RES-023 | FeatureGroup.name SHALL be unique. | P3 | `name` carries a uniqueness constraint (like WorkQueue.name); creating a second FeatureGroup with an existing name is rejected. |
| RES-024 | A FeatureGroup SHALL expose utilization for administrators. | P2 | The running/queued counts and quota utilization of a FeatureGroup are queryable, enabling an admin to review and adjust the quota. |

### FeatureGroupMembership roles

| ID | Statement | Priority | Acceptance Criteria |
|----|-----------|----------|---------------------|
| RES-025 | A FeatureGroupMembership SHALL carry a role. | P1 | Membership exposes a typed `role` (admin / submitter / viewer); the role is settable at join time and updatable thereafter. |
| RES-026 | Membership role SHALL gate capability within the group. | P1 | Only `admin` may adjust the group quota/membership; only `admin`/`submitter` may submit work counted against the group; `viewer` may read only; unauthorized actions are rejected. |
| RES-027 | Membership SHALL retain its temporal join semantics. | P0 | Membership continues to use (fg_id, user_id) as primary key with `join_date` and a nullable `departure_date`; setting `departure_date` ends the membership without deleting history. |

### User identity and lifecycle

| ID | Statement | Priority | Acceptance Criteria |
|----|-----------|----------|---------------------|
| RES-028 | The canonical User SHALL carry an account status. | P1 | User exposes a `status` column typed as AccountStatus (ACTIVE/INACTIVE/SUSPENDED/DELETED); the column is non-null with a sensible default (ACTIVE). |
| RES-029 | The canonical User SHALL carry an authentication type. | P1 | User exposes an `authtype` column typed as AuthenticationType (INTERNAL/OAUTH); the column is non-null. |
| RES-030 | A non-ACTIVE User SHALL be unable to submit or own new work. | P1 | When a User's `status` is INACTIVE/SUSPENDED/DELETED, attempts to submit new WorkPackets under that user are rejected; existing history is preserved. |
| RES-031 | Deprovisioning a User SHALL be deterministic and end memberships. | P1 | A deprovisioning operation transitions the User `status` to a non-active value and stamps `departure_date` on the user's active FeatureGroupMemberships in a single, traceable action. |
| RES-032 | Identity SHALL be consolidated into one authoritative User record. | P1 | The divergent `OauthUser`/`users` table is reconciled with the canonical `User`; provider/roles/auth attributes are represented as typed columns/relationships on the single authoritative record; there is no second free-string identity table for the same users. |
| RES-033 | User roles SHALL be typed rather than a free-string list. | P2 | Roles are represented via a typed relationship/enum rather than a comma-separated VARCHAR; querying a user's roles does not require string parsing. |

### State machines and observability

| ID | Statement | Priority | Acceptance Criteria |
|----|-----------|----------|---------------------|
| RES-034 | WorkPacketStatus and WorkQueueState transitions SHALL be governed by an explicit set of legal transitions. | P2 | A defined transition table specifies legal source→target transitions; an illegal transition (e.g. SUCCEEDED→RUNNING) is rejected with a descriptive error rather than silently applied. |
| RES-035 | The execution plane SHALL expose queue golden-signal metrics. | P2 | Queue depth, oldest-message age (queue latency), throughput, and error rate are derivable from stored timestamps/status for each WorkQueue, sufficient to drive SLO burn-rate alerts. |
| RES-036 | State transitions SHALL be observable/auditable. | P2 | Each significant transition is associated with a timestamp (see RES-013); transition history is retrievable for debugging, satisfying the repository's debuggability mandate. |

## 5. Non-Functional Requirements

- **Reliability (P0):** No work is silently lost or double-run. Every leased packet has
  a visibility timeout and heartbeat; an expired lease is always reclaimed; exhausted
  work always lands in a retained dead-letter state (RES-002..RES-007). Dead-letter
  retention SHOULD exceed source-queue retention to support triage and redrive.
- **Debuggability (P0):** Failures never pass silently. Structured `error_detail`,
  `exit_code`, transition timestamps, and an illegal-transition rejection path make
  every failure inspectable without decoding the opaque `packet` blob
  (RES-008, RES-013, RES-034, RES-036). Multiline error messages follow the repository
  standard.
- **Scalability (P1):** Per-queue concurrency caps, per-tenant quotas, and runner-pool
  binding let the system scale horizontally and bind autoscaling to queue depth without
  pool exhaustion (RES-015, RES-016, RES-020).
- **Fairness / Isolation (P1):** Priority levels plus a fairness/tenant key and weighted
  fair-share prevent a noisy tenant from monopolizing shared capacity
  (RES-011, RES-012, RES-021, RES-022).
- **Security / Governance (P1):** Account status and auth type are first-class on a
  single authoritative User; deprovisioning is deterministic; membership roles gate
  capability (RES-025..RES-033). `SemanticError` on API misuse must bubble; over-quota
  and unauthorized actions raise clear, non-silent errors.
- **Observability (P2):** Queue golden signals (depth, oldest-age, throughput, error
  rate) are computable for SLO alerting (RES-035).
- **Data integrity (P3):** Enumerated columns are typed (qtype, status, authtype, role,
  priority); natural keys (FeatureGroup.name) are unique (RES-018, RES-023).

## 6. Best Practices Adopted

- Start with a small fixed set of priority levels (3-5) plus a fairness key and surface
  priority-broken-down queue metrics rather than a complex scheme up front — adopted in
  RES-011, RES-012, RES-021. Source: <https://docs.temporal.io/develop/task-queue-priority-fairness>
- Separate per-queue *concurrency* from *limit/total machines*, stop dispatching at the
  cap, and bind autoscaling to queues — adopted in RES-015, RES-016. Source:
  <https://docs.gitlab.com/runner/configuration/autoscale/>
- Enforce per-tenant ResourceQuota/LimitRange so one tenant cannot exceed its share,
  rejecting over-quota work and monitoring utilization — adopted in RES-020, RES-024.
  Source: <https://kubernetes.io/docs/concepts/security/multi-tenancy/>
- Give queued work a lease/visibility timeout, heartbeat, bounded retry count
  (maxReceiveCount >= 5) with exponential backoff, and a dead-letter queue retained
  longer than the source — adopted in RES-002..RES-007. Source:
  <https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html>
- Manage the full identity lifecycle (provisioning, status, deterministic
  deprovisioning), distinguish authentication from provisioning/roles, and consolidate
  identity into one record — adopted in RES-028..RES-033. Source:
  <https://auth0.com/docs/authenticate/protocols/saml/saml-configuration/deprovision-users-in-saml-integrations>
- Instrument queues with golden signals (depth/saturation, oldest-message age,
  throughput, error rate) feeding SLO burn-rate alerts — adopted in RES-013, RES-035.
  Source: <https://sre.google/sre-book/monitoring-distributed-systems/>

## 7. Data Model Traceability

Reference: `source/packages/ccai/pychestrate/core/storage/orm.py`.

| Entity (orm.py lines) | Owned / extended by requirements |
|-----------------------|----------------------------------|
| **WorkPacket** (551-578) | RES-001, RES-002, RES-003, RES-004, RES-005, RES-006, RES-007, RES-008, RES-009, RES-010, RES-011, RES-012, RES-013 |
| **WorkQueue** (536-548) | RES-014, RES-015, RES-016, RES-017, RES-018, RES-019 |
| **FeatureGroup** (581-595) | RES-020, RES-021, RES-022, RES-023, RES-024 |
| **FeatureGroupMembership** (688-702) | RES-025, RES-026, RES-027 |
| **User** (514-533) + **AccountStatus** (79-90) + **AuthenticationType** (93-98); reconciles **OauthUser**/`users` (705-726) | RES-028, RES-029, RES-030, RES-031, RES-032, RES-033 |
| **WorkPacketStatus** (135-143) / **WorkQueueState** (125-132) state machines | RES-007, RES-009, RES-034, RES-035, RES-036 |

Cross-entity relationships introduced by these requirements:

- WorkQueue → runner pool / site binding (RES-016).
- FeatureGroup ↔ WorkQueue and/or FeatureGroup id stamped on WorkPacket as the
  fairness/tenant key (RES-012, RES-022).
- WorkPacket → WorkPacket `blocked_by` dependency edges (RES-010).
- WorkPacket → User constrained by User.status (RES-030).
- User deprovisioning → FeatureGroupMembership.departure_date (RES-031).

## 8. Open Questions

1. **Runner pool / site model ownership.** RES-016 requires a runner-pool/site entity
   that does not yet exist in `orm.py`. Does it belong to the Resources area or to a
   separate Infrastructure/Sites area, and what is its primary key relationship to
   WorkQueue?
2. **OauthUser reconciliation strategy.** RES-032 requires consolidating the `users`
   table into the canonical `user` table. Is this a destructive migration, a merge with
   provider attributes moved onto `User`, or a satellite identity-provider table keyed
   to a single `User`? This intersects the Identity/Auth area.
3. **Quota semantics.** Is FeatureGroup `quota` (RES-020) a count of concurrent packets,
   a rate, or an abstract resource budget (CPU/memory) like Kubernetes ResourceQuota?
   The chosen unit affects enforcement and metrics.
4. **Preemption.** Priority (RES-011) enables ordering, but should the scheduler preempt
   a lower-priority running packet for a higher-priority one, or only affect dispatch
   ordering? Preemption interacts with leases and attempt counts.
5. **Backoff and lease parameters.** What are the default visibility timeout, heartbeat
   interval, backoff curve, and `max_attempts` (RES-002, RES-003, RES-005, RES-006), and
   are they per-queue configurable?
6. **Fairness key granularity.** RES-012 proposes FeatureGroup id as the fairness key;
   should additional dimensions (user, branch, build) participate in fair-share?
7. **State-machine authority.** Where do the legal-transition tables (RES-034) live —
   in the ORM layer, a service layer, or a shared state-machine module — and how are
   they versioned alongside the enums?
8. **Roles taxonomy.** RES-025/RES-033 assume admin/submitter/viewer. Does this align
   with the broader product RBAC model, and is the role per-FeatureGroup only or also
   global on User?
