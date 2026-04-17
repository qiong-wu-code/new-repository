#!/usr/bin/env python3
"""
CLI template for skill-callable scripts.

Copy this file and fill in the TODO sections. Keep the scaffolding (argparse,
emit(), exit codes, stderr logging) intact — it's what makes the script safe
for LLM/skill orchestration.

Design principles:
  - stdout: JSON only (machine-readable)
  - stderr: logs for humans
  - exit codes: 0=ok, 2=user error, 3=runtime error, 4=partial success
  - --dry-run always available
  - required args never have defaults
  - single emit() exit path for consistency
"""
import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# ============================================================
# Exit codes
# ============================================================
EXIT_OK = 0
EXIT_USER_ERROR = 2      # bad args, missing paths — user can fix
EXIT_RUNTIME_ERROR = 3   # unexpected exception — check stderr
EXIT_PARTIAL = 4         # some items failed, some succeeded

# ============================================================
# Logging: stderr only, never pollutes stdout
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    stream=sys.stderr,
)
log = logging.getLogger(__name__)


# ============================================================
# Argument parsing
# ============================================================
def parse_args():
    p = argparse.ArgumentParser(
        prog='TODO_script_name',
        description='TODO one-line description of what this script does.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  %(prog)s --input-dir ./data --output-file result.json

  # Dry run (no side effects)
  %(prog)s --input-dir ./data --output-file result.json --dry-run

  # Process subset only
  %(prog)s --input-dir ./data --output-file result.json --only item1,item2

Exit codes:
  0 = all ok
  2 = user error (bad args, path not found)
  3 = runtime error (unexpected exception, see stderr)
  4 = partial success (some items failed)
""",
    )

    # ---- Required args (no defaults, LLM must pass explicitly) ----
    # TODO: replace with your actual required args
    p.add_argument('--input-dir', required=True,
                   metavar='DIR', type=Path,
                   help='Input directory to process.')

    # ---- Optional args with explicit defaults ----
    p.add_argument('--output-file', default='output.json',
                   metavar='PATH', type=Path,
                   help='Output file path (default: %(default)s)')
    p.add_argument('--only', default=None,
                   metavar='IDS',
                   help='Comma-separated IDs to process (default: all)')

    # ---- Flags ----
    p.add_argument('--dry-run', action='store_true',
                   help='Show planned actions without executing side effects.')
    p.add_argument('--force', action='store_true',
                   help='Overwrite existing output without prompt.')
    p.add_argument('-v', '--verbose', action='store_true',
                   help='Verbose logging to stderr.')

    return p.parse_args()


# ============================================================
# Validation
# ============================================================
def validate_args(args) -> list[str]:
    """Return list of error messages. Empty list = all valid."""
    errors = []

    if not args.input_dir.is_dir():
        errors.append(f"--input-dir does not exist or is not a directory: {args.input_dir}")

    if args.only is not None and not args.only.strip():
        errors.append("--only cannot be empty string; omit the flag instead")

    # TODO: add more validations as needed

    return errors


# ============================================================
# Unified exit: stdout is ALWAYS JSON
# ============================================================
def emit(payload: dict, exit_code: int = EXIT_OK):
    """Print JSON to stdout and exit. The only normal exit path."""
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.exit(exit_code)


# ============================================================
# Business logic — TODO: replace with your actual work
# ============================================================
def discover_items(input_dir: Path, only_ids: set[str] | None = None) -> list[dict]:
    """Discover items to process. Returns list of dicts."""
    items = []
    for entry in sorted(input_dir.iterdir()):
        if not entry.is_dir():
            continue
        item_id = entry.name  # TODO: extract real ID
        if only_ids and item_id not in only_ids:
            continue
        items.append({'id': item_id, 'path': entry})
    return items


def process_one(item: dict, dry_run: bool = False) -> dict:
    """Process a single item. Return {'status': 'ok'|'failed'|..., ...}."""
    if dry_run:
        return {'status': 'would_process'}

    # TODO: your actual logic here
    # Return a dict with at minimum a 'status' field.
    return {'status': 'ok'}


# ============================================================
# Main
# ============================================================
def main():
    args = parse_args()

    if args.verbose:
        log.setLevel(logging.DEBUG)

    # 1. Validate args
    errors = validate_args(args)
    if errors:
        emit({
            'status': 'error',
            'error_kind': 'invalid_args',
            'errors': errors,
        }, EXIT_USER_ERROR)

    # 2. Discover work
    only_ids = set(args.only.split(',')) if args.only else None
    try:
        items = discover_items(args.input_dir, only_ids)
    except Exception as e:
        log.exception("Discovery failed")
        emit({
            'status': 'error',
            'error_kind': 'discovery_failed',
            'message': str(e),
        }, EXIT_RUNTIME_ERROR)

    if not items:
        emit({
            'status': 'error',
            'error_kind': 'no_items_found',
            'input_dir': str(args.input_dir),
            'only_filter': args.only,
        }, EXIT_USER_ERROR)

    log.info(f"Discovered {len(items)} items")

    # 3. Dry-run: show plan and exit
    if args.dry_run:
        emit({
            'status': 'dry_run',
            'would_process': [{'id': it['id']} for it in items],
            'total': len(items),
            'output_file': str(args.output_file),
        }, EXIT_OK)

    # 4. Execute
    summary = {'ok': 0, 'failed': 0, 'error': 0}
    per_item = []
    for it in items:
        try:
            r = process_one(it)
            summary[r['status']] = summary.get(r['status'], 0) + 1
            per_item.append({'id': it['id'], 'status': r['status']})
            log.debug(f"{it['id']}: {r['status']}")
        except Exception as e:
            log.exception(f"Processing failed for {it['id']}")
            summary['error'] += 1
            per_item.append({'id': it['id'], 'status': 'error', 'message': str(e)})

    # 5. Emit summary
    exit_code = EXIT_PARTIAL if summary['error'] > 0 or summary.get('failed', 0) > 0 else EXIT_OK
    emit({
        'status': 'ok' if exit_code == EXIT_OK else 'partial',
        'total': len(items),
        'summary': summary,
        'items': per_item,
        'output_file': str(args.output_file),
        'timestamp': datetime.now().isoformat(),
    }, exit_code)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        log.warning("Interrupted by user")
        sys.exit(130)
    except SystemExit:
        raise  # emit() uses SystemExit, don't swallow it
    except Exception as e:
        log.exception("Unhandled exception")
        emit({
            'status': 'error',
            'error_kind': 'unhandled_exception',
            'message': str(e),
        }, EXIT_RUNTIME_ERROR)
