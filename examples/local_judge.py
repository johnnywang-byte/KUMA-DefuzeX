"""Judge a two-step local Case from file-change Evidence; see local_judge.md."""

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Any

from kuma import create_run
from kuma.providers import CaseGenerationContext, JudgeContext

TODO_PATH = "notes/todo.md"
TASKS = (
    f"Create {TODO_PATH} with two unchecked tasks.",
    f"Mark the first task in {TODO_PATH} as done.",
)
# The public Case carries only TASKS; the expected outcome stays in the Judge.
EXPECTED_CHANGES = ("created", "modified")


class LocalCase:
    """Supply the public two-step Case without an Agent Profile or network."""

    agent_profile_required = False

    def generate_case(self, _context: CaseGenerationContext) -> dict[str, object]:
        """Return one text Input per task, in execution order."""
        return {
            "case_id": "case_local_judge_demo",
            "input_type": "text",
            "inputs": [
                {
                    "input_id": f"input_local_judge_{index}",
                    "payload_type": "text",
                    "payload": task,
                }
                for index, task in enumerate(TASKS, start=1)
            ],
        }


def call_your_agent(
    test_input: str, repo: Path, *, skip_edit: bool = False
) -> dict[str, str]:
    """Replace this deterministic body with your Agent, which edits ``repo``."""
    todo = repo / TODO_PATH
    if test_input == TASKS[0]:
        todo.parent.mkdir(exist_ok=True)
        todo.write_text("- [ ] Draft notes\n- [ ] Share notes\n", encoding="utf-8")
    elif not skip_edit:
        todo.write_text("- [x] Draft notes\n- [ ] Share notes\n", encoding="utf-8")
    # --fail-demo still reports success, so only file Evidence reveals the gap.
    return {"message": "Done", "task": test_input}


def _same_path(change_path: str, relative: str) -> bool:
    """Compare trailing components so the rule ignores the repository location."""
    expected = PurePosixPath(relative).parts
    return PurePosixPath(change_path).parts[-len(expected) :] == expected


def local_judge(context: JudgeContext) -> dict[str, Any]:
    """Check every committed step against its expected file change."""
    issues: list[dict[str, object]] = []
    gaps: list[dict[str, object]] = []
    if len(context.history) != len(EXPECTED_CHANGES):
        gaps.append({"code": "steps_missing", "message": "Not every step ran."})
    for item, expected in zip(context.history, EXPECTED_CHANGES, strict=False):
        step = item.test_input.index
        submission = item.submission
        evidence = submission.file_evidence
        if submission.status != "completed":
            issues.append(
                {
                    "code": "step_not_completed",
                    "step": step,
                    "message": f"Step {step} ended as {submission.status}.",
                }
            )
        elif evidence is None or not evidence.complete:
            gaps.append(
                {
                    "code": "file_evidence_incomplete",
                    "step": step,
                    "message": f"File changes for step {step} were not fully captured.",
                }
            )
        elif not any(
            change.change_type == expected and _same_path(change.path, TODO_PATH)
            for change in evidence.changes
        ):
            issues.append(
                {
                    "code": "expected_change_missing",
                    "step": step,
                    "message": f"Step {step} reported success but {TODO_PATH} "
                    f"was not {expected}.",
                }
            )
    # A confirmed issue is a conclusion; missing Evidence elsewhere cannot hide it.
    status = "issue" if issues else "insufficient_evidence" if gaps else "pass"
    return {
        "report_id": "report_local_judge_demo",
        "status": status,
        "confidence": 1.0,
        "stop_reason": "deterministic_file_rule",
        "issues": issues,
        "evidence_gaps": gaps,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fail-demo",
        action="store_true",
        help="Skip the second file edit to show an issue report.",
    )
    args = parser.parse_args(argv)

    with TemporaryDirectory(prefix="kuma-local-judge-") as temporary:
        repo = Path(temporary)
        (repo / "README.md").write_text(
            "# Temporary example repository\n", encoding="utf-8"
        )
        run = create_run(
            repo_path=repo,
            case_provider=LocalCase(),
            judge_provider=local_judge,
            max_steps=len(TASKS),
            allow_local=True,
            track_files=True,
        )
        try:
            report = None
            while (test_input := run.get_input()) is not None:
                try:
                    output = call_your_agent(test_input, repo, skip_edit=args.fail_demo)
                except Exception:
                    # Do not submit raw exception text, which can contain secrets.
                    report = run.submit(status="failed", error="Agent failed")
                else:
                    # The final submit() runs the Judge and returns its TestReport.
                    report = run.submit(output)

            for item in run.history:
                submission = item.submission
                evidence = submission.file_evidence
                changes = "unavailable" if evidence is None else len(evidence.changes)
                print(
                    f"step={item.test_input.index} "
                    f"submission={submission.status} file_changes={changes}"
                )
            print(f"state={run.state}")
            print(f"report_status={report.status}")
            for issue in (*report.issues, *report.evidence_gaps):
                print(f"finding={issue['code']} step={issue.get('step', '-')}")
            return 0 if report.status == "pass" else 1
        finally:
            # Release an unfinished Run on interruption or invalid Agent output.
            if run.state in {"ready", "input_delivered"}:
                run.cancel()


if __name__ == "__main__":
    raise SystemExit(main())
