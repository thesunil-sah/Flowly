---
description: Run the code or test suite and analyze any failures in detail
argument-hint: [file, test pattern, or command — optional]
allowed-tools: Read, Grep, Glob, Bash
---

Run the code/tests and analyze any failures. Target: $ARGUMENTS

If no target was given above, detect and run the project's default
test suite for the whole project.

Work through these steps IN ORDER.

## Step 1 — Detect how to run
- Identify the language, runtime, and test framework
  (Jest, pytest, go test, cargo test, etc.).
- Look for config/manifest files (package.json, pyproject.toml,
  Makefile, etc.) to find the correct run command.
- State the exact command you are about to run before running it.

## Step 2 — Run it
- Execute the code and/or the tests.
- Paste the relevant output (summary line, and full output for
  anything that failed).
- Report the totals: how many passed, failed, skipped.

## Step 3 — Analyze each failure
For every failure, give:
- The test or line that failed and the exact error/assertion message.
- The root cause — what is actually going wrong, not just the symptom.
  Read the relevant source code to confirm.
- Whether the bug is in the code under test or in the test itself.

## Step 4 — Propose the fix
For each failure:
- Describe the specific fix (file and line).
- Note any side effects or other tests the fix might affect.
- Do NOT edit files — only propose. (Add Edit to allowed-tools if you
  want it to apply fixes automatically.)

## Final summary
- Overall status: ALL PASSING or FAILURES REMAIN.
- Ordered list of failures from most to least critical.
- The single most likely root cause if multiple failures share one.