# Session E: Codex Cloud outer-session registration

**Work branch:** `poc/mcp-codex-cloud`, from `feat/xorder-mcp`.

**Owns:** `mcp/poc/codex-cloud-registration/`.

## Question and first result

Which supported configuration path, if any, registers an MCP with the actual
reusable Codex Cloud session? This unresolved interface is the first thing to
test, before building a Codex-specific installer.

A server running inside the workspace or a separately launched inner CLI is
not proof that the surrounding session has its tools.

## Work

1. Record the exact product, environment mode, account/workspace, and launch
   mechanism. Distinguish current reusable Cloud from legacy integrations,
   hosted Work, and a native CLI on an owned host.
2. Inspect current supported configuration sources, local installed product
   documentation/code where available, and the official
   [environment][env] and [configuration][config] references.
3. Test the strongest documented outer-registration route with a minimal
   uniquely marked retrieval tool. Use A's server or a temporary SDK stub.
4. Investigate the documented
   `mcp_servers.<id>.experimental_environment = "remote"` lead only if the actual
   product exposes the controlling configuration. Do not assume a workspace
   configuration file is read by the outer orchestrator.
5. Demonstrate tool discovery and retrieval from the actual conversation.
   Retain what configuration source caused it.
6. Only after registration succeeds, test startup context and a native diagnostic
   route separately. A start skill is not assumed to be a per-tool callback.
7. Exercise a fresh task and the appropriate republish/update behavior. Record
   which tasks retain old state.
8. If registration is blocked, test useful startup context independently where
   supported, without relabeling that as MCP registration.

## Acceptance or negative finding

A positive result includes a tool call by the actual hosted session and the
uniquely marked packet response, plus exact setup and version information.

A negative report distinguishes:

- An explicitly documented unsupported route.
- A tested configuration that was ignored or rejected.
- Missing account access or an unavailable setting.
- A configuration source that remains unknown.

“Could not find it” is not proof that all cloud MCP is impossible. Likewise,
inner-CLI success does not answer the outer-session question.

## Early decision and deliverables

Aim to test one concrete configuration hypothesis at the first checkpoint.
If it fails, test a second only when evidence identifies a plausible route.
Report the precise boundary rather than spending the session building an
installer around an unproved assumption.

Deliver the smallest runnable fixture, attempted configurations, sanitized
observations, and `RESULTS.md`. State what the maintainer can act on: a working
route, a product/account action, or a bounded open question.
Open a PR to `feat/xorder-mcp`; do not merge it.

[env]: https://learn.chatgpt.com/docs/environments/cloud-environments
[config]: https://learn.chatgpt.com/docs/config-file/config-reference
