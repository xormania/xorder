"""Read-only pull observations and explicit startup disk estimates."""
import json
from pathlib import Path
import shutil
import subprocess

from runtime import nonnegative_setting

GIB = 1024**3


def docker_json(arguments, env):
    try:
        result = subprocess.run(["docker", *arguments], env=env, capture_output=True, text=True, timeout=20)
        return json.loads(result.stdout) if result.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def image_manifest(reference, platform, env):
    manifest = docker_json(["manifest", "inspect", reference], env)
    for _ in range(3):
        if not isinstance(manifest, dict):
            return None
        if "layers" in manifest:
            return manifest
        requested = platform.split("/") if platform else []
        entries = manifest.get("manifests")
        if not isinstance(entries, list):
            return None
        matches = [item for item in entries
                   if isinstance(item, dict) and isinstance(item.get("platform"), dict)
                   and len(requested) >= 2 and item["platform"].get("os") == requested[0]
                   and item.get("platform", {}).get("architecture") == requested[1]
                   and (len(requested) < 3 or item["platform"].get("variant") == requested[2])]
        if len(matches) != 1:
            return None  # An unknown/ambiguous platform is not a measured pull size.
        digest = matches[0].get("digest")
        if not isinstance(digest, str) or not digest.startswith("sha256:"):
            return None
        repository = reference.split("@", 1)[0]
        tag = repository.find(":", repository.rfind("/") + 1)
        if tag >= 0:
            repository = repository[:tag]
        manifest = docker_json(["manifest", "inspect", repository + "@" + digest], env)
    return None


def manifest_blobs(manifest):
    """Descriptor sizes are registry bytes; compressed layer sizes exclude config."""
    if not isinstance(manifest, dict) or not isinstance(manifest.get("layers"), list):
        return None
    blobs = {}
    for item in [manifest.get("config"), *manifest["layers"]]:
        if not isinstance(item, dict) or not isinstance(item.get("digest"), str):
            return None
        size = item.get("size")
        if type(size) is not int or size < 0:
            return None
        previous = blobs.get(item["digest"])
        if previous and previous["size"] != size:
            return None
        blobs[item["digest"]] = item
    return blobs


def recorded_sizes(repository, platform):
    sizes = {}
    try:
        for image in json.loads((repository / "catalog.json").read_text())["images"]:
            for item in image.get("platforms", []):
                if platform and item.get("platform") != platform:
                    continue
                size = item.get("metrics", {}).get("image_size_bytes")
                if type(size) is int and size >= 0:
                    for reference in (image.get("digest_reference"), image.get("exact_reference")):
                        if reference:
                            sizes[reference] = size
    except (OSError, ValueError, KeyError):
        pass
    return sizes


def preflight(workspace, configuration, env, repository):
    """Refuse known shortfalls; unavailable size/quota observations remain warnings."""
    reserve = nonnegative_setting(env, "XORDER_DISK_RESERVE_GIB", "1") * GIB
    factor = nonnegative_setting(env, "XORDER_PULL_EXPANSION_FACTOR", "3")
    explicit = nonnegative_setting(env, "XORDER_PULL_BUDGET_GIB", "0") * GIB
    mode = env.get("XORDER_DISK_PREFLIGHT", "refuse")
    if mode not in ("refuse", "warn"):
        raise ValueError("XORDER_DISK_PREFLIGHT must be refuse or warn")
    client_free = shutil.disk_usage(workspace).free
    # Cheap reserve check comes before optional network manifest observations.
    if client_free < reserve:
        message = (f"disk preflight: checkout has {client_free/GIB:.2f} GiB free; "
                   f"configured stack reserve is {reserve/GIB:.2f} GiB")
        if mode == "refuse":
            raise ValueError(message + "; reclaim space before up or deliberately adjust XORDER_DISK_RESERVE_GIB")
        print("WARNING: " + message, flush=True)
    info = docker_json(["info", "--format", "{{json .}}"], env)
    info = info if isinstance(info, dict) else {}
    architecture = {"x86_64": "amd64", "aarch64": "arm64"}.get(info.get("Architecture"), info.get("Architecture"))
    platform = env.get("DOCKER_DEFAULT_PLATFORM") or (
        info["OSType"] + "/" + architecture if info.get("OSType") and architecture else None)
    requests = {(service["image"], service.get("platform") or platform)
                for service in configuration.get("services", {}).values()
                if isinstance(service, dict) and service.get("image")}
    unique_blobs, estimates, unknown = {}, [], []
    for reference, selected in sorted(requests, key=lambda item: (item[0], item[1] or "")):
        local = docker_json(["image", "inspect", reference], env)
        if isinstance(local, list) and local:
            candidate = local[0]
            actual = candidate.get("Os", "") + "/" + candidate.get("Architecture", "")
            if selected and len(selected.split("/")) == 3:
                actual += "/" + candidate.get("Variant", "")
            if not selected or actual == selected:
                print(f"pull: {reference} already local", flush=True)
                continue
        blobs = manifest_blobs(image_manifest(reference, selected, env))
        advertised = sum(item["size"] for item in blobs.values()) if blobs is not None else None
        if blobs is not None:
            compressed = sum(item["size"] for item in blobs.values()
                             if item.get("mediaType", "").endswith(("gzip", "zstd")))
            print(f"pull: {reference}: registry blobs {advertised/1024**2:.1f} MiB, "
                  f"compressed layers {compressed/1024**2:.1f} MiB "
                  "(advertised full image; locally shared layers may reduce transfer)", flush=True)
            unique_blobs.update(blobs)
        else:
            print(f"WARNING: pull size unknown for {reference}; registry metadata/platform unavailable", flush=True)
        measured = recorded_sizes(repository, selected).get(reference)
        if measured is not None:
            estimates.append(2 * measured)
        elif advertised is not None:
            estimates.append(factor * advertised)
            print(f"WARNING: {reference}: unpacked size unknown; using {factor:g}x registry-byte planning estimate", flush=True)
        else:
            unknown.append(reference)
    pull_estimate = max(sum(estimates), sum(item["size"] for item in unique_blobs.values()), explicit)
    print(f"disk preflight: stack reserve {reserve/GIB:.2f} GiB; missing-image cold-pull estimate "
          f"{pull_estimate/GIB:.2f} GiB (estimate, not a quota or transfer guarantee)", flush=True)
    if unknown:
        print("WARNING: disk preflight cannot fully budget unknown images: " + ", ".join(unknown) +
              "; set XORDER_PULL_BUDGET_GIB from a trusted size observation", flush=True)
    daemon_root = info.get("DockerRootDir")
    # A local socket does not prove that the daemon's filesystem is this
    # client's filesystem (Desktop, forwarded and mounted sockets are common).
    # Only the caller can confirm a client-visible path for the selected engine.
    confirmed_root = env.get("XORDER_DOCKER_DATA_DIR")
    docker_free = None
    if confirmed_root:
        path = Path(confirmed_root)
        if not path.is_absolute() or not path.is_dir():
            raise ValueError("XORDER_DOCKER_DATA_DIR must be an existing absolute client-visible directory confirmed for the selected Docker engine")
        try:
            docker_free = shutil.disk_usage(path).free
            shared = path.stat().st_dev == workspace.stat().st_dev
        except OSError:
            pass
    if docker_free is None:
        print("WARNING: Docker data filesystem free space is unverified from this client; "
              "the daemon-reported root alone does not establish filesystem locality. "
              "Check the daemon/VM disk separately before pulling, or set XORDER_DOCKER_DATA_DIR "
              "to its confirmed client-visible data directory", flush=True)
    else:
        required = pull_estimate + (reserve if shared else 0)
        print(f"disk preflight: Docker data filesystem {docker_free/GIB:.2f} GiB free; "
              f"estimated required {required/GIB:.2f} GiB", flush=True)
        if docker_free < required:
            message = "disk preflight: Docker data filesystem is below the configured cold-pull/startup estimate"
            if mode == "refuse":
                raise ValueError(message + "; reclaim space before up or deliberately use XORDER_DISK_PREFLIGHT=warn")
            print("WARNING: " + message, flush=True)
    return {"reserve_bytes": reserve, "pull_estimate_bytes": pull_estimate,
            "advertised_unique_blob_bytes": sum(item["size"] for item in unique_blobs.values()),
            "unknown_images": unknown, "checkout_free_bytes": client_free, "docker_free_bytes": docker_free,
            "daemon_reported_data_root": daemon_root, "docker_data_root_confirmed": bool(confirmed_root)}
