# Tollgate — a self-hostable, MCP-native control plane for AI agents

**Status:** Week 1, pre-alpha · **Live:** not deployed yet · **Uptime (30d):** n/a · **Cost/month:** $0 · **Spec pins:** MCP 2026-07-28

Tollgate sits between agents and the tools and models they use. It identifies every caller, enforces policy with human approval gates and a kill switch, routes model calls with fallbacks, attributes cost per user, agent, tool and task, and writes a tamper-evident audit log.

## The problem and the decision

_To be written with ADR-001 (Day 1): why a control plane, and why not adopt an existing gateway._

## Architecture

_One diagram goes here once the gateway skeleton exists (end of Week 1)._

## Numbers

_Populated from Week 9: policy scenarios, injection scenarios, gateway overhead p50/p95, cost per task, uptime._

| Metric | Value | Measured on |
|---|---|---|
| | | |

## Run it in 5 minutes

Requires [uv](https://docs.astral.sh/uv/) and Python 3.13.

```bash
uv sync
```

```bash
uv run pytest
```

_Full local stack instructions arrive with the gateway skeleton._

## Failure log

_Annotated traces, a failure taxonomy, and what each failure changed. Starts in Week 5._

## Threat model (OWASP ASI01–ASI10)

_Mapped in Week 10._

## ADRs

| # | Decision | Status |
|---|---|---|
| 001 | Why a control plane, why not an existing gateway | Planned |

## Licences and why

Tollgate is licensed under [Apache-2.0](LICENSE). It includes an explicit patent grant, matches the licences of comparable gateways such as IBM ContextForge and agentgateway, and is accepted by most enterprise legal reviews without negotiation.

## Upstream

_Contributions back to the MCP, OpenTelemetry, Langfuse and OWASP projects are tracked here as they land._
