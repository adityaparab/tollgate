# MCP 2026-07-28 cheat sheet

A one-page working reference for building Tollgate. It covers the stateless core of MCP revision 2026-07-28 over Streamable HTTP. Where a rule matters to a gateway, it says so.

Source pages: [changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog) · [base protocol](https://modelcontextprotocol.io/specification/2026-07-28/basic/index) · [versioning](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning) · [Streamable HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http) · [discover](https://modelcontextprotocol.io/specification/2026-07-28/server/discover) · [tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) · [MRTR](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/mrtr) · [caching](https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/caching)

## The one idea

Every request stands alone. There is no handshake and no session. Each request carries everything the server needs: protocol version, client capabilities and, optionally, client identity. Any server replica can answer any request. Long-lived state lives behind explicit handles that the client passes as ordinary tool arguments.

## The life of one `tools/call`

1. **The client POSTs** one JSON-RPC request to the single MCP endpoint, for example `/mcp`.
2. **Headers mirror the body**, so intermediaries can route without parsing JSON:

   ```http
   POST /mcp HTTP/1.1
   Content-Type: application/json
   Accept: application/json, text/event-stream
   MCP-Protocol-Version: 2026-07-28
   Mcp-Method: tools/call
   Mcp-Name: get_weather
   ```

3. **The body carries the per-request metadata** in `params._meta`:

   ```json
   {
     "jsonrpc": "2.0",
     "id": 1,
     "method": "tools/call",
     "params": {
       "name": "get_weather",
       "arguments": { "location": "Seattle, WA" },
       "_meta": {
         "io.modelcontextprotocol/protocolVersion": "2026-07-28",
         "io.modelcontextprotocol/clientCapabilities": {},
         "io.modelcontextprotocol/clientInfo": { "name": "ExampleClient", "version": "1.0.0" }
       }
     }
   }
   ```

4. **The server validates, in this order of concern:** the `Origin` header, then that headers match the body, then that the version is supported, then that the required `_meta` keys are present.
5. **The server answers** with either `application/json`, one object, or `text/event-stream`, an SSE stream for this request only. The stream may carry `notifications/progress` or `notifications/message` before the final response, and the final response ends it.
6. **The result always has a `resultType`.** It is `"complete"` for a normal result. It is `"input_required"` when the server needs more input first; see MRTR below.
7. **Closing the stream cancels the request.** Streams are not resumable, so a client that loses one re-sends the request with a new id.

## Required headers

| Header | Value comes from | Required on | If missing or wrong |
|---|---|---|---|
| `MCP-Protocol-Version` | `_meta["io.modelcontextprotocol/protocolVersion"]` | Every POST | 400, `-32020` HeaderMismatch |
| `Mcp-Method` | `method` | Every request | 400, `-32020` |
| `Mcp-Name` | `params.name`, or `params.uri` for resources | `tools/call`, `resources/read`, `prompts/get` | 400, `-32020` |
| `Mcp-Param-{Name}` | A tool argument marked `x-mcp-header` in its `inputSchema` | Whenever that argument has a value | 400, `-32020` |
| `Accept` | Must list `application/json` and `text/event-stream` | Every POST | Transport-level rejection |

**Encoding.** A value that isn't plain visible ASCII, or that has leading or trailing spaces, is sent as `=?base64?<base64 of UTF-8>?=`. A plain value that happens to look like that pattern is encoded too. Servers decode before comparing with the body.

**Comparison rules.** Header names are case-insensitive. Header values are case-sensitive. Integers compare numerically.

**Gateway rule.** An intermediary that enforces policy from mirrored headers SHOULD reject protocol versions that don't require header and body to match, rather than trust headers it can't validate. This is why Tollgate's northbound side is modern-only.

**Intermediary rule.** A proxy that doesn't recognise an `Mcp-Param-*` header must forward it unchanged.

## Required `_meta` keys on every request

| Key | Required | Notes |
|---|---|---|
| `io.modelcontextprotocol/protocolVersion` | Yes | Must equal the `MCP-Protocol-Version` header |
| `io.modelcontextprotocol/clientCapabilities` | Yes | Capabilities relevant to this request |
| `io.modelcontextprotocol/clientInfo` | SHOULD | Self-reported. Never base security decisions on it |
| `io.modelcontextprotocol/logLevel` | No | Without it, the server must not send `notifications/message` |
| `traceparent`, `tracestate`, `baggage` | No | W3C trace context. Week 7 uses these |

A request missing a required key gets `-32602` and HTTP 400. Results SHOULD carry `io.modelcontextprotocol/serverInfo` in their `_meta`, which is also self-reported and also not for security decisions.

**Key naming.** A prefix whose second label is `modelcontextprotocol` or `mcp` is reserved, for example `io.modelcontextprotocol/`. Tollgate's own keys need a prefix of its own, such as `io.github.adityaparab.tollgate/`.

## Error codes

| Code | Name | When | HTTP status |
|---|---|---|---|
| `-32700` | Parse error | Body is not valid JSON | Not fixed by the spec |
| `-32600` | Invalid request | Not a valid JSON-RPC request | Not fixed by the spec |
| `-32601` | Method not found | Unknown RPC method | 404 |
| `-32602` | Invalid params | Missing required `_meta`, unknown tool, unknown resource | 400 for missing `_meta`; otherwise not fixed |
| `-32603` | Internal error | Server fault | Not fixed by the spec |
| `-32020` | HeaderMismatch | Header missing, malformed, or different from the body | 400 |
| `-32021` | MissingRequiredClientCapability | Request needs a capability the client didn't declare; `data.requiredCapabilities` lists it | 400 |
| `-32022` | UnsupportedProtocolVersion | Version not served; `data.supported` and `data.requested` | 400 |

**Code ranges.**
- `-32000` to `-32019` is legacy. Don't use it.
- `-32020` to `-32099` belongs to the spec only. Never invent codes there.
- Application errors go outside `-32768` to `-32000`.

**Retired codes.** `-32002` (resource not found) and `-32042` are retired. Accept `-32002` from older servers, but never emit it.

## Protocol error or tool error?

| Situation | Report as | Why |
|---|---|---|
| Unknown tool, malformed request, server fault | JSON-RPC error, for example `-32602` | The model can't fix it |
| Bad argument values, upstream API failure, business-rule failure | Result with `isError: true` | The model can read it and retry differently |

For Tollgate: an unknown namespaced tool is a protocol error. An upstream that times out is a tool error, with a message the model can act on.

## What disappeared compared with 2025-11-25

| Gone | Replaced by | Why a gateway is glad |
|---|---|---|
| `initialize` and `notifications/initialized` | Per-request `_meta`, plus `server/discover` | No handshake state to hold per client |
| `Mcp-Session-Id` and protocol sessions | Nothing. Use explicit handles in tool arguments | Any replica serves any request, so no sticky load balancing |
| HTTP GET stream; `resources/subscribe` and `resources/unsubscribe` | `subscriptions/listen`, one long-lived POST stream | One endpoint, one method, POST only |
| Server-initiated requests on streams: sampling, elicitation, roots | MRTR: `InputRequiredResult` and a client retry | Every exchange is client-initiated, so the gateway sees and can police all of it |
| `ping` and `logging/setLevel` | Log level per request in `_meta` | Fewer methods to route |
| SSE resumability and `Last-Event-ID` | Re-send with a new id | No replay buffers |
| Tasks in the core protocol | The `io.modelcontextprotocol/tasks` extension | Optional; negotiated through `capabilities.extensions` |

**Deprecated, but still working for at least 12 months:** Roots, Sampling, Logging, the old HTTP+SSE transport, and Dynamic Client Registration, which gives way to Client ID Metadata Documents.

## `server/discover`

- Servers **must** implement it. Clients may call it first, but don't have to.
- The request has only `_meta`. The result looks like this:

  ```json
  {
    "resultType": "complete",
    "supportedVersions": ["2026-07-28"],
    "capabilities": { "tools": {} },
    "instructions": "Optional guidance for the model",
    "_meta": { "io.modelcontextprotocol/serverInfo": { "name": "x", "version": "1.0.0" } },
    "ttlMs": 3600000,
    "cacheScope": "public"
  }
  ```

- On HTTP, a client can find out a server's era without discover. It sends a modern request; a `400` carrying a recognised modern error means a modern server. Anything else means fall back to `initialize`.

## Tools

- **`tools/list` must not vary by connection.** It may vary by the caller's authorization. It is paginated with `cursor` and `nextCursor`, and SHOULD come back in a **deterministic order** so prompt caches hit.
- **Tool names** SHOULD be 1 to 128 characters from `A-Z a-z 0-9 _ - .`, and are case-sensitive. The spec says aggregators SHOULD prefix names to avoid collisions, and SHOULD NOT use `serverInfo.name` for that. That rule backs ADR-002.
- **Annotations** such as `destructiveHint` and `readOnlyHint` are **untrusted** unless the server is trusted. Tollgate's policy engine must not rely on them alone.
- **Results** carry `content`, plus optional `structuredContent` that must match `outputSchema` if one exists, plus `isError`.

## MRTR: when the server needs more input

1. The server returns `resultType: "input_required"` with `inputRequests`. This is a map of id to an `elicitation/create`, `sampling/createMessage` or `roots/list` request. It may also return an opaque `requestState`.
2. The client gathers answers and **retries the original request with a new JSON-RPC id**. It adds `inputResponses` and echoes `requestState` byte for byte.
3. **Only three methods may do this:** `tools/call`, `resources/read` and `prompts/get`.
4. **`requestState` comes back through the client, so treat it as attacker-controlled.** If it affects authorization or business logic, protect it with an HMAC or AEAD. Bind it to the principal, a short expiry, and the originating request.
5. **Don't cache interim results or retries.**

Tollgate's Week 6 approval gate uses exactly this flow. A parked `tools/call` returns `input_required`; when the human approves, the client's retry resumes the DBOS workflow.

## Caching

- **Hints are required on complete results** of `server/discover`, `tools/list`, `prompts/list`, `resources/list`, `resources/templates/list` and `resources/read`. The hints are `ttlMs`, which must be 0 or more, and `cacheScope`, which is `"public"` or `"private"`.
- **`public`** means any shared gateway may serve the response to any user.
- **`private`** means the cache must be keyed by authorization context. A different token needs a different cache.
- **The cache key is the method plus the parameters that matter,** such as `cursor` or `uri`.
- **A `list_changed` notification invalidates** a cached list immediately.
- **Every page of one list must use the same `cacheScope`.**

Tollgate's Week 2 cache must respect this. Once policy filters tools per user in Week 5, Tollgate's own `tools/list` becomes `private`.

## Statelessness checklist for Tollgate

- [ ] No decision depends on an earlier request from the same connection.
- [ ] No per-client memory between requests. Process-wide upstream connections are fine.
- [ ] GET or DELETE on `/mcp` returns 405. A stray `Mcp-Session-Id` or `Last-Event-ID` is ignored.
- [ ] `Origin` is validated. Locally, bind to `127.0.0.1`.
- [ ] State across calls only through explicit, authorized handles, or through integrity-protected `requestState`.
