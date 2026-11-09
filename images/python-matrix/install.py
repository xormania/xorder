#!/usr/bin/env python3
"""Preinstall exact compatibility interpreters outside persisted user storage."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def replace_pip_bootstrap(module, wheel, pin, original):
    """Replace the distributor's exact bundled pip, preserving other wheels."""
    module, wheel = Path(module), Path(wheel)
    old_wheel = module.parent / "_bundled" / f"pip-{original['version']}-py3-none-any.whl"
    for path, expected in ((module, original["module_sha256"]),
                           (old_wheel, original["wheel_sha256"]), (wheel, pin["sha256"])):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"Unexpected Python bootstrap input: {path}")
    source = module.read_text()
    old = f'_PIP_VERSION = "{original["version"]}"'
    if source.count(old) != 1:
        raise RuntimeError("Unexpected ensurepip version declaration")
    destination = old_wheel.with_name(f"pip-{pin['version']}-py3-none-any.whl")
    if destination.exists():
        raise RuntimeError("Replacement pip wheel already exists")
    shutil.copyfile(wheel, destination)
    module.write_text(source.replace(old, f'_PIP_VERSION = "{pin["version"]}"'))
    old_wheel.unlink()

def install_environment(secret=Path("/run/secrets/xorder_ca"),
                        trust_directory=Path("/run/xorder-build-trust"),
                        system_ca=Path("/etc/ssl/certs/ca-certificates.crt")):
    env = {**os.environ, "UV_PYTHON_INSTALL_DIR": "/opt/xorder/python",
           "UV_CACHE_DIR": "/tmp/python-matrix-install-cache"}
    if secret.is_file():
        # Both inputs remain outside image layers: the CA is a BuildKit secret
        # and the combined trust store is on this RUN's tmpfs mount.
        bundle = trust_directory / "ca-bundle.pem"
        bundle.write_bytes(system_ca.read_bytes() + b"\n" + secret.read_bytes())
        env.update(UV_SYSTEM_CERTS="1", SSL_CERT_FILE=str(bundle))
    return env


def main():
    pins = json.loads(Path("/opt/xorder/python-matrix/versions.json").read_text())
    bootstrap = json.loads(Path("/opt/xorder/python-matrix/pip-bootstrap.json").read_text())
    env = install_environment()
    # Install all patches independently of the parent's default Python. Keep
    # /usr/local/bin/python* and its pip environment intact across refreshes.
    subprocess.run(["uv", "python", "install", "--no-bin", *pins.values()], env=env, check=True)
    bin_directory = Path("/opt/xorder/python-bin")
    bin_directory.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="python-matrix-bootstrap-") as temporary:
        wheel = Path(temporary) / f"pip-{bootstrap['version']}-py3-none-any.whl"
        subprocess.run([sys.executable, str(Path(__file__).with_name("fetch_build_input.py")),
                        "--url", bootstrap["url"], "--sha256", bootstrap["sha256"],
                        "--destination", str(wheel), "--cache-dir", "/var/cache/xorder-downloads"],
                       env=env, check=True)
        for minor, expected in pins.items():
            installed = subprocess.check_output(
                ["uv", "python", "find", "--managed-python", "--no-project", expected],
                env={**env, "UV_PYTHON_DOWNLOADS": "never"}, text=True).strip()
            executable = bin_directory / f"python{minor}"
            executable.symlink_to(installed)
            actual = subprocess.check_output(
                [str(executable), "-c", "import platform, sqlite3; print(platform.python_version())"],
                text=True).strip()
            if actual != expected:
                raise SystemExit(f"Python {minor}: expected {expected}, observed {actual}")
            if expected in bootstrap["replacements"]:
                module = subprocess.check_output(
                    [str(executable), "-I", "-c", "import ensurepip; print(ensurepip.__file__)"],
                    text=True).strip()
                replace_pip_bootstrap(module, wheel, bootstrap, bootstrap["replacements"][expected])
                # The distributor owns this build-only update. Keep uv's
                # EXTERNALLY-MANAGED marker so runtime global installs stay guarded.
                subprocess.run([str(executable), "-I", "-m", "pip", "install", "--break-system-packages",
                                "--no-index", "--no-deps", "--upgrade", str(wheel)],
                               env={**env, "PIP_NO_INDEX": "1"}, check=True)
    shutil.rmtree(env["UV_CACHE_DIR"], ignore_errors=True)


if __name__ == "__main__":
    main()
