# Ragy AI Agents: Test Plan

## Purpose

This plan verifies that the Phase 1 coordinator is correct by default, fails closed, stays offline, and records evidence. Tests are designed for Python Standard Library and SQLite only. They must not require package installation, API access, internet access, or writes outside the project.

## Test Environment

- Windows 11 local workspace.
- One coordinator instance and deterministic Mock Agents.
- A temporary test workspace under the project root.
- SQLite test database and audit files inside that test workspace.
- No model runtime, provider configuration, network client, shell command, subprocess, scheduler, or external service.

Tests must clean up only their own project-scoped temporary data and preserve failed-test evidence when configured to do so.

## Acceptance Tests

| ID | Scenario | Expected result |
| --- | --- | --- |
| A-01 | Create a valid objective | Coordinator creates one task with a unique ID and `Draft` state |
| A-02 | Submit an approved plan | Task follows only the defined legal transition path |
| A-03 | Dispatch Research Mock | Schema-valid simulated finding is attached to the matching task |
| A-04 | Dispatch Developer Mock | Simulated implementation and test evidence are recorded; no file is changed |
| A-05 | Dispatch Quality & Security Mock | Verdict is independent and must precede acceptance |
| A-06 | Dispatch Automation Mock | Only a dry-run result is returned; no schedule or external effect exists |
| A-07 | Restart coordinator | Valid task state and audit sequence can be restored and verified |
| A-08 | Verify audit log | Untouched chain verifies against its saved anchor |
| A-09 | Reach resource boundary | Inputs and outputs below configured limits succeed predictably |

## Failure and Recovery Tests

| ID | Scenario | Expected result |
| --- | --- | --- |
| F-01 | Unknown role or capability | Denied before dispatch and recorded as a security event |
| F-02 | Illegal state transition | Rejected without changing task state |
| F-03 | Result task ID differs from assigned task | Rejected and never attached to another task |
| F-04 | Result schema is incomplete or has invalid status | Rejected with a diagnostic error |
| F-05 | Mock timeout or controlled exception | Task becomes `Blocked` or retry-limited; no partial acceptance |
| F-06 | SQLite lock or controlled persistence failure | Operation fails safely; state/audit consistency is checked on recovery |
| F-07 | Disk-budget warning or write failure | Stop new persistence safely and surface operator action; do not silently drop audit events |
| F-08 | Coordinator restart during a handoff | Recovery identifies incomplete work and requires safe replay or review |
| F-09 | Oversized payload | Rejected before storage and logged without recording the oversized content |

## Authorization and Security Tests

| ID | Attack or misuse | Expected result |
| --- | --- | --- |
| S-01 | Agent asks for HTTP, HTTPS, DNS, socket, or provider access | Denied; no network operation is attempted |
| S-02 | Agent asks for a shell, subprocess, installer, or package manager | Denied; no child process is created |
| S-03 | Proposed path is outside the project root | Denied before filesystem access |
| S-04 | Proposed path uses traversal, symlink, or reparse-point escape | Denied after final-path resolution |
| S-05 | Mock attempts direct SQLite or audit access | Interface is absent/denied; coordinator remains sole writer |
| S-06 | Developer role requests acceptance | Denied because review authority belongs to Quality & Security |
| S-07 | Automation role requests execution rather than dry-run | Denied in Phase 1 |
| S-08 | Prompt text instructs policy override | Treated as untrusted content; policy remains unchanged |
| S-09 | Replayed result envelope | Detected through task state, result identity, and idempotence checks |
| S-10 | Excessive retries or recursive tasks | Bounded and marked blocked for human review |

## Audit Integrity Tests

| ID | Change to audit history | Expected result |
| --- | --- | --- |
| L-01 | Change one normalized event field | Chain verification fails at that event |
| L-02 | Insert an event in the middle | Sequence/predecessor verification fails |
| L-03 | Remove a middle event | Predecessor verification fails |
| L-04 | Reorder events | Sequence and hash verification fails |
| L-05 | Corrupt the saved anchor | Verification reports anchor mismatch |
| L-06 | Replace the entire local chain and anchor | Documented limitation: local verification alone cannot prove this attack occurred |
| L-07 | Compromise a future integrity key | Documented limitation: keyed tags cannot protect against key compromise |

L-06 and L-07 are mandatory honesty tests: passing them means the system reports the limitation correctly, not that hash chains solve it.

## Resource and Reliability Tests

- Test the configured input, output, retry, task-count, and disk-budget limits at the boundary and one value beyond it.
- Verify that large artifacts are referenced by IDs/hashes rather than copied into every result.
- Run repeated short workflows and confirm that audit growth, SQLite size, and process memory stay within configured local budgets.
- Simulate abrupt coordinator termination only against a project-scoped test workspace, then verify recovery and audit consistency.
- Run tests serially in Phase 1; concurrency is not accepted until it has its own ordering, locking, and resource tests.

## Exit Criteria

Phase 1 is acceptable only when all acceptance tests pass; all authorization/security tests demonstrate denial before effect; audit tampering is detected within its stated limits; recovery behavior is documented; and no test uses a network, API, package, or out-of-project write. Any failed mandatory test blocks later phases.
