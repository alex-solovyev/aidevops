"""Disposable Git integration; intentionally outside the portable OS validator."""

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from worker_lifecycle.admission import AdmissionClosed, AdmissionRegistry
from worker_lifecycle.enrollment import GenerationEnrollment, MARKER, _git_directory
from worker_lifecycle.storage import LifecycleRegistry, StoreConflict


class EnrollmentContract(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="generation-enrollment-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.repo = self.root / "repo"
        self.tree = self.root / "tree"
        self.git("init", "-q", str(self.repo))
        self.git("-C", str(self.repo), "commit", "-q", "--allow-empty", "-m", "fixture")
        self.git("-C", str(self.repo), "worktree", "add", "-q", "--detach", str(self.tree))
        self.store = LifecycleRegistry.initialize(self.root / "state")
        self.enrollment = GenerationEnrollment(self.store)
        self.marker = _git_directory(self.tree) / MARKER

    def git(self, *args):
        return subprocess.run(
            ["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
             "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", *args],
            check=True, capture_output=True, timeout=15,
        )

    def test_replay_and_lookup_preserve_generation_without_new_events(self):
        generation = self.enrollment.resolve(self.tree, create=True)
        before = self.store.summary()
        self.assertEqual(self.enrollment.resolve(self.tree, create=True), generation)
        self.assertEqual(self.enrollment.resolve(self.tree), generation)
        self.assertEqual(self.store.summary(), before)
        self.assertEqual(self.git("-C", str(self.tree), "status", "--porcelain").stdout, b"")

    def test_interruption_between_marker_and_transaction_is_recoverable(self):
        with patch.object(AdmissionRegistry, "open_generation", side_effect=OSError("interrupted")):
            with self.assertRaises(OSError):
                self.enrollment.resolve(self.tree, create=True)
        before = self.marker.read_bytes()
        with self.assertRaises(AdmissionClosed):
            self.enrollment.resolve(self.tree)
        generation = self.enrollment.resolve(self.tree, create=True)
        self.assertEqual(self.marker.read_bytes(), before)
        self.assertEqual(self.enrollment.resolve(self.tree), generation)

    def test_closed_admission_cannot_be_reopened(self):
        generation = self.enrollment.resolve(self.tree, create=True)
        AdmissionRegistry(self.store).close_generation(str(uuid4()), generation)
        before = self.store.summary()
        with self.assertRaises(AdmissionClosed):
            self.enrollment.resolve(self.tree, create=True)
        self.assertEqual(self.store.summary(), before)

    def test_replaced_directory_with_copied_git_pointer_is_rejected(self):
        self.enrollment.resolve(self.tree, create=True)
        pointer = (self.tree / ".git").read_bytes()
        self.tree.rename(self.root / "original")
        self.tree.mkdir()
        (self.tree / ".git").write_bytes(pointer)
        with self.assertRaises(StoreConflict):
            self.enrollment.resolve(self.tree, create=True)

    def test_other_installation_and_canonical_checkout_are_rejected(self):
        self.enrollment.resolve(self.tree, create=True)
        other = GenerationEnrollment(LifecycleRegistry.initialize(self.root / "other"))
        with self.assertRaises(StoreConflict):
            other.resolve(self.tree, create=True)
        with self.assertRaises(ValueError):
            self.enrollment.resolve(self.repo, create=True)

    def test_invalid_marker_is_preserved_not_replaced(self):
        self.marker.write_bytes(b"broken")
        self.marker.chmod(0o600)
        with self.assertRaises(ValueError):
            self.enrollment.resolve(self.tree, create=True)
        self.assertEqual(self.marker.read_bytes(), b"broken")

    def test_missing_marker_cannot_rebind_reserved_path(self):
        self.enrollment.resolve(self.tree, create=True)
        self.marker.unlink()
        with self.assertRaises(StoreConflict):
            self.enrollment.resolve(self.tree, create=True)
        self.assertFalse(self.marker.exists())

    def test_concurrent_creators_converge(self):
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(self.enrollment.resolve, self.tree, create=True) for _ in range(4)]
            self.assertEqual(len({future.result() for future in futures}), 1)

    def test_publication_link_left_by_crash_is_recoverable(self):
        with patch.object(AdmissionRegistry, "open_generation", side_effect=OSError("interrupted")):
            with self.assertRaises(OSError):
                self.enrollment.resolve(self.tree, create=True)
        os.link(self.marker, self.marker.parent / ".interrupted-publish.tmp")
        self.assertEqual(self.enrollment.resolve(self.tree, create=True), self.enrollment.resolve(self.tree))

    def launch(self, path):
        entry = Path(__file__).resolve().parents[1] / "worker-launch.py"
        return subprocess.run(
            [sys.executable, "-E", "-s", "-B", str(entry), "--initialize",
             "--state-dir", str(self.store.directory), "--worktree", str(path),
             "--", "touch", str(path / "executed")],
            cwd=path, capture_output=True, text=True, timeout=30,
        )

    def test_creation_hook_and_automatic_launch_share_generation(self):
        scripts = Path(__file__).resolve().parents[2] / "scripts"
        created = self.root / "created"
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(("AIDEVOPS_", "GIT_", "WORKTREE_"))}
        env.update(HOME=str(self.root), AIDEVOPS_LIFECYCLE_STATE_DIR=str(self.store.directory),
                   GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="core.hooksPath", GIT_CONFIG_VALUE_0="/dev/null")
        result = subprocess.run(
            ["bash", "-c", 'source "$1/shared-constants.sh" && source "$1/shared-worktree-create.sh" '
             '&& worktree_create_registered "$2" "$3" HEAD --detach',
             "fixture", str(scripts), str(self.repo), str(created)],
            cwd=self.root, env=env, capture_output=True, text=True, timeout=40,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        generation = self.enrollment.resolve(created)
        result = self.launch(created)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((created / "executed").exists())
        with self.store.connection() as connection:
            bindings = connection.execute("SELECT generation_id FROM bindings").fetchall()
            self.assertEqual([row[0] for row in bindings], [generation])

    def test_automatic_launch_cannot_bypass_closed_or_damaged_enrollment(self):
        generation = self.enrollment.resolve(self.tree, create=True)
        saved = self.marker.read_bytes()
        self.marker.write_bytes(b"invalid")
        result = self.launch(self.tree)
        self.assertEqual(result.returncode, 75, result.stderr)
        self.assertFalse((self.tree / "executed").exists())
        self.marker.write_bytes(saved)
        AdmissionRegistry(self.store).close_generation(str(uuid4()), generation)
        result = self.launch(self.tree)
        self.assertEqual(result.returncode, 75, result.stderr)
        self.assertFalse((self.tree / "executed").exists())


if __name__ == "__main__":
    unittest.main()
