"""Validate public source documentation without fetching external links."""

import json
import re
import sys
from hashlib import sha256
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT_FILES = (
    "README.md",
    "LICENSE",
    "NOTICE.md",
    "MAINTAINERS.md",
    "GOVERNANCE.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "SUPPORT.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "AGENTS.md",
    "pyproject.toml",
    "MANIFEST.in",
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
)
TREES = {
    ".github": {".md", ".yml", ".yaml"},
    "agentlean": {".py", ".md"},
    "docs": {".md"},
    "examples": {".md", ".json"},
    "scripts": {".py", ".md"},
    "tests": {".py", ".md"},
}
EXCLUDED = {"docs/agent-handoff.md"}
REQUIRED = {"README.md", "LICENSE", "pyproject.toml", "agentlean/__init__.py", "agentlean/cli.py"}
PRIVATE_MARKERS = (
    re.compile(r"https?://chatgpt\.com/share/", re.I),
    re.compile(r"[A-Z]:[\\/]+Users[\\/]+[^\s\\/]+", re.I),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
)


def collect(root: Path) -> dict[Path, bytes]:
    root = root.resolve(strict=True)
    candidates = [root / name for name in ROOT_FILES if (root / name).exists()]
    for directory, suffixes in TREES.items():
        candidates.extend(
            path
            for path in (root / directory).rglob("*")
            if path.is_file() and path.suffix in suffixes and "__pycache__" not in path.parts
        )
    contents = {}
    for path in sorted(set(candidates)):
        relative = path.relative_to(root)
        if relative.as_posix() in EXCLUDED:
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError(f"public source must not include linked/external files: {relative}")
        contents[relative] = path.read_bytes()
    missing = REQUIRED - {path.as_posix() for path in contents}
    if missing:
        raise ValueError(f"required public source files missing: {sorted(missing)}")
    return contents


def _without_fences(text: str) -> str:
    return re.sub(r"```.*?```", "", text, flags=re.S)


def _anchors(text: str) -> set[str]:
    found, counts = set(), {}
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", _without_fences(text), flags=re.M):
        heading = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", heading)
        slug = re.sub(r"[^\w\s-]", "", heading.lower()).strip()
        slug = re.sub(r"\s", "-", slug)
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        found.add(slug + (f"-{count}" if count else ""))
    return found


def validate(root: Path, contents: dict[Path, bytes] | None = None) -> dict:
    root = root.resolve(strict=True)
    contents = collect(root) if contents is None else contents
    texts = {path: raw.decode("utf-8") for path, raw in contents.items()}
    errors, links = [], 0
    for path, text in texts.items():
        if any(pattern.search(text) for pattern in PRIVATE_MARKERS):
            errors.append(
                f"{path.as_posix()}: possible private context, personal path or credential marker"
            )
        if path.suffix != ".md":
            continue
        for destination in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", _without_fences(text)):
            destination = destination.strip().strip("<>")
            parts = urlsplit(destination)
            if parts.scheme or parts.netloc:
                continue
            links += 1
            absolute = (
                (root / path.parent / unquote(parts.path)).resolve() if parts.path else root / path
            )
            if not absolute.is_relative_to(root):
                errors.append(f"{path.as_posix()}: link escapes public source: {destination}")
                continue
            target = absolute.relative_to(root)
            if target not in contents and target / "README.md" in contents:
                target = target / "README.md"
            if target not in contents:
                errors.append(f"{path.as_posix()}: missing public link target: {destination}")
            elif (
                parts.fragment
                and target.suffix == ".md"
                and unquote(parts.fragment) not in _anchors(texts[target])
            ):
                errors.append(f"{path.as_posix()}: unknown heading: {destination}")
    examples = [
        path
        for path in contents
        if path.parent == Path("examples")
        and path.name.startswith("checks.")
        and path.suffix == ".json"
    ]
    if examples:
        sys.path.insert(0, str(root))
        from agentlean.quality import load_gates

        for path in examples:
            try:
                gates = load_gates(root / path)
                if gates.digest != sha256(contents[path]).hexdigest():
                    raise ValueError("example changed during validation")
            except (ValueError, OSError) as exc:
                errors.append(f"{path.as_posix()}: {exc}")
    if errors:
        raise ValueError("\n".join(errors))
    return {
        "public_files": len(contents),
        "local_links": links,
        "check_examples": len(examples),
        "external_links": "not fetched",
        "secret_scan": "obvious markers only; manual review still required",
    }


def main() -> int:
    try:
        print(json.dumps(validate(Path(__file__).resolve().parents[1]), indent=2))
    except (ValueError, OSError, UnicodeError) as exc:
        print(f"documentation check failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
