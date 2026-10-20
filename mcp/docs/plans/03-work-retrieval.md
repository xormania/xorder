# Session C: actual Work conversation retrieval

**Work branch:** `poc/mcp-work-retrieval`, from `feat/xorder-mcp`.

**Owns:** `mcp/poc/work-retrieval/`.

## Question and first result

Can a new personal Work conversation discover the installed xorder MCP and
retrieve a uniquely marked packet from the intended service?

Prove registration in the conversation. A successful curl request or server
started in a scratch workspace does not answer this question.

## Work

1. Verify the current official [plugin quickstart][quickstart] and
   [connection guide][connect] for the target account/product.
2. Choose the fastest available supported route: public HTTPS or
   [Secure MCP Tunnel][tunnel] to a private/local service.
   Record where the actual request originates and which process must stay alive.
3. Use A's server when available. Otherwise build the smallest disposable SDK
   fixture under this PoC, matching the shared packet contract. Label that
   server temporary and rerun against A after integration.
4. Establish endpoint reachability and the selected supported authentication
   route. A non-sensitive fixture can prove initial connection; separately
   record whether authenticated private access has been demonstrated.
5. Connect/install the plugin through the supported account flow. If an owner
   action is required, provide the tested endpoint, exact settings, and remaining
   action rather than an open-ended setup request.
6. In a new Work conversation, explicitly retrieve the marked packet. Retain
   discovered tool metadata, the tool call, returned identity, and visible result.
7. Try an indirect task without naming the packet to observe voluntary discovery.
   Treat that result separately from reliable registration.
8. Change the fixture version and test the documented metadata refresh/new-chat
   behavior. Check the effect of stopping/restarting the service or tunnel.

## Acceptance

- The tool is registered in the intended conversation.
- The selected packet identity and content are actually returned there.
- The actual caller can reach the endpoint through the chosen route.
- Authentication and private-content status are accurately described.
- Service/tunnel and conversation lifecycle dependencies are recorded.
- Failure to connect is distinguishable from no tool selection by the model.

This session proves retrieval, not interception of arbitrary workspace edits.
D investigates asynchronous feedback independently.

## Early decision and handoff

Test registration before writing a deployment platform. If the account or route
is unavailable, report the exact missing capability/access and retain the runnable
server/configuration. Try a second route only when documentation or an observed
failure supplies a concrete reason.

Deliver README commands/configuration, sanitized evidence, and `RESULTS.md`.
Publish a working endpoint contract for D when available; D need not wait to
implement its fixture producer. Open a PR to `feat/xorder-mcp`; do not merge.

[quickstart]: https://developers.openai.com/plugins/quickstart
[connect]: https://developers.openai.com/plugins/deploy/connect-chatgpt
[tunnel]: https://developers.openai.com/api/docs/guides/secure-mcp-tunnels
