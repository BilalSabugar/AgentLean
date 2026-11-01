"""Public snapshots must not contain local artifacts or silently broken guides."""

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.check_docs import validate
from scripts.prepare_source import prepare


def project(root):
    (root / "README.md").write_text("# Project\n[Guide](docs/guide.md#setup)\n")
    (root / "LICENSE").write_text("MIT fixture")
    (root / "pyproject.toml").write_text('[project]\nname = "fixture"\n')
    (root / "agentlean").mkdir()
    (root / "agentlean/__init__.py").write_text('__version__ = "0.4.0"\n')
    (root / "agentlean/cli.py").write_text('"""Synthetic fixture."""\n')
    (root / "docs").mkdir()
    (root / "docs/guide.md").write_text("# Guide\n## Setup\n")


class PublicSourceTests(unittest.TestCase):
    def test_private_artifacts_are_excluded_and_export_is_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project(root)
            (root / ".env").write_text("private fixture")
            (root / "docs/agent-handoff.md").write_text("private development context")
            (root / ".agentlean").mkdir()
            (root / ".agentlean/trials.jsonl").write_text("private trial data")
            first, second = root / "first.zip", root / "second.zip"
            prepare(root, first)
            prepare(root, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                names = archive.namelist()
                self.assertIn("agentlean-source/README.md", names)
                self.assertFalse(
                    any("handoff" in name or "trials" in name or ".env" in name for name in names)
                )
                manifest = json.loads(archive.read("agentlean-source/SOURCE-MANIFEST.json"))
                self.assertIn("docs/guide.md", manifest["files"])
            original = first.read_bytes()
            with self.assertRaisesRegex(ValueError, "already exists"):
                prepare(root, first)
            self.assertEqual(first.read_bytes(), original)

    def test_missing_or_private_links_block_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project(root)
            for link in ("missing.md", "docs/guide.md#missing-heading", "docs/agent-handoff.md"):
                (root / "README.md").write_text(f"[Broken]({link})\n")
                with self.subTest(link=link), self.assertRaises(ValueError):
                    validate(root)

    def test_obvious_private_markers_and_escaping_links_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project(root)
            (root / "docs/guide.md").write_text("# Guide\n## Setup\n" + "sk-" + "a" * 30)
            with self.assertRaisesRegex(ValueError, "credential marker"):
                validate(root)
            (root / "docs/guide.md").write_text("# Guide\n## Setup\n")
            (root / "README.md").write_text("[Outside](../../private.md)\n")
            with self.assertRaisesRegex(ValueError, "escapes public source"):
                validate(root)
