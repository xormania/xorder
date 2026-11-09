"""Extract the hash-verified Chrome ZIP, preserving ordinary Unix modes."""
import argparse
from pathlib import Path, PurePosixPath
import shutil
import stat
import zipfile


def entry(info, destination):
    path = PurePosixPath(info.filename)
    if (path.is_absolute() or not path.parts or path.parts[0] != "chrome-linux64"
            or ".." in path.parts or "\\" in info.filename):
        raise ValueError(f"Unsafe Chrome ZIP path: {info.filename}")
    unix_mode = info.external_attr >> 16
    expected_kind = stat.S_IFDIR if info.is_dir() else stat.S_IFREG
    if stat.S_IFMT(unix_mode) not in (0, expected_kind):
        raise ValueError(f"Unsupported Chrome ZIP member type: {info.filename}")
    target = destination.joinpath(*path.parts)
    for ancestor in (target, *target.parents):
        if ancestor == destination:
            break
        if ancestor.is_symlink():
            raise ValueError(f"Chrome ZIP target traverses a symlink: {info.filename}")
    # Preserve only ordinary permission bits; setuid, setgid and sticky are
    # deliberately excluded. Non-Unix archives receive ordinary safe defaults.
    mode = unix_mode & 0o777 if info.create_system == 3 else (0o755 if info.is_dir() else 0o644)
    return target, mode


def extract(archive_path, destination):
    destination = Path(destination).resolve()
    with zipfile.ZipFile(archive_path) as archive:
        planned = [(info, *entry(info, destination)) for info in archive.infolist()]
        targets = [target for _info, target, _mode in planned]
        if len(targets) != len(set(targets)):
            raise ValueError("Chrome ZIP contains duplicate member paths")
        destination.mkdir(parents=True, exist_ok=True)
        directories = []
        for info, target, mode in planned:
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                directories.append((target, mode))
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
                target.chmod(mode)
        # Restore directory permissions after writing children, including when
        # the archive declares a directory that is not owner-writable.
        for target, mode in sorted(directories, key=lambda item: len(item[0].parts), reverse=True):
            target.chmod(mode)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    extract(args.archive, args.destination)
