"""Verify the local Case and Judge example offline, including failure paths."""

from __future__ import annotations

import importlib.util
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from kuma.errors import ValidationError

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "local_judge", ROOT / "examples/local_judge.py"
)
assert SPEC is not None and SPEC.loader is not None
EXAMPLE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXAMPLE)


def _run(argv: list[str]) -> tuple[int, list[str]]:
    output = io.StringIO()
    with redirect_stdout(output):
        code = EXAMPLE.main(argv)
    return code, output.getvalue().splitlines()


class LocalJudgeTests(unittest.TestCase):
    def test_pass(self) -> None:
        self.assertEqual(
            _run([]),
            (
                0,
                [
                    "step=0 submission=completed file_changes=2",
                    "step=1 submission=completed file_changes=1",
                    "state=report_ready",
                    "report_status=pass",
                ],
            ),
        )

    def test_claimed_success_without_change_is_an_issue(self) -> None:
        self.assertEqual(
            _run(["--fail-demo"]),
            (
                1,
                [
                    "step=0 submission=completed file_changes=2",
                    "step=1 submission=completed file_changes=0",
                    "state=report_ready",
                    "report_status=issue",
                    "finding=expected_change_missing step=1",
                ],
            ),
        )

    def test_agent_failure_is_reported_without_exception_text(self) -> None:
        with patch.object(
            EXAMPLE, "call_your_agent", side_effect=RuntimeError("secret-token")
        ):
            code, lines = _run([])
        self.assertEqual(code, 1)
        self.assertIn("step=1 submission=failed file_changes=0", lines)
        self.assertIn("finding=step_not_completed step=1", lines)
        self.assertNotIn("secret-token", "\n".join(lines))

    def test_missing_file_evidence_is_insufficient(self) -> None:
        create_run = EXAMPLE.create_run

        def without_tracking(**options):
            return create_run(**{**options, "track_files": False})

        with patch.object(EXAMPLE, "create_run", side_effect=without_tracking):
            code, lines = _run([])
        self.assertEqual(code, 1)
        self.assertIn("step=0 submission=completed file_changes=unavailable", lines)
        self.assertIn("report_status=insufficient_evidence", lines)
        self.assertIn("finding=file_evidence_incomplete step=0", lines)
        self.assertNotIn("report_status=pass", lines)

    def test_confirmed_issue_is_not_hidden_by_missing_evidence(self) -> None:
        create_run = EXAMPLE.create_run

        def without_tracking(**options):
            return create_run(**{**options, "track_files": False})

        # Step 0 fails (an issue); step 1 completes without file Evidence (a gap).
        with (
            patch.object(EXAMPLE, "create_run", side_effect=without_tracking),
            patch.object(
                EXAMPLE,
                "call_your_agent",
                side_effect=[RuntimeError(), {"message": "Done"}],
            ),
        ):
            code, lines = _run([])
        self.assertEqual(code, 1)
        self.assertIn("report_status=issue", lines)
        self.assertIn("finding=step_not_completed step=0", lines)
        self.assertIn("finding=file_evidence_incomplete step=1", lines)

    def test_invalid_output_releases_runtime(self) -> None:
        with (
            patch.object(EXAMPLE, "call_your_agent", return_value=None),
            self.assertRaises(ValidationError),
        ):
            EXAMPLE.main([])
        # A leaked active-Run lease would prevent the next Run from starting.
        self.test_pass()

    def test_interruption_releases_runtime(self) -> None:
        with (
            patch.object(EXAMPLE, "call_your_agent", side_effect=KeyboardInterrupt),
            self.assertRaises(KeyboardInterrupt),
        ):
            EXAMPLE.main([])
        self.test_pass()


if __name__ == "__main__":
    unittest.main()
