# Ragy AI Agents: Final Architecture

## Status and Scope

This document defines the approved target architecture and the deliberately small Phase 1 implementation boundary. Phase 1 runs locally on Windows 11, uses only the Python Standard Library and SQLite, starts with one coordinator and Mock Agents, and has no network, API, package-installation, shell-execution, or external side-effect capability.

`AGENTS.md` remains the project policy. The design below turns the relevant policy into runtime and operating-system enforcement points; a document alone is not treated as a security control.

## Architectural Goals

- Make planning, execution, and review distinct workflow states.
- Make authority explicit, least-privilege, time-bounded, and machine-enforced.
- Preserve evidence for each decision, transition, test, and review.
- Be useful without a cloud model provider or any third-party Python package.
- Allow future model providers through replaceable adapters, without making them part of Phase 1.
- Operate within modest Windows 11 memory, disk, and CPU budgets.

## Phase 1 Topology

```text
Human approval
      |
      v
Main Coordinator -----> Policy Enforcement Point
      |                         |
      |                         +---- denies network, API, shell, installs,
      |                                out-of-scope paths, and unapproved states
      |
      +----> Research Mock Agent
      +----> Developer Mock Agent
      +----> Quality & Security Mock Agent
      +----> Automation Mock Agent
      |
      +----> Result Validator -----> SQLite Task Store
      |
      +----> Audit Writer ---------> Append-only Audit Log
```

All work is initiated and finalized by the Main Coordinator. Mock Agents return deterministic, structured simulated results. They do not invoke models, tools, subprocesses, network clients, or direct database writes.

## Components

### Human Approval Boundary

The human supplies objectives and confirms gates that alter authority: code execution, dependency installation, network access, external provider use, external effects, deployment, or any paid service. Absence of approval means denial.

### Main Coordinator

The coordinator is the only component permitted to create tasks, change task state, assign a role, persist accepted results, or close a workflow. It owns the state machine and rejects transitions that are not legal for the task's current state.

The coordinator does not execute arbitrary commands, make network requests, or treat an agent response as authorization. It can only dispatch a task after policy evaluation passes.

### Policy Enforcement Point (PEP)

The PEP is a required runtime boundary, not a prompt instruction. Before dispatching work or recording an effect, it evaluates:

- the actor role and task identifier;
- the requested capability;
- the approved project-root path, if a path is involved;
- the workflow state and active human approval;
- resource limits and whether the requested operation is allowed in the current phase.

Phase 1 grants no network, API, package-management, shell, child-process, installation, or external-write capability to any actor. The PEP fails closed on unknown roles, capabilities, state transitions, or malformed inputs.

### Mock Agents

Each Mock Agent implements only its role contract:

- **Research:** returns cited simulated findings and explicit uncertainty.
- **Developer:** returns a proposed implementation summary and simulated local test evidence; it does not write files in Phase 1.
- **Quality & Security:** returns an independent accept, reject, or needs-evidence verdict against stated criteria.
- **Automation:** returns a dry-run schedule or idempotence assessment; it never triggers a scheduled action.

Mock Agents are scaffolding for contract tests. In-process mocks are not an OS security boundary; they prove workflow and policy behavior, not containment of hostile code.

### Result Validator

Every result must match a role-specific schema before it can be persisted. Required fields include task identifier, actor role, status, evidence references, assumptions, risks, and next-step recommendation. Unknown fields, invalid status values, missing evidence, and mismatched task IDs are rejected.

### SQLite Task Store

SQLite is the source of truth for task metadata, legal state transitions, approval records, decision references, and result metadata. Raw large artifacts are not duplicated in the database. The coordinator alone writes the database; agents return results over the coordinator-controlled interface.

### Audit Writer

The audit writer records security-relevant events and workflow transitions in sequence. It is independent from ordinary application logging: ordinary diagnostic logs may be rotated, while audit events are retained according to an explicit retention policy.

## Authority Model

An agent receives a task-scoped capability set, never ambient authority. A capability is valid only for its task, role, approved workflow state, project root, and expiry. The following are distinct capabilities, even if no one receives them in Phase 1:

- `task.create`, `task.assign`, `task.transition`
- `artifact.read`, `artifact.write-project`
- `audit.append`, `audit.verify`
- `test.run-local`
- `network.connect`, `provider.invoke`, `process.spawn`, `package.install`
- `external.effect`, `deployment.execute`

The last five are denied for every Phase 1 task. A future phase may introduce them only with a separate approved capability, technical enforcement, tests, and documented risk review.

## Message and Handoff Contract

The coordinator uses structured task envelopes rather than free-form instructions. A task envelope contains the objective, assigned role, allowed capabilities, approved inputs, resource limits, acceptance criteria, approval reference, and parent task.

A result envelope contains the task ID, role, outcome, evidence, tests performed, assumptions, risks, and requested next state. Agent results are advisory until the coordinator validates the schema and the Quality & Security role completes the required review.

Legal transitions are:

```text
Draft -> Planned -> AwaitingApproval -> Assigned -> Working
Working -> EvidenceSubmitted -> UnderReview -> Accepted | Rejected
Working -> Assigned (bounded retry) | Blocked
Accepted -> Closed
```

No role may skip `AwaitingApproval`, self-accept its own implementation, or close a task without the required review evidence. A retry from `Working` to `Assigned` is allowed only while the task's coordinator-owned attempt counter remains below its configured maximum.

## Audit Log Design

Each event has a monotonically increasing sequence number, UTC timestamp, event type, actor, task ID, normalized event payload, previous event hash, and current event hash. Canonical serialization is required so verification is deterministic. The event hash covers the complete normalized event and the prior hash. A keyed integrity tag is additionally recommended once worker processes are separated; its key must be held outside all agent contexts.

The chain is **tamper-evident**, not tamper-proof. It detects modification, insertion, reordering, or removal within a verified chain. It cannot by itself prevent a local administrator from deleting the entire log, replacing the chain, rewriting the current trusted anchor, or recomputing hashes. If the integrity key is compromised, a keyed tag also loses value. A trustworthy claim beyond local tamper evidence requires periodic anchors stored outside the attacker's writable scope, such as a human-verified offline export or an approved write-once/independent audit system. Those anchors are out of scope for Phase 1 and must not be simulated as stronger protection than they are.

## Windows 11 Enforcement Plan

Phase 1 is deliberately single-process and mock-only. It enforces the allowed operation set at the coordinator boundary and does not claim that hostile in-process Python code can be securely confined.

Before replacing mocks with executable workers, the deployment must add real separation:

- Run the coordinator and each worker under distinct least-privileged Windows identities.
- Apply NTFS ACLs so workers cannot write the SQLite database, audit log, policy files, or sibling workspaces.
- Pass worker results through coordinator-controlled standard input/output or another authenticated local channel; workers do not receive database credentials or write paths.
- Resolve every proposed path and reject paths outside the project root, traversal, reparse-point, or symlink escapes.
- Apply Windows Defender Firewall outbound-deny rules to worker identities or executables; allow no network rule until a separately approved phase.
- Do not grant package-manager, installer, child-process, or shell permissions to worker identities.

Windows ACLs and firewall rules are deployment actions requiring explicit approval. They are specified here but are not being applied by this documentation change.

## Resource and Data Limits

The initial safe operating profile is one coordinator, sequential mock dispatch, one active workflow, SQLite in local mode, and no model runtime. It should be usable on a Windows 11 machine with 8 GB RAM because it has no resident model or external service.

Recommended initial configurable limits are:

- one active workflow and one active mock task;
- at most 256 KiB normalized input or result payload per handoff;
- at most 1 MiB aggregate working context per task;
- explicit disk budget for the project audit store, with an alert before the configured limit;
- bounded retries and timeouts for every state transition.

These are safeguards, not performance claims. Larger documents are referenced by immutable artifact IDs and hashes rather than copied into agent context. Any increase must be benchmarked and recorded in a decision entry.

## Evolution Boundary

Only after Phase 1 acceptance may the project evaluate isolated worker processes, a local model runtime, optional vector retrieval, or provider adapters. Gemini, Grok, and OpenRouter remain conceptual adapters until an approved future phase. No provider is a mandatory dependency, and no automatic fallback may convert a local task into a paid remote request.
