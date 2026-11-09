# Runtime capability build components

Python development, the Python compatibility matrix, live harnesses, and Rust
retain their public image lines and runtime contracts. Their new revisions build
from independently verified internal components. A component definition is build
intent; it is not an available public development image or an accepted release.

| Component | Exact inputs | Consumers |
| --- | --- | --- |
| `python-foundation` | Python 3.14 upstream digest, common Debian installer and package-feed observations, shared workspace/user entrypoint | Python development and live harnesses |
| `python-matrix-interpreters` | Same upstream Python/Trixie platform, uv digest, managed interpreter pins and installer | Python compatibility matrix |
| `rust-toolchain` | Rust 1.99 upstream digest, rustfmt, Clippy and wasm target installation recipe | Rust development |

The Python foundation is the actual filesystem parent of both Python development
and live harnesses. It supplies the existing Debian tools, development libraries,
user, HOME and workspace. Python development adds uv from its exact upstream OCI
image and retains the uv-aware certificate entrypoint. Harnesses add their Node
OCI payload, tmux, signature verification tools and launch helpers. They retain
their existing root-owned HOME initialization checks before UID/GID remapping.
A Node refresh does not rebuild the Python foundation; a uv refresh affects only
its declared consumers. The foundation records its actual upstream repository and
digest. Each consuming image checks that record against its own declared base
before assembly; an independently changed Python or harness base cannot silently
reuse a foundation built from another upstream. Informational tags do not alter
this digest comparison.

Managed matrix interpreters are installed together from the qualified version
map into `/opt/xorder/python` and `/opt/xorder/python-bin`. The matrix image copies
those immutable paths from the verified component, while installing tmux in its
own operating-system layer. Interpreter installation therefore does not depend
on tmux, application state, HOME contents or the parent's uv runtime configuration.
Runtime downloads remain disabled. This component keeps the three pinned
interpreters as one qualified compatibility tuple.

Rust formatter, Clippy and wasm installation happen on the exact Rust upstream
image before xorder's Debian development setup. A package-feed refresh can update
native build libraries without downloading those fixed Rust components again.
The final image inherits the Rust component as its actual filesystem parent;
compiler files and native libraries are not copied between unrelated runtime
bases.

Component identities include the exact platform and declared ABI. Their builders
must verify the component before publication, and final images still run normal
readiness checks. Source labels are added only to final image metadata. Cache
imports and local cache mounts do not themselves establish durable component
publication or a verified final image.

The existing UXor and FrankenPHP definitions, scripts and qualified image pins
are unchanged by this decomposition. Their later configuration migration is a
separate consumer change.
