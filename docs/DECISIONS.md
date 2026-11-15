# Ragy AI Agents: Engineering Decisions

## Decision Record Status

The following decisions are accepted for the initial architecture. A later change requires a new dated decision record with rationale, risk analysis, test impact, and required human approval.

## D-001: Start with One Coordinator and Mock Agents

**Decision:** Phase 1 has one authoritative Main Coordinator and four deterministic Mock Agents.

**Reason:** This proves task contracts, state transitions, review independence, failure handling, and audit behavior without the variability, resource cost, or authority expansion of LLMs and autonomous tools.

**Consequences:** The first implementation does not measure model quality or secure hostile in-process code. It is a workflow foundation, not a production autonomous-agent system.

**Rejected alternative:** Start with several live model-backed agents. It would make failures difficult to reproduce and would introduce network, cost, privacy, and secret-management concerns before policy enforcement is proven.

## D-002: Enforce Permissions in the Runtime and Later at the OS Boundary

**Decision:** Use a deny-by-default Policy Enforcement Point in the coordinator, task-scoped capabilities, schema validation, and future Windows ACL/firewall isolation.

**Reason:** `AGENTS.md` is necessary governance but is not technical enforcement. Models and prompts cannot be trusted to preserve security boundaries.

**Consequences:** All behavior must pass through purpose-built, validated operations. Phase 1's in-process mocks are intentionally not claimed to be hostile-code containment; executable workers require separate Windows identities and ACLs.

## D-003: Network and APIs Are Denied in Phase 1

**Decision:** No sockets, DNS, HTTP(S), provider API, telemetry, update check, or remote tool may be available in Phase 1.

**Reason:** This satisfies the local-first safety requirement, avoids cloud cost and data transmission, and allows deterministic tests.

**Consequences:** Research and model behavior are simulated. Any future remote integration needs a specific approval, a narrow technical network rule, a data-policy review, and an explicit cost ceiling.

## D-004: Use Python Standard Library and SQLite First

**Decision:** The initial implementation may use only Python Standard Library facilities and SQLite.

**Reason:** They minimize dependencies, installation steps, supply-chain exposure, and resource use on Windows 11.

**Consequences:** The first coordinator should favor simple, explicit code over framework convenience. A third-party framework or database requires a separate decision, approval, and validation plan.

## D-005: Audit Logs Are Tamper-Evident, Not Tamper-Proof

**Decision:** Use canonical sequenced hash chains, with future keyed integrity tags and independent checkpoints when approved.

**Reason:** Hash chaining detects many local changes after a known-good anchor without external infrastructure.

**Consequences:** The project must not describe a local hash chain as immutable. An attacker who controls the log, anchor, verifier, or integrity key can defeat purely local evidence. Independent anchoring is required for stronger claims.

## D-006: Coordinator Is the Sole State and Audit Writer

**Decision:** Agents return structured results; only the coordinator persists accepted task state and audit events.

**Reason:** A single writer simplifies authorization, ordering, integrity, recovery, and evidence ownership.

**Consequences:** Agent throughput is intentionally limited in Phase 1. Scale is deferred until concurrency semantics and isolated worker communication are tested.

## D-007: Model Providers Are Optional Adapters

**Decision:** Gemini, Grok, OpenRouter, and local runtimes are future adapters behind a normalized internal contract. No provider is required for the core architecture.

**Reason:** This avoids vendor lock-in and prevents automatic conversion of local work into paid remote work.

**Consequences:** Provider selection belongs in approved policy, not agent prompts. Remote fallback is disabled by default; free tiers are treated as conditional and bounded, not as guaranteed capacity.

## D-008: Memory Is Evidence-First and Bounded

**Decision:** Use SQLite for workflow metadata, project-scoped append-only audit records, and references/hashes for larger artifacts. Start with lexical retrieval only if retrieval becomes necessary.

**Reason:** It preserves provenance, reduces memory pressure, and avoids prematurely introducing a vector database or embeddings pipeline.

**Consequences:** The source of truth is the reviewed artifact and audit record, not an agent summary or vector index. Long contexts are bounded and large payloads are not copied across handoffs.

## D-009: Resource Limits Are Functional Requirements

**Decision:** Phase 1 uses sequential execution, one active workflow, bounded payloads, bounded retries, and an explicit disk budget.

**Reason:** Windows 11 machines may have limited RAM, storage, or GPU capacity; predictable degradation is preferable to hidden resource exhaustion.

**Consequences:** Performance scaling is deferred. Any move to parallel workers or local models requires measurement, a documented resource profile, and security testing.

## D-010: Automation Is Dry-Run First

**Decision:** The Automation Agent initially produces only plans, schedules, and idempotence analyses. It cannot create scheduled tasks, send messages, deploy, delete, or trigger external work.

**Reason:** Automation turns a recommendation into an effect and therefore needs stronger authorization and rollback controls.

**Consequences:** Real automation is a later, separately approved capability with a limited scope, observability, stop condition, and human override.

## D-011: The Initial Core Has No Generic Tool Interface

**Decision:** The implemented Phase 1 core exposes task, approval, result, and review operations only. It does not expose generic command, network, process, package, file-write, or provider-invocation operations to agents.

**Reason:** A narrow API makes the deny-by-default policy enforceable and testable. In-process Mock Agents receive only task data and return structured results.

**Consequences:** The current implementation is intentionally limited to local workflow simulation. A future executable tool needs its own capability, schema, isolation plan, acceptance tests, and explicit human approval.

## Summary of Current Posture

The accepted foundation is an offline, local, single-coordinator workflow with simulated agents and technically enforced denial of sensitive capabilities. It prioritizes evidence, reproducibility, and Windows-compatible resource limits over early autonomy. No runtime, dependency, model, provider, or automation service is authorized by these decisions alone.
