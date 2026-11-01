"""Create a reviewed, deterministic public-source ZIP; never publish or overwrite."""

import argparse
import json
import sys
import zipfile
from hashlib import sha256
from pathlib import Path

if __package__:
    from .check_docs import collect, validate
else:
    from check_docs import collect, validate


def prepare(root: Path, destination: Path) -> dict:
    contents = collect(root)
    validation = validate(root, contents)
    destination = destination.absolute()
    if destination.suffix.lower() != ".zip":
        raise ValueError("public source output must use a .zip filename")
    checksum = destination.with_name(destination.name + ".sha256")
    if (
        destination.exists()
        or destination.is_symlink()
        or checksum.exists()
        or checksum.is_symlink()
    ):
        raise ValueError("output or checksum already exists; choose a new filename")
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "files": {p.as_posix(): sha256(raw).hexdigest() for p, raw in contents.items()},
    }
    payloads = {
        **{p.as_posix(): raw for p, raw in contents.items()},
        "SOURCE-MANIFEST.json": (json.dumps(manifest, indent=2) + "\n").encode(),
    }
    created = False
    try:
        with destination.open("xb") as stream:
            created = True
            with zipfile.ZipFile(stream, "w") as archive:
                for name, raw in sorted(payloads.items()):
                    entry = zipfile.ZipInfo("agentlean-source/" + name, (1980, 1, 1, 0, 0, 0))
                    entry.create_system = 3
                    entry.external_attr = 0o100644 << 16
                    entry.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(entry, raw)
        digest = sha256(destination.read_bytes()).hexdigest()
        with checksum.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(f"{digest}  {destination.name}\n")
    except BaseException:
        if created:
            destination.unlink(missing_ok=True)
        raise
    return {"archive": str(destination), "sha256": digest, **validation}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path)
    mode.add_argument("--list", action="store_true", help="print reviewed public paths for staging")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        if args.list:
            contents = collect(root)
            validate(root, contents)
            print("\n".join(path.as_posix() for path in contents))
        else:
            print(json.dumps(prepare(root, args.output), indent=2))
    except (ValueError, OSError, UnicodeError) as exc:
        print(f"source preparation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
