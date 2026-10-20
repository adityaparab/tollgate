---
status: accepted
date: 2026-10-20
decision-makers: Aditya Parab
---

# ADR-001: Build Tollgate as a small control plane instead of adopting an existing MCP gateway

## Context and problem statement

AI agents call tools over MCP and call models over provider APIs. Teams running agents in production need one place that answers five questions for every tool call:

1. Who is calling?
2. Is this call allowed, or does a human need to approve it first?
3. Which model handled the work, and what did the call cost, by user, agent, tool and task?
4. Can we prove afterwards what happened, in a record nobody can quietly edit?
5. Can we stop a runaway agent immediately?

Several open-source MCP gateways exist. Should Tollgate adopt one of them, contribute to one, or build its own control plane?

Tollgate is also a portfolio project. The decision has to produce a system one engineer can build in 12 weeks, explain end to end, and run at $0 on free tiers. It must also show judgement, not just volume.

## Decision drivers

- **Durable human approval of risky tool calls.** The call pauses, a human decides, and it resumes without calling the model again.
- **A tamper-evident audit record of every tool call,** with a published schema others can adopt.
- **Cost attribution for tool calls and model calls,** by user, agent, tool and task, reconciled from OpenTelemetry spans.
- **Strict, provable conformance** with MCP 2026-07-28, checked by the official conformance suite in CI.
- **Secure defaults.** Audit, Origin checks and authentication are on unless deliberately turned off.
- **Runs on one free-tier arm64 VM.** The target is an Oracle Cloud Ampere A1 instance with a Cloudflare edge.
- **Reuse proven parts** rather than rebuild them: LiteLLM for model routing, Keycloak for identity, DBOS for durable workflows, Langfuse for traces.
- **Small enough to explain end to end** in a three-minute demo and a one-hour interview.

## Considered options

1. Adopt IBM ContextForge.
2. Adopt agentgateway.
3. Extend Docker MCP Gateway.
4. Contribute the missing features to an existing gateway.
5. Build Tollgate as a small control plane that composes existing components.

## Decision outcome

**Chosen option: 5, build Tollgate.** It is the only option that delivers the first three drivers together: durable approvals, tamper-evident tool-call audit, and tool-level cost attribution. It does so at a size one engineer can own.

Tollgate is not positioned as a replacement for these gateways. It is a reference control plane that shows how those three capabilities fit together. Where an existing component already does a job well, Tollgate uses it instead of competing with it.

### What changed during evaluation

The original plan argued that existing gateways predated MCP 2026-07-28. That argument no longer holds:

- **ContextForge v1.1.0,** released 19 October 2026, negotiates 2026-07-28 by default.
- **agentgateway v1.6.0,** released 2 October 2026, announces full 2026-07-28 support.

This ADR therefore does not claim protocol novelty. Building on 2026-07-28 is table stakes, not a differentiator.

### Consequences

- **Good:** Tollgate can make audit, approval and cost the core of its design, rather than add-ons configured after the fact.
- **Good:** strict conformance becomes a published, CI-checked property instead of a claim.
- **Good:** reused components keep the hand-written surface small. Tollgate writes the gateway, policy engine, approval service and cost processor, and nothing else.
- **Bad:** Tollgate owns spec conformance and must track future MCP revisions itself.
- **Bad:** it will have far fewer features than ContextForge or agentgateway, such as A2A routing, catalogs and an admin UI. The README must say so plainly.
- **Bad:** a solo project has no production users. Its claims rest on tests, published numbers and 30 days of live uptime, not adoption.

### Confirmation

This decision stays valid only while the gap is real. Check it twice, at the end of Week 5 and at the end of Week 10:

- Re-read the latest releases of ContextForge and agentgateway.
- If either ships durable human approval of tool calls **and** a tamper-evident tool-call audit, write ADR-001a. It should decide whether Tollgate continues as a reference implementation, becomes a plugin for that gateway, or turns its audit schema into an upstream contribution.

## Pros and cons of the options

### 1. Adopt IBM ContextForge

Evaluated hands-on with v1.1.0 on 20 October 2026; see `docs/research/contextforge-notes.md`.

- **Good:** very broad. It covers federation, virtual servers, an admin UI, RBAC, OpenTelemetry tracing, Prometheus metrics and an LLM provider layer.
- **Good:** supports both protocol eras. It speaks 2026-07-28 to clients and falls back to `initialize` for legacy upstreams.
- **Good:** Apache-2.0, and ships a native arm64 image.
- **Bad:** tool calls are not written to the audit trail. With audit enabled, only admin actions were recorded.
- **Bad:** audit records have no hash chain, MCP method or OWASP ASI category, and there's no published schema.
- **Bad:** no token or cost attributes on tool-call spans.
- **Bad:** four conformance gaps:
  - it accepts a version header that disagrees with the body;
  - it reports unknown tools as tool errors instead of `-32602`;
  - it drops the request id on version errors;
  - it accepts a hostile `Origin` by default.
- **Bad:** audit, security logging, tracing and Origin checks are all off by default.
- **Bad:** large: 490 API routes, a 590 MB image, and about 680 MB of RAM with 2 workers. The README still calls arm64 unsupported in production.

### 2. Adopt agentgateway

Evaluated from its README and release notes up to v1.6.0, not hands-on.

- **Good:** a fast Rust proxy covering MCP and A2A. It has JWT, API-key and OAuth auth, CEL policies that can match MCP methods such as `tools/call`, rate limiting and OpenTelemetry.
- **Good:** announces full MCP 2026-07-28 support, including MRTR capabilities for modern clients.
- **Good:** has LLM cost tracking for common public models, plus token or dollar budgets per API key. It runs standalone or on Kubernetes.
- **Good:** Apache-2.0, with an active community.
- **Bad:** its release notes mention no human-approval workflow for tool calls and no durable pause and resume.
- **Bad:** no tamper-evident audit log or published audit schema is mentioned. It offers access logs.
- **Bad:** cost and budgets are described per model call and per API key, not per tool call or task.
- **Neutral:** written in Rust. Contributing approval or audit features means working in a different language and against the maintainers' roadmap.

### 3. Extend Docker MCP Gateway

Evaluated from its repository and Docker's documentation.

- **Good:** MIT licence. Simple to run, with each MCP server isolated in its own container.
- **Bad:** focused on running and cataloguing MCP servers locally, not on policy, approval, audit or cost.
- **Bad:** none of its last eight releases mentions MCP 2026-07-28. The newest is v0.44.1, from 23 September 2026.
- **Bad:** its enterprise gateway is invite-only.

### 4. Contribute the missing features to an existing gateway

- **Good:** real-world impact, and it shows the ability to work in someone else's codebase.
- **Bad:** each missing capability crosses that project's design: durable approvals need a workflow engine, and a tamper-evident audit needs a storage contract. The design would belong to the maintainers, not to Tollgate.
- **Bad:** acceptance and timing are outside the project's control, so it can't anchor a 12-week plan.
- **Taken in part:** Tollgate will still contribute upstream where it fits. That means the audit-log schema to the OWASP Agentic Security Initiative, cost attributes to the OpenTelemetry GenAI semantic conventions, and conformance findings to the gateways above.

### 5. Build Tollgate as a small control plane

- **Good:** meets every decision driver, by design.
- **Good:** composes proven components for model routing, identity, durable workflows and traces, so the new code is the control-plane logic itself.
- **Good:** every claim can be measured and published, including conformance, gateway overhead, uptime and cost.
- **Bad:** the most work, and the least feature coverage of the five options.
- **Bad:** carries the maintenance and spec-tracking burden alone.

## More information

**Research behind this decision:**
- `docs/research/contextforge-notes.md`: hands-on evaluation of ContextForge v1.1.0.
- `docs/spec-cheatsheet.md`: the MCP 2026-07-28 rules Tollgate must meet.

**Sources checked on 20 October 2026:**

| Project | Stars | Licence | Latest release |
|---|---|---|---|
| ContextForge | 4,669 | Apache-2.0 | v1.1.0, 19 October 2026 |
| agentgateway | 5,430 | Apache-2.0 | v1.6.0, 2 October 2026 |
| Docker MCP Gateway | 1,609 | MIT | v0.44.1, 23 September 2026 |

**Follow-up:** before Week 5, spend one hour running agentgateway standalone. Confirm the three gaps listed against it, and update this ADR if any claim is wrong.

**Related decisions:** ADR-002 covers tool namespacing, and ADR-003 covers protocol eras.
