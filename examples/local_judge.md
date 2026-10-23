# Local Case and Judge from file Evidence

This example runs the fully local Provider combination: a custom Case Provider
delivers two steps, a deterministic Agent edits a temporary repository, and a
custom Judge Provider decides the result from each step's file-change Evidence.
No API key, model client, Docker, network, or hosted Case or Judge is used, so it
costs nothing. Temporary files are removed when the example exits.

From the repository root, install this checkout in an isolated Python environment:

```bash
python -m venv .venv
```

Activate `.venv` before the install and run commands: `source .venv/bin/activate`
on macOS/Linux, or `.venv\Scripts\Activate.ps1` in Windows PowerShell.

Then run:

```bash
python -m pip install .
python examples/local_judge.py
```

Expected output:

```text
step=0 submission=completed file_changes=2
step=1 submission=completed file_changes=1
state=report_ready
report_status=pass
```

Step indexes are zero-based. Step 0 records two changes: the created `notes`
directory and `notes/todo.md`. The example exits with status 0 only for `pass`.

To see the Judge catch an Agent that reports success without doing the work:

```bash
python examples/local_judge.py --fail-demo
```

```text
step=0 submission=completed file_changes=2
step=1 submission=completed file_changes=0
state=report_ready
report_status=issue
finding=expected_change_missing step=1
```

The second step still returns `{"message": "Done", ...}`, but its Evidence shows
no file change, so the Judge reports an `issue` and the example exits with status 1.

## How the pieces fit

- `LocalCase.generate_case()` returns only the public tasks. The expected file
  changes live in the Judge, as a private rubric would.
- `run.get_input()` returns the next task until it returns `None`; each
  `run.submit()` commits one step. With a Judge configured, the final `submit()`
  runs it and returns the `TestReport`.
- `track_files=True` (the default) records hashes, sizes, and change types for
  each step. File text is not captured unless you also set `upload_diff=True`.
- `local_judge(context)` receives the committed `context.history`. It returns
  `issue` for a failed step or missing change, `insufficient_evidence` when file
  capture was incomplete and no issue was confirmed, and otherwise `pass`. It
  never guesses a result from missing Evidence.

## Connect your Agent

Replace only the body of `call_your_agent(test_input, repo)` in
[local_judge.py](local_judge.py) and return the Agent's actual finite
JSON-compatible result. Point `repo_path` at the repository your Agent works in,
then adapt `TASKS`, `EXPECTED_CHANGES`, and `local_judge()` to your own checks.

Agent exceptions are submitted as `failed` without the raw exception text, and the
Judge reports them as `step_not_completed`. An unfinished Run is cancelled on
interruption or invalid output to release local resources.

A real Agent may make paid model calls even though this Case and Judge are local.
For the official hosted Judge, omit `judge_provider` and follow the
[SDK guide](../docs/sdk-guide.md). Hosted evaluation requires an API key and may
consume credits.

Offline regression checks (from the repository root):

```bash
python tools/verify_local_judge.py
```
