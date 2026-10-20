# Handoff to a cloud probe session

Use branch `poc/mcp-cloud-capability-fixture` of `xormania/xorder`, based on
`feat/xorder-mcp`. Read this directory's README and RESULTS before setup.

1. Identify your actual product, UI entry point and environment type. Record
   whether the caller is the outer cloud conversation, an inner CLI or an SDK
   test client. Do not guess from a model name or installed executable.
2. Run the native fixture smoke test. If Docker is available, build the image
   and run `verify-image.sh`. Keep the source commit and image ID with results.
   A Docker failure is useful evidence; continue with native installation.
3. Register the fixture with the actual session using the platform's supported
   mechanism. Make a native `xorder_probe_status` call with a fresh challenge,
   then retrieve the packet. Preserve the native call/result and packet hash.
   If registration is inaccessible, identify the exact missing interface or
   account action. Shell-driven success is a separate result.
4. Test a supported native diagnostic event using the diagnostic command. Keep
   hook execution, model delivery and subsequent retrieval/retry separate.
   Evaluate behavior in a fresh session that has not read the packet's answer.
5. Create a marker in the proposed persistent location. In a genuinely new
   session, read it before setup can recreate state, and retest configuration
   and MCP visibility. Record which session/environment was reused.

Copy `result-template.json` into your own `mcp/poc/cloud-probe-<surface>/`
directory. Fill it from evidence, leave unexecuted checks `not_tested`, and
retain sanitized native traces. First report the decisive result or precise
blocker, then the smallest next step. The fixture is not an OAuth server or
an automatic installation mechanism; those host interfaces remain to be tested.

Keep your changes in your session branch. Do not modify accepted catalog
availability or merge into master. Coordinate any fixture corrections rather
than replacing another session's packet bytes without updating its identity.
