---
name: example-task
description: Example skill showing how to orchestrate a CLI-template-based script.
  Use this as a reference when writing skills that call scripts following the
  cli_template.py pattern.
---

# Example Task

## When to use

When the user asks to run `my_script.py` against a directory.

## Execution

**STRICT RULE: Do not write Python code. Only invoke existing scripts via shell.**

### Step 1: Confirm inputs

Ask user for:
- Input directory path
- Whether they want dry-run first (recommended for new datasets)

### Step 2: Dry-run

    python scripts/my_script.py \
      --input-dir <path> \
      --dry-run

Parse stdout as JSON. Show user the `would_process` list. Ask to proceed.

### Step 3: Execute

    python scripts/my_script.py \
      --input-dir <path>

### Step 4: Interpret exit code

Branch based on the exit code of Step 3:

| Exit code | Meaning | Action |
|-----------|---------|--------|
| 0 | All ok | Parse `summary` from stdout JSON, report counts to user |
| 2 | User error | Parse `errors` array, tell user exactly what to fix |
| 3 | Script crashed | Read last 20 lines of stderr, show user, suggest they report it |
| 4 | Partial success | Parse `items`, list the ones with `status != 'ok'` |

### Step 5: Report

Summarize in natural language:
- Total items processed
- Success / failure counts
- Output file location
- Any items needing attention

## Forbidden actions

- ❌ Writing Python to parse the output instead of using `json.loads`
- ❌ Passing different argument names than those in `--help`
- ❌ Retrying a failed run without first reading stderr
- ❌ Skipping the dry-run on first invocation against a new input
- ❌ Modifying the script itself to "fix" errors — report to user instead

## If things go wrong

If the script output is not valid JSON (shouldn't happen, but...):
1. Do not attempt to parse with regex
2. Show the user the raw stdout and last 30 lines of stderr
3. Suggest they run `python scripts/my_script.py --help` to check invocation

If `--help` itself fails:
- The script is broken. Do not try to fix it. Report to user.
