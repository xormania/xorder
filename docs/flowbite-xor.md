# flowbite-xor profile compatibility

The repository is now [xormania/uxor](https://github.com/xormania/uxor).
Read the current [uxor development and testing profile](uxor.md).

Published `flowbite-xor-dev` image names, exact tags and digests remain usable.
The legacy `examples/flowbite-xor/run.sh` entry point and `FLOWBITE_PROJECT`
variable remain accepted; new sessions can use `examples/uxor/run.sh` and
`UXOR_PROJECT`. Both entry points retain the same default stack and state
identities for a given workspace.
