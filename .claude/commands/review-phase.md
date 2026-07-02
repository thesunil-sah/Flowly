---
description: Review the current file or phase — run it, checklist it, hunt for failures, and plan what to build next
argument-hint: [file-path or phase-name — optional]
allowed-tools: Read, Grep, Glob, Bash
---

You are doing a thorough engineering review. The target is: $ARGUMENTS

If no target was given above, review the current work in progress by
inspecting recent changes:
!`git status`
!`git diff HEAD`

Work through the following steps IN ORDER. Do not skip any. Show your
findings for each step before moving to the next.

## Step 1 — Understand the scope
- Identify what file(s) or phase you are reviewing.
- Read the relevant code fully (use Read/Grep/Glob).
- In 2–3 sentences, summarize what this code/phase is supposed to do.

## Step 2 — Run the code
- Detect the language, runtime, and test framework.
- Run the code and/or its tests (e.g. `npm test`, `pytest`, `go run`, etc.).
- Report exactly what passed, what failed, and paste the key output.
- If it can't be run, say why and what's missing to run it.

## Step 3 — Checklist review
Evaluate against each item. Mark ✅ pass / ⚠️ concern / ❌ fail, with
specific line numbers:
1. Correctness — logic errors, edge cases, off-by-one, null/empty handling
2. Readability — naming, function size, nesting, dead code
3. Security — injection, unsafe input, exposed secrets, unsafe deps
4. Performance — redundant work, N+1, unnecessary allocations
5. Error handling — failures caught and surfaced clearly
6. Tests — coverage gaps, missing edge cases
7. Documentation — non-obvious logic explained

## Step 4 — Failure hunt
- List every way this could realistically break in production.
- Include: bad/malformed input, race conditions, network/IO failure,
  empty states, boundary values, and unhandled exceptions.
- For each, note how likely it is and how to guard against it.

## Step 5 — What's next
- State clearly whether this phase is DONE or NEEDS-WORK.
- List the concrete next things to build to move forward, in order.
- Flag anything currently blocking progress.

## Final summary
Give a prioritized action list:
🔴 Must fix now   🟡 Should fix soon   🟢 Nice to have
Then one line: is it safe to build on top of this yet? (yes/no + why)