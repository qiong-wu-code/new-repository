#!/usr/bin/env python3
"""
Extract error traceback from a model's Converter_result/convert/.log/ directory.

Single-responsibility: just extract errors.
Does NOT scan models, does NOT parse SNR, does NOT write reports.

Usage:
  extract_errors.py --converter-result-dir /path/to/model/Converter_result
"""
import argparse
import json
import logging
import re
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_USER_ERROR = 2
EXIT_RUNTIME_ERROR = 3

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s', stream=sys.stderr)
log = logging.getLogger(__name__)

# Priority-ordered error patterns
ERROR_PATTERNS = [
    (re.compile(r'Traceback \(most recent call last\):[\s\S]*?(?=\n\S|\n\n|\Z)', re.M),
     'python_traceback'),
    (re.compile(r'(?:FATAL|CRITICAL)[:\s].+', re.I), 'fatal'),
    (re.compile(r'Segmentation fault[^\n]*', re.I), 'segfault'),
    (re.compile(r'ERROR[:\s].+', re.I), 'error_line'),
]


def parse_args():
    p = argparse.ArgumentParser(
        prog='extract_errors',
        description='Extract error traceback from Converter_result logs.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --converter-result-dir /path/to/m001_xxx/Converter_result

Exit codes:
  0 = ran successfully (status in JSON indicates whether errors were found)
  2 = bad arguments
  3 = unexpected runtime error
""",
    )
    p.add_argument('--converter-result-dir', required=True, type=Path, metavar='DIR',
                   help='Path to Converter_result/ directory')
    p.add_argument('--max-chars', type=int, default=500, metavar='N',
                   help='Max chars of error snippet (default: %(default)s)')
    p.add_argument('--tail-mb', type=int, default=10, metavar='MB',
                   help='Read only last N MB of log (default: %(default)s)')
    p.add_argument('-v', '--verbose', action='store_true')
    return p.parse_args()


def emit(payload: dict, exit_code: int = EXIT_OK):
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.exit(exit_code)


def find_log_file(converter_result_dir: Path) -> Path | None:
    """Find the most recent log file under convert/.log/"""
    log_dir = converter_result_dir / 'convert' / '.log'
    if not log_dir.is_dir():
        return None
    logs = [f for f in log_dir.iterdir() if f.is_file()]
    if not logs:
        return None
    logs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return logs[0]


def extract_from_log(log_path: Path, max_chars: int, tail_mb: int) -> dict:
    """Extract error snippet from the end of the log file."""
    try:
        size = log_path.stat().st_size
        read_bytes = min(size, tail_mb * 1024 * 1024)
        with log_path.open('rb') as f:
            f.seek(size - read_bytes)
            text = f.read().decode('utf-8', errors='replace')
    except Exception as e:
        return {'status': 'read_error', 'error': str(e), 'log_file': str(log_path)}

    for pattern, kind in ERROR_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            snippet = matches[-1][:max_chars]  # last match = closest to crash
            return {
                'status': 'found',
                'kind': kind,
                'snippet': snippet,
                'log_file': str(log_path),
            }

    return {
        'status': 'no_error_pattern',
        'log_file': str(log_path),
        'note': 'log exists but no known error pattern matched',
    }


def main():
    args = parse_args()
    if args.verbose:
        log.setLevel(logging.DEBUG)

    cr = args.converter_result_dir
    if not cr.is_dir():
        emit({'status': 'error', 'error_kind': 'invalid_args',
              'errors': [f'--converter-result-dir does not exist: {cr}']},
             EXIT_USER_ERROR)

    log_file = find_log_file(cr)
    if log_file is None:
        emit({'status': 'no_log', 'converter_result_dir': str(cr)}, EXIT_OK)

    result = extract_from_log(log_file, args.max_chars, args.tail_mb)
    emit(result, EXIT_OK)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except SystemExit:
        raise
    except Exception as e:
        log.exception('Unhandled exception')
        emit({'status': 'error', 'error_kind': 'unhandled_exception', 'message': str(e)},
             EXIT_RUNTIME_ERROR)
