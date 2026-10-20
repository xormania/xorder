#!/usr/bin/env bash
# Run from any directory. Requires Docker and a host Python with requirements.lock.
set -euo pipefail
fixture=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
image=${1:?usage: verify-image.sh IMAGE [OUTPUT_DIRECTORY]}
output=${2:-out/cloud-probe-container}
probe_python=${PROBE_PYTHON:-python3}
mkdir -p "$output"
output=$(cd -- "$output" && pwd)
temporary=$(mktemp -d)
container_id=
cleanup() {
  if [ -n "$container_id" ]; then docker rm -f "$container_id" >/dev/null; fi
  rm -rf -- "$temporary"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
docker image inspect "$image" --format '{{.Id}}' > "$output/image-id.txt"
docker image inspect "$image" --format '{{json .Config.Labels}}' > "$output/image-labels.json"

# The image must work without package downloads or model credentials at runtime.
docker run --rm --network none "$image" \
  /opt/xorder-cloud-probe/venv/bin/python /opt/xorder-cloud-probe/smoke.py > "$output/in-container.json"
"$probe_python" "$fixture/smoke.py" --output "$output/stdio-from-host.json" \
  --stdio-command docker run --rm -i --network none "$image" xorder-cloud-probe serve > /dev/null

# An explicit published port, tested from outside the container.
container_id=$(docker run --detach --publish 127.0.0.1::8000 "$image")
port=$(docker inspect "$container_id" --format '{{(index (index .NetworkSettings.Ports "8000/tcp") 0).HostPort}}')
"$probe_python" - "$port" <<'PY'
import socket, sys, time
deadline = time.monotonic() + 20
while time.monotonic() < deadline:
    try:
        with socket.create_connection(("127.0.0.1", int(sys.argv[1])), timeout=1):
            break
    except OSError:
        time.sleep(0.1)
else:
    raise SystemExit("Container port did not become reachable")
PY
"$probe_python" "$fixture/smoke.py" --url "http://127.0.0.1:$port/mcp" \
  --output "$output/http-from-host.json" > /dev/null
docker logs "$container_id" > "$output/server.log" 2>&1

# Two different containers, one explicitly retained directory. No named volume remains.
mkdir "$temporary/state"
chmod 0777 "$temporary/state"
for action in create read; do
  docker run --rm --network none --mount "type=bind,src=$temporary/state,dst=/probe-state" \
    "$image" xorder-cloud-probe state "$action" --directory /probe-state \
    --challenge container-restart > "$output/state-$action.json"
done
cmp "$output/state-create.json" "$output/state-read.json"
"$probe_python" - "$output" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
for name in ("in-container.json", "stdio-from-host.json", "http-from-host.json"):
    report = json.loads((root / name).read_text())
    assert report["status"] == "passed", name
    assert all(item["server"]["uid"] == 1000 for item in report["observations"]), name
print("Image checks passed: offline runtime, stdio, published HTTP port, UID, retained directory.")
print("Native cloud registration, hook delivery and fresh-session reuse remain untested.")
PY
