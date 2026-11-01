"""Preview-first managed installs, conflict detection and reversible removal."""

import base64
import json
from hashlib import sha256
from importlib.resources import files
from pathlib import Path

from . import __version__
from .storage import atomic_write, file_lock, strict_json

DESTINATIONS = {
    "codex": ".agents/skills/agentlean/SKILL.md",
    "claude": ".claude/skills/agentlean/SKILL.md",
    "generic": ".agentlean/workflow.md",
}


def _safe_path(root: Path, relative: str) -> Path:
    path = root / relative
    if not path.resolve().is_relative_to(root) or path.is_symlink():
        raise ValueError(f"destination escapes target or is a symlink: {path}")
    return path


def _manifest(root: Path, agent: str):
    if agent not in DESTINATIONS:
        raise ValueError(f"unknown agent profile: {agent}")
    path = _safe_path(root, f".agentlean/install-{agent}.json")
    if not path.exists():
        return path, None
    data = strict_json(path.read_text(encoding="utf-8"))
    allowed = {DESTINATIONS[agent], "CLAUDE.md" if agent == "claude" else "AGENTS.md"}
    if (
        not isinstance(data, dict)
        or set(data) != {"schema_version", "version", "agent", "files"}
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
        or data["agent"] != agent
        or not isinstance(data["version"], str)
        or not isinstance(data["files"], dict)
        or not data["files"]
        or not set(data["files"]).issubset(allowed)
        or DESTINATIONS[agent] not in data["files"]
    ):
        raise ValueError(f"invalid installation manifest: {path}")
    for relative, digest in data["files"].items():
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
        ):
            raise ValueError(f"invalid file digest in manifest: {path}")
        asset = _safe_path(root, relative)
        if not asset.is_file() or sha256(asset.read_bytes()).hexdigest() != digest:
            raise ValueError(
                f"managed file modified or missing; preserve/restore your edits before proceeding: {asset}"
            )
    return path, data


def _commit(root: Path, changes: dict[Path, bytes | None]) -> None:
    """Persist recovery data before writes and rollback ordinary I/O failures."""
    originals = {path: path.read_bytes() if path.exists() else None for path in changes}
    journal = _safe_path(root, ".agentlean/install-transaction.json")

    def encode(content):
        return base64.b64encode(content).decode("ascii") if content is not None else None

    transaction = {
        p.relative_to(root).as_posix(): {"before": encode(originals[p]), "after": encode(value)}
        for p, value in changes.items()
    }
    atomic_write(journal, (json.dumps(transaction) + "\n").encode("utf-8"))
    changed = []
    try:
        for path, content in changes.items():
            if content is None:
                path.unlink()
            else:
                atomic_write(path, content)
            changed.append(path)
    except BaseException as exc:
        failures = []
        for path in reversed(changed):
            try:
                original = originals[path]
                if original is None:
                    path.unlink(missing_ok=True)
                else:
                    atomic_write(path, original)
            except OSError as error:
                failures.append(str(error))
        if failures:
            raise OSError(
                f"installation failed and rollback needs manual repair: {failures}"
            ) from exc
        journal.unlink()
        raise
    journal.unlink()


def recover(target: Path, apply: bool = False) -> list[str]:
    """Restore a journaled interrupted operation without discarding later edits."""
    root = target.resolve(strict=True)
    if apply:
        with file_lock(_safe_path(root, ".agentlean/install.lock")):
            return _recover(root, True)
    return _recover(root, False)


def _recover(root: Path, apply: bool):
    journal = _safe_path(root, ".agentlean/install-transaction.json")
    if not journal.is_file():
        raise ValueError("no interrupted installation transaction found")
    data = strict_json(journal.read_text(encoding="utf-8"))
    allowed = (
        set(DESTINATIONS.values())
        | {"AGENTS.md", "CLAUDE.md"}
        | {f".agentlean/install-{agent}.json" for agent in DESTINATIONS}
    )
    if not isinstance(data, dict) or not data or not set(data).issubset(allowed):
        raise ValueError("invalid recovery journal")
    changes = {}
    for relative, states in data.items():
        if not isinstance(states, dict) or set(states) != {"before", "after"}:
            raise ValueError("invalid recovery states")
        decoded = {}
        for key, value in states.items():
            if value is not None and not isinstance(value, str):
                raise ValueError("invalid recovery content")
            decoded[key] = base64.b64decode(value, validate=True) if value is not None else None
        path = _safe_path(root, relative)
        current = path.read_bytes() if path.exists() else None
        if current not in (decoded["before"], decoded["after"]):
            raise ValueError(
                f"file changed since interrupted operation; preserve edits before recovery: {path}"
            )
        changes[path] = decoded["before"]
    if apply:
        for path, content in changes.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write(path, content)
        journal.unlink()
    return [
        f"{'RESTORE' if apply else 'WOULD RESTORE'} {p.relative_to(root).as_posix()}"
        for p in changes
    ]


def _operate(root: Path, agent: str, apply: bool, upgrade: bool, remove: bool):
    if _safe_path(root, ".agentlean/install-transaction.json").exists():
        raise ValueError(
            "interrupted installation found; preview agentlean recover TARGET, then use --apply"
        )
    manifest, previous = _manifest(root, agent)
    if remove:
        if previous is None:
            raise ValueError("no managed installation found; unowned files will not be removed")
        changes = {_safe_path(root, relative): None for relative in previous["files"]}
        changes[manifest] = None
        messages = [
            f"{'REMOVE' if apply else 'WOULD REMOVE'} {p.relative_to(root).as_posix()}"
            for p in changes
        ]
    else:
        name = "CLAUDE.md" if agent == "claude" else "AGENTS.md"
        candidates = {DESTINATIONS[agent]: "SKILL.md", name: "AGENTS.md"}
        contents = {}
        messages = []
        for relative, template in candidates.items():
            path = _safe_path(root, relative)
            if previous is not None and relative not in previous["files"]:
                messages.append(f"KEEP {relative}: not managed by AgentLean")
                continue
            if previous is None and path.exists():
                if relative == name:
                    messages.append(
                        f"KEEP {relative}: merge the packaged instruction fragment manually if useful"
                    )
                    continue
                raise ValueError(
                    f"destination already exists and is unowned; nothing overwritten: {path}"
                )
            contents[path] = files("agentlean").joinpath("templates", template).read_bytes()
        if previous is not None:
            changed = any(path.read_bytes() != content for path, content in contents.items())
            if changed and not upgrade:
                raise ValueError(
                    "installed workflow differs from this release; preview with init --upgrade"
                )
            if not changed and previous["version"] == __version__:
                return messages + [f"UNCHANGED {agent}: AgentLean {__version__} already installed"]
        changes = {
            path: content
            for path, content in contents.items()
            if not path.exists() or path.read_bytes() != content
        }
        for path in changes:
            action = "UPDATE" if path.exists() else "CREATE"
            messages.append(
                f"{action if apply else 'WOULD ' + action} {path.relative_to(root).as_posix()}"
            )
        data = {
            "schema_version": 1,
            "version": __version__,
            "agent": agent,
            "files": {
                p.relative_to(root).as_posix(): sha256(content).hexdigest()
                for p, content in contents.items()
            },
        }
        changes[manifest] = (json.dumps(data, indent=2) + "\n").encode("utf-8")
        messages.append(
            f"{'WRITE' if apply else 'WOULD WRITE'} {manifest.relative_to(root).as_posix()}"
        )
    if apply:
        _commit(root, changes)
    return messages


def install(
    target: Path, agent: str, apply: bool = False, upgrade: bool = False, remove: bool = False
) -> list[str]:
    if agent not in DESTINATIONS:
        raise ValueError(f"unknown agent profile: {agent}")
    root = target.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("target must be an existing repository directory")
    if apply:
        lock = _safe_path(root, ".agentlean/install.lock")
        with file_lock(lock):
            return _operate(root, agent, apply, upgrade, remove)
    return _operate(root, agent, apply, upgrade, remove)
