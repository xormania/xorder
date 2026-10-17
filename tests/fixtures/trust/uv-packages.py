"""Create tiny PEP 517 backend/proof wheels without external build tools."""
import hashlib
import sys
import zipfile
from pathlib import Path


def wheel(directory, name, contents):
    filename = f"{name}-1.0.0-py3-none-any.whl"
    metadata = f"{name}-1.0.0.dist-info"
    files = {**contents,
             f"{metadata}/METADATA": f"Metadata-Version: 2.3\nName: {name}\nVersion: 1.0.0\n",
             f"{metadata}/WHEEL": "Wheel-Version: 1.0\nGenerator: xorder-fixture\nRoot-Is-Purelib: true\nTag: py3-none-any\n"}
    files[f"{metadata}/RECORD"] = "".join(f"{path},,\n" for path in [*files, f"{metadata}/RECORD"])
    directory.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(directory / filename, "w") as archive:
        for path, value in files.items():
            archive.writestr(path, value)
    digest = hashlib.sha256((directory / filename).read_bytes()).hexdigest()
    (directory / "index.html").write_text(f'<a href="{filename}#sha256={digest}">{filename}</a>\n')


def main():
    directory, origin = Path(sys.argv[1]), sys.argv[2]
    if origin == "first":
        # This wheel itself must be downloaded by uv's isolated PEP 517 build.
        # Importing the proof dependency additionally proves the locked runtime
        # wheel from the independent second origin was installed.
        backend = '''from pathlib import Path
import zipfile

def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    name = "fixture_uv_project-1.0.0-py3-none-any.whl"
    dist = "fixture_uv_project-1.0.0.dist-info"
    files = {
        "fixture_uv_project.py": "from fixture_uv_proof import PROOF\\nBUILT = 'isolated HTTPS backend'\\n",
        dist + "/METADATA": "Metadata-Version: 2.3\\nName: fixture-uv-project\\nVersion: 1.0.0\\nRequires-Dist: fixture-uv-proof==1.0.0\\n",
        dist + "/WHEEL": "Wheel-Version: 1.0\\nGenerator: xorder-tls-backend\\nRoot-Is-Purelib: true\\nTag: py3-none-any\\n",
    }
    files[dist + "/RECORD"] = "".join(path + ",,\\n" for path in [*files, dist + "/RECORD"])
    with zipfile.ZipFile(Path(wheel_directory) / name, "w") as archive:
        for path, value in files.items():
            archive.writestr(path, value)
    return name
'''
        wheel(directory / "simple/fixture-uv-backend", "fixture_uv_backend", {"fixture_uv_backend.py": backend})
    else:
        wheel(directory / "simple/fixture-uv-proof", "fixture_uv_proof",
              {"fixture_uv_proof.py": "PROOF = 'independent HTTPS wheel'\n"})


if __name__ == "__main__":
    main()
