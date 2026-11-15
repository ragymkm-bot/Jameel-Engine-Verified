# Ragy AI Agents: Phased Implementation Plan

## Implementation Principles

- Deliver one testable boundary at a time.
- Keep Phase 1 offline, local, and deterministic.
- Use Python Standard Library and SQLite only; no third-party package is assumed.
- Treat each phase exit criterion as mandatory before the next phase starts.
- Preserve `AGENTS.md` and `README.md`; this plan does not authorize changes outside the project.

## Phase 0: Architecture Baseline

**Purpose:** Freeze the contracts and safety invariants before implementation.

**Deliverables:** the architecture, security model, decisions, and test plan in `docs`.

**Exit criteria:** the team agrees that Phase 1 has one coordinator, Mock Agents, no network, no API, no package installation, and no executable side effects.

## Phase 1: Deterministic Coordinator Skeleton

**Purpose:** Establish one authoritative workflow owner.

**Scope:** create the task state machine, task/result schemas, role assignment checks, approval state, and bounded retry behavior using only the Standard Library and SQLite.

**Not in scope:** model calls, plugins, HTTP clients, shell commands, worker processes, scheduled jobs, source changes by agents, or package installation.

**Exit criteria:** only the coordinator can create or transition task state; invalid transitions fail closed; state survives a controlled restart; each legal transition has an audit event.

## Phase 2: Policy Enforcement Point

**Purpose:** Make permissions executable instead of relying on documentation or prompts.

**Scope:** implement role-to-capability allowlists, task-scoped validation, project-root path validation, payload-size limits, and explicit denial records. The permitted Phase 1 set remains deliberately small.

**Exit criteria:** tests show that unknown roles, unknown capabilities, path escapes, missing approvals, malformed results, and forbidden operations are denied before persistence or side effects.

## Phase 3: Audit Store and Verification

**Purpose:** Produce locally tamper-evident workflow history.

**Scope:** implement sequenced canonical events, predecessor hashes, verification, audit rotation policy, and recovery behavior. Keep task state and audit history logically distinct.

**Exit criteria:** a clean chain verifies; modification, insertion, reordering, and removal after an anchor are detected; the implementation documents that local privileged replacement remains possible without an independent anchor.

## Phase 4: Mock Agent Contracts

**Purpose:** validate multi-agent handoffs without model or network dependency.

**Scope:** add deterministic Research, Developer, Quality & Security, and Automation Mock Agents. Each returns schema-valid simulated results or controlled failures.

**Exit criteria:** the coordinator can complete a planned workflow through review using only mocks; a role cannot approve its own implementation; the Automation Mock is dry-run only.

## Phase 5: Acceptance, Failure, and Security Tests

**Purpose:** demonstrate the system's safety properties before adding power.

**Scope:** run the tests defined in `TEST_PLAN.md`, including restart, malformed state, audit tampering, network-deny, resource limit, path, and authorization tests.

**Exit criteria:** all mandatory tests pass, failures are diagnosable from local records, and no test requires an API, network connection, package, or external filesystem write.

## Phase 6: Windows Process Isolation Assessment

**Purpose:** decide whether mocks may be replaced by executable workers.

**Scope:** design and review separate Windows identities, NTFS ACLs, firewall outbound-deny rules, worker workspace boundaries, local IPC, and recovery/rollback procedures.

**Human gate:** explicit approval is required before creating identities, changing ACLs, firewall rules, or launching workers.

**Exit criteria:** hostile-worker tests show that a worker cannot modify coordinator state, audit history, sibling workspaces, or reach the network. If this cannot be shown, retain mock-only operation.

## Phase 7: Local Model Pilot

**Purpose:** evaluate a local model only after isolation and policy controls work.

**Scope:** one approved local model runtime, a fixed adapter contract, bounded input/output, and offline evaluation tasks.

**Human gate:** approve any program/model download and storage location beforehand.

**Exit criteria:** the pilot remains local, meets quality and resource thresholds, and cannot acquire extra authority through tool output or model text.

## Phase 8: Optional Provider Pilot

**Purpose:** evaluate one remote provider adapter without provider lock-in.

**Scope:** a single approved provider, a small non-sensitive test corpus, explicit spend ceiling, data policy, and no automatic paid fallback.

**Human gate:** written approval for the provider, task type, data class, budget, expiry, and stop condition. Secrets are handled outside agent context and are never written to project files or logs.

**Exit criteria:** provider behavior matches the adapter contract; cost and privacy evidence is recorded; disabling the adapter restores local-only behavior.

## Resource Management Plan

Phase 1 deliberately avoids resident models and parallel worker pools. Keep one active workflow and sequential mock execution on machines with limited memory. Bound individual handoff payloads, reference rather than duplicate large artifacts, cap retries, and monitor project disk consumption.

Before enabling a local model, record the available RAM, disk, GPU/CPU capability, model size, expected context size, and measured latency. Do not choose a model based only on advertised capability.

## Change and Rollback Discipline

Every later implementation increment must be small, tested, reviewed, and linked to an audit/decision record. A failed phase is rolled back by disabling the new capability and preserving evidence; destructive cleanup is not an automated response. No phase authorizes activity outside the project unless the human specifically approves that future activity.

## Phase 1 Core Completion Record

The initial core implements the Coordinator, Task Manager, explicit state machine, Approval Gate, deterministic Mock Agents, SQLite state store, and structured hash-chained audit log using only the Python Standard Library. It remains offline and local. Run `python -m unittest discover -s tests -v` from the project root to verify the implementation; no package installation or network access is required.
