# ContextForge hands-on notes

**Tested:** 20 October 2026 · **Version:** ContextForge v1.1.0 (`ghcr.io/ibm/mcp-context-forge:v1.1.0`, released 19 October 2026) · **Host:** Apple Silicon, Docker 29.9.1, native `linux/arm64` image · **Upstream used:** DeepWiki's public MCP server, `https://mcp.deepwiki.com/mcp`

Evidence for ADR-001. Everything below was observed on a local container unless marked "per docs".

## Summary

ContextForge is a capable, broad gateway, and v1.1.0 already speaks MCP 2026-07-28. So "the incumbent predates the new spec" is **no longer a valid argument** for Tollgate. The gaps that remain:

- **Tool calls never reach the audit trail.**
- **The audit record has no hash chain**, no OWASP ASI tags and no MCP method.
- **Tool-call traces carry no token or cost attributes.**
- **Four spec rules are broken**, one of them by default configuration.

It is also large: 490 API routes, a 590 MB image, and about 680 MB of RAM with only 2 workers.

## What I did

1. Started the container with an admin account, a JWT secret and SQLite storage. I capped it at 2 workers; by default it starts 16 on this machine.
2. Registered DeepWiki as an upstream gateway through `POST /gateways`, using the Streamable HTTP transport.
3. Created a virtual server with DeepWiki's three tools, and called it at `/servers/{id}/mcp` with hand-written 2026-07-28 requests.
4. Sent the same 8 invalid-request cases planned for Tollgate's Day 2, plus five more.
5. Restarted with audit trail, security logging, database logging and OpenTelemetry console export on, then repeated the calls.

## Protocol versions

- **Inbound, from clients:** dual-era. `MCP_INBOUND_PROTOCOL_MODE` defaults to `auto` from v1.1.0. A 2026-07-28 request is served statelessly, and a legacy `initialize` is also answered. `server/discover` advertises `supportedVersions: ["2026-07-28"]`. But the unsupported-version error lists five versions, from 2024-11-05 to 2026-07-28, so the two answers disagree.
- **Outbound, to upstreams:** `MCP_CLIENT_CONNECT_MODE=auto`. It probes `server/discover` first and falls back to `initialize`. The trace showed a `MCP send server/discover` span to DeepWiki before the legacy connection.
- **The real-world upstream is legacy-only.** DeepWiki rejected a 2026-07-28 request with HTTP 400 and code `-32600`, saying it supports only 2024-11-05 to 2025-11-25. It should have used `-32022` with `data.supported`. Because `-32600` is not a recognised modern error, a dual-era client falls back correctly anyway.
- **It bundles the same SDK Tollgate uses,** Python `mcp` 2.3.0.

## Spec conformance as a 2026-07-28 server

| # | Case | Spec expects | ContextForge v1.1.0 | Verdict |
|---|---|---|---|---|
| 1 | `Mcp-Method` header missing | 400, `-32020` | 400, `-32020` | Pass |
| 2 | `Mcp-Name` differs from `params.name` | 400, `-32020` | 400, `-32020` | Pass |
| 2b | `Mcp-Name` missing on `tools/call` | 400, `-32020` | 400, `-32020` | Pass |
| 2c | `Mcp-Method` says `tools/list`, body is `tools/call` | 400, `-32020` | 400, `-32020` | Pass |
| 3 | Header version `2025-11-25`, `_meta` version `2026-07-28` | 400, `-32020` | 200, served as legacy, no `resultType` | **Fail** |
| 4 | Version `1900-01-01` in both places | 400, `-32022`, same request id | 400, `-32022`, but `id: null` | **Partial**: id dropped |
| 5 | Unknown method `foo/bar` | 404, `-32601` | 404, `-32601` | Pass |
| 6 | HTTP GET on the endpoint | 405 | 405 | Pass |
| 7 | `_meta` missing `clientCapabilities` | 400, `-32602` | 400, `-32602`, names the missing key | Pass |
| 8 | Unknown tool | JSON-RPC error `-32602` | 200 with `isError: true`, "Unknown tool: nope" | **Fail** |
| 9 | Stray `Mcp-Session-Id` on a modern request | Ignored, never echoed | Ignored, not echoed | Pass |
| 10 | Legacy `initialize` | Allowed for dual-era servers | Answered | Pass, by design |
| 11 | No `Authorization` header | Authentication required | 401 | Pass |
| 12 | Hostile `Origin: https://evil.example` | 403 | 200 | **Fail by default.** Enforcement needs `MCP_ALLOWED_ORIGINS` set |
| 13 | `tools/list` ordering across 3 calls | Deterministic | Same order every time, though not sorted | Pass |

Case 3 is the important one for a gateway. The header says legacy while the body says modern. An intermediary routing on the header and a server reading the body would then disagree about which rules apply. That is exactly the mismatch the header rules exist to prevent.

## Tool naming across upstreams

- **The scheme is `<gateway-slug>-<tool-name>`,** with underscores turned into hyphens. For example, `read_wiki_structure` becomes `deepwiki-read-wiki-structure`.
- **The slug comes from the operator's gateway name,** not from the server's self-reported `serverInfo`. That's good, and it matches the spec's advice.
- **Routing uses a stored mapping,** with `originalName`, `customName` and `gatewaySlug` per tool, rather than parsing the name. A hyphen separator can't be split unambiguously, because slugs and tool names both contain hyphens.
- **v1.1.0 rejects colliding names** at registration time across visibility scopes, per the release notes.
- **Upstream annotations come through empty.** DeepWiki sends none, so there's nothing for policy to use.

Lesson for ADR-002: a reversible naming scheme, an id with no `__` plus a split on the first `__`, means Tollgate needs no lookup table to route. Keeping the upstream's original characters avoids surprising renames.

## Audit and observability

- **Off by default:** `AUDIT_TRAIL_ENABLED`, `SECURITY_LOGGING_ENABLED`, `STRUCTURED_LOGGING_DATABASE_ENABLED`, `OBSERVABILITY_ENABLED` and `OTEL_ENABLE_OBSERVABILITY` all default to false. Out of the box, `/api/logs/audit-trails` is empty.
- **With audit on, only admin actions are recorded.** Creating the gateway and creating the server produced records. Tool calls, both successful and failed, produced **none**, and none appeared in the activity log or security events either.
- **The audit record shape** is: `id`, `timestamp`, `correlation_id`, `action`, `resource_type`, `resource_id`, `resource_name`, `user_id`, `user_email`, `success`, `requires_review`, `data_classification`. There's no hash chain, previous-record link or signature. There's also no MCP method, OWASP ASI category or upstream identity. It's a database table, not a published schema.
- **Traces** use OpenTelemetry spans, with HTTP, MCP and some GenAI attributes. Keys seen: `mcp.method.name`, `mcp.protocol.version`, `mcp.tool.name`, `gen_ai.operation.name`, `gen_ai.tool.name`, `jsonrpc.request.id`, `tool.gateway_id`, `user.email`, `user.is_admin`. It optionally adds `langfuse.*` attributes. It traces outbound MCP calls as `MCP send <method>` spans.
- **No cost on tool calls.** No `gen_ai.usage.*`, token, price or cost attributes appeared on tool-call spans, and the OpenAPI schemas have no cost or budget fields. Per its docs, the separate LLM provider layer reports token usage and cost. I didn't test it, since it needs a model provider key.
- **Metrics:** `/v1/metrics` gives per-entity counts and response times. `/metrics/prometheus` exists. A large admin observability API covers top-slow, top-errors, heatmaps and tool chains.

## Licence and platform

- **Licence:** Apache-2.0.
- **arm64:** the README still says arm64 "is not supported on production". But `v1.1.0` and `latest` ship a native `linux/arm64` image, and it ran without Rosetta. The gap is in support, not in builds. That matters for Tollgate's Oracle Ampere A1 target, which is arm64.
- **Image tags:** releases are tagged `v1.1.0`. Tags in the form `1.1.0` and `1.0.0-RC-3` don't exist, so the research notes are stale on this point. The project went stable at v1.0.8 on 18 August 2026.

## Operational footprint

| Measure | Value |
|---|---|
| Image size | 590 MB |
| Memory, idle after calls, 2 workers | 683 MB |
| Default worker count on this host | 16 |
| API routes in OpenAPI | 490 |
| GitHub stars | 4,669 |

**Secure-by-default checks it enforces:** startup fails if the default user password is under 12 characters. It also logs errors when cross-gateway routing is left unconfigured.

## What this means for ADR-001

**Arguments that no longer hold:**
- "Built on 2026-07-28 from day one." ContextForge negotiates it too, and on the same SDK.
- "It doesn't detect name collisions." v1.1.0 does.

**Arguments that hold, with evidence:**
1. **Tool invocations aren't audited, and audit records aren't tamper-evident.** Tollgate's hash-chained, published audit schema covering every `tools/call` is a real difference.
2. **Tool calls aren't cost-attributed.** Tollgate's ledger by user, agent, tool and task is a real difference.
3. **Conformance gaps.** Cases 3, 4, 8 and the default Origin behaviour. Tollgate can claim and prove strict conformance with the official suite in CI.
4. **Size and focus.** A 490-route platform against a small, auditable control plane that one engineer can explain end to end. This argument is about portfolio and teaching value, so state it honestly, not as a product claim.
5. **Secure defaults.** Audit, security logging and Origin checks are opt-in. Tollgate turns them on and can't run without them.

## What this means for Tollgate's plan

- **Southbound, Tollgate must speak legacy too.** The one public server tested, DeepWiki, is legacy-only. Day 5 of the Week 1 plan marks non-2026 upstreams as `incompatible`, which would exclude servers like this. Keep the northbound side modern-only, as in ADR-003, but let the upstream client fall back to `initialize`. The SDK's `Client` already negotiates eras.
- **Case 3 is worth a test** in Tollgate's version gate, and possibly an upstream issue on ContextForge.
- **Case 8 confirms the plan's error rule:** unknown tool is `-32602`, not `isError`.

## How to reproduce

```bash
docker pull ghcr.io/ibm/mcp-context-forge:v1.1.0
```

Generate four secrets into an env file: `JWT_SECRET_KEY`, `AUTH_ENCRYPTION_SECRET`, `PLATFORM_ADMIN_PASSWORD` and `DEFAULT_USER_PASSWORD`, each at least 12 characters. Then run:

```bash
docker run -d --name contextforge -p 127.0.0.1:4444:4444 --env-file cf.env -e GUNICORN_WORKERS=2 -e MCPGATEWAY_ADMIN_API_ENABLED=true -e HOST=0.0.0.0 -e AUTH_REQUIRED=true -e PLATFORM_ADMIN_EMAIL=admin@example.com -e DATABASE_URL=sqlite:///./mcp.db -e AUDIT_TRAIL_ENABLED=true -e OTEL_ENABLE_OBSERVABILITY=true -e OTEL_TRACES_EXPORTER=console ghcr.io/ibm/mcp-context-forge:v1.1.0
```

Mint a token inside the container:

```bash
docker exec contextforge sh -c 'python3 -m mcpgateway.utils.create_jwt_token --username admin@example.com --admin --exp 240 --secret "$JWT_SECRET_KEY"'
```

Then register an upstream with `POST /gateways`, create a virtual server with `POST /servers`, and send MCP requests to `/servers/{id}/mcp`.
