# Ragy AI Agents: Security Model and Permissions

## Security Objective

Ragy AI Agents must fail closed: a capability is unavailable unless an explicit, technical control permits it for a specific approved task. Natural-language guidance, model prompts, and agent self-reporting are not authorization mechanisms.

## Assets to Protect

- Project files, SQLite task state, policy configuration, and audit records.
- Human approvals, decisions, test evidence, and workflow history.
- Confidential task content and metadata.
- Host integrity, including the Windows user profile and files outside the project root.
- Budget and privacy posture if future cloud providers are approved.

API keys are intentionally outside the Phase 1 design. No agent may request, receive, inspect, log, or persist them.

## Trust Boundaries

| Boundary | Trusted action | Not trusted |
| --- | --- | --- |
| Human to coordinator | Explicit approval with scope | Ambiguous instructions or implied consent |
| Coordinator to agent | Schema-validated, least-privilege task | Agent output, prompts, and recommendations |
| Agent to storage | None in Phase 1 | Direct database or audit writes |
| Project root to host | Project-scoped reads/writes only when enabled | Parent paths, other drives, temporary broad paths |
| Local system to network | No connection in Phase 1 | DNS, HTTP(S), provider APIs, telemetry, update checks |

## Capability Matrix

| Actor | Permitted in Phase 1 | Explicitly denied |
| --- | --- | --- |
| Human | Create objective; approve a documented gate | Implicit approval through task text |
| Main Coordinator | Create/assign/transition tasks; validate and persist structured results; append audit events | Network, API use, shell, installs, external effects |
| Research Mock | Receive a bounded input and return a simulated result | Filesystem access, database access, network, tools |
| Developer Mock | Return a simulated implementation and test report | Source changes, subprocesses, installs, network |
| Quality & Security Mock | Return an independent review verdict | Editing reviewed work, accepting itself, host access |
| Automation Mock | Return dry-run automation information | Scheduling, sending, deployment, deletion, network |
| Audit Writer | Append validated coordinator events and verify a chain | Altering past events or authorizing work |

## Enforcement Mechanisms

### Application-Level Enforcement

The coordinator contains the sole policy decision and policy enforcement path. It validates role, task ID, state, capability, path scope, size limit, approval reference, and schema before each action. Unknown values are denied. The application exposes no generic command-execution, HTTP-client, package-management, or provider-invocation interface in Phase 1.

The coordinator must use allowlists rather than blocklists. It should expose purpose-built operations such as `create_task` and `record_review`, not a generic `run` operation. Mock Agents receive data objects, not service handles, database handles, callable network clients, or filesystem paths.

### Filesystem Enforcement

Any future project write capability is rooted at the resolved project directory and is denied if it escapes through a relative path, reparse point, or link. The coordinator must verify the final resolved location before a write and record the approved path in the audit log.

When executable workers are introduced, NTFS ACLs must make the policy real at the OS boundary: workers cannot write coordinator state, policy, audit history, or content outside their assigned workspace. A process with broad user permissions is not an acceptable containment strategy.

### Network and API Enforcement

Phase 1 has a network-deny invariant: no DNS, HTTP, HTTPS, sockets, telemetry, provider API, update check, or remote tool connection is part of the runtime. The implementation should have no network client capability to call.

For a future worker-process phase, outbound-deny Windows Defender Firewall rules must be applied to the worker identity or executable before the worker is trusted. A narrow allow rule, if ever approved, must name the destination, port, task type, expiry, data policy, and spending limit. An approval record alone is insufficient if a firewall rule still allows all outbound traffic.

### Process and Installation Enforcement

No child process, shell, package manager, installer, interpreter invocation, or scheduled task is permitted in Phase 1. Future process execution requires a separate executable allowlist, argument schema, working-directory constraint, output-size limit, timeout, and audit record.

## Threat Model

| Threat | Example | Required control |
| --- | --- | --- |
| Prompt injection | Input asks an agent to ignore policy or exfiltrate data | Treat all agent input/output as untrusted; PEP and capability checks are non-bypassable |
| Privilege escalation | Developer requests a shell or broad file path | No generic execution interface; deny unknown capabilities; future ACL isolation |
| Path escape | `..`, symlink, or reparse-point traversal | Resolve final path; project-root allowlist; worker ACLs |
| Data tampering | Rewriting task state or audit history | Coordinator-only writes, schema checks, hash chain, ACLs, external anchors later |
| Replay/confusion | Submit a result for another task | Bind task ID, role, state, and parent reference in every envelope |
| Denial of service | Oversized input, retry loop, database lock | Size limits, bounded retries, timeouts, sequential Phase 1 dispatch |
| Cost escalation | Provider fallback or autonomous tools | No network/API in Phase 1; future zero-default budget and explicit provider allowlist |
| Privacy leak | Sensitive data sent to a provider | Local-only default; data classification and approval before any remote path |

## Audit Integrity and Its Limits

An audit event chain detects edits after a known-good anchor. Verification recomputes each event hash in sequence and confirms the stored predecessor relation. A keyed integrity tag can strengthen the scheme if its key remains inaccessible to workers and attackers.

Hash chains do not provide independent storage, confidentiality, availability, or protection from a sufficiently privileged local attacker. A local administrator may remove all events, replace the log and its anchor, or alter the verification program. Therefore the precise Phase 1 claim is **local tamper evidence after verification against a known-good anchor**, not immutable or legally non-repudiable logging.

Later, and only with approval, the coordinator may periodically export a signed digest to an independent retention location. This changes the threat model because the attacker must then compromise both locations. It is not performed in Phase 1.

## Human Approval Rules

Human approval is required before enabling any of the following:

- package or program installation;
- child-process or shell execution;
- network or API access, including model providers;
- data transmission outside the project;
- writes outside an approved project workspace;
- deletion, deployment, account change, message send, or other external effect;
- an increase to resource, retention, or budget limits.

Approval must name the purpose, scope, expiry, responsible role, and rollback or stop condition. A broad permanent approval is not an acceptable substitute.

## Security Acceptance Criteria

- Every denied capability is rejected before an effect occurs.
- Every permitted state transition is attributable to a task, role, and approval state.
- No mock can access a filesystem, network, subprocess, or database handle.
- Audit verification detects a changed, reordered, inserted, or removed event after the trusted anchor.
- Documentation and runtime claims clearly distinguish application checks from OS-enforced isolation.
