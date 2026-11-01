"""Inspect candidate archives, rebuild the sdist, and write SHA256SUMS."""

import argparse
import hashlib
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path


def check(directory: Path, rebuild: Path | None = None):
    wheels = list(directory.glob("*.whl"))
    sources = list(directory.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1:
        raise ValueError(
            "expected exactly one wheel and one source archive in a clean candidate directory"
        )
    forbidden = (
        ".verification",
        ".release-check",
        "codex-engineering",
        "__pycache__",
        ".pyc",
        "trials.jsonl",
        "agent-handoff.md",
    )
    for archive in [*wheels, *sources]:
        if archive.suffix == ".whl":
            with zipfile.ZipFile(archive) as stream:
                names = stream.namelist()
            if (
                "agentlean/templates/SKILL.md" not in names
                or "agentlean/templates/AGENTS.md" not in names
            ):
                raise ValueError("wheel is missing workflow templates")
        else:
            with tarfile.open(archive) as stream:
                names = stream.getnames()
        if any(fragment in name for name in names for fragment in forbidden):
            raise ValueError(f"unexpected private or generated content in {archive}")
        print(f"Archive contents checked: {archive.name} ({len(names)} entries)")
    sums = "".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
        for path in sorted([*wheels, *sources])
    )
    (directory / "SHA256SUMS").write_text(sums, encoding="utf-8", newline="\n")
    if rebuild is not None:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-cache-dir",
                "--no-index",
                "--no-deps",
                "--no-build-isolation",
                "--wheel-dir",
                str(rebuild),
                str(sources[0]),
            ],
            check=True,
            timeout=120,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument(
        "--rebuild",
        type=Path,
        help="rebuild the sdist into this directory (build dependencies must be installed)",
    )
    args = parser.parse_args()
    check(args.directory, args.rebuild)
