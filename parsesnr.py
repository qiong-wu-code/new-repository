#!/usr/bin/env python3
"""
Parse a single org_vs_hw.txt file and output SNR info as JSON.

Expected format (one field per line):
  Model name: <model_id>_<model_name>.<ext>
  SDK version: x.y.z.w
  Data type: org_model:<type_a> VS hw:<type_b>
  SNR: <N.NNN>db                            (single-output)
  SNR: [N.NN, N.NN, -N.NN]db                (multi-output)

Usage:
  parse_snr.py --input-file /path/to/org_vs_hw.txt
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

SNR_DECIMALS = 2

# Strip trailing known model extensions from "Model name"
MODEL_EXT_RE = re.compile(r'\.(onnx|tflite|snc|pb|pt|pth|bin|h5)$', re.IGNORECASE)

# Field-level patterns
RE_MODEL = re.compile(r'^\s*Model\s+name\s*:\s*(.+?)\s*$', re.MULTILINE)
RE_SDK = re.compile(r'^\s*SDK\s+version\s*:\s*(\S+)', re.MULTILINE)
RE_DTYPE = re.compile(
    r'^\s*Data\s+type\s*:\s*org_model\s*:\s*(\S+)\s+VS\s+hw\s*:\s*(\S+)',
    re.MULTILINE | re.IGNORECASE,
)
# SNR can be list [a, b, c]db or single number 12.34db (negative allowed)
RE_SNR_LIST = re.compile(r'^\s*SNR\s*:\s*\[([^\]]+)\]\s*db', re.MULTILINE | re.IGNORECASE)
RE_SNR_SINGLE = re.compile(r'^\s*SNR\s*:\s*(-?\d+(?:\.\d+)?)\s*db', re.MULTILINE | re.IGNORECASE)


def parse_args():
    p = argparse.ArgumentParser(
        prog='parse_snr',
        description='Parse org_vs_hw.txt and extract SNR + metadata.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --input-file /path/to/m001/Converter_result/org_vs_hw.txt

Output fields (on success):
  model_filename        raw model file name from header
  model_name            filename with extension stripped
  sdk_version           SDK version string
  dtype_org             original model dtype
  dtype_hw              hardware/quantized dtype
  snr                   float (single-output) or list of floats (multi-output)
  snr_min               float, always present (for uniform sorting/filtering)
  is_multi_output       bool

Exit codes:
  0 = parser ran; check status in JSON ('ok' | 'missing' | 'parse_error')
  2 = bad arguments
  3 = unexpected runtime error
""",
    )
    p.add_argument('--input-file', required=True, type=Path, metavar='PATH',
                   help='Path to org_vs_hw.txt')
    p.add_argument('--decimals', type=int, default=SNR_DECIMALS, metavar='N',
                   help=f'Round SNR to N decimals (default: {SNR_DECIMALS})')
    p.add_argument('-v', '--verbose', action='store_true')
    return p.parse_args()


def emit(payload: dict, exit_code: int = EXIT_OK):
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.exit(exit_code)


def _round(x: float, decimals: int) -> float:
    return round(float(x), decimals)


def parse_org_vs_hw(path: Path, decimals: int = SNR_DECIMALS) -> dict:
    """Parse the org_vs_hw.txt file into a structured dict."""
    if not path.exists():
        return {'status': 'missing', 'path': str(path)}

    try:
        text = path.read_text(errors='replace')
    except Exception as e:
        return {'status': 'read_error', 'path': str(path), 'error': str(e)}

    result = {'status': 'ok', 'path': str(path)}
    missing_fields = []

    # Model name + strip extension
    m = RE_MODEL.search(text)
    if m:
        raw = m.group(1).strip()
        result['model_filename'] = raw
        result['model_name'] = MODEL_EXT_RE.sub('', raw)
    else:
        missing_fields.append('Model name')

    # SDK version
    m = RE_SDK.search(text)
    if m:
        result['sdk_version'] = m.group(1).strip()
    else:
        missing_fields.append('SDK version')

    # Data type (two sub-fields)
    m = RE_DTYPE.search(text)
    if m:
        result['dtype_org'] = m.group(1).strip()
        result['dtype_hw'] = m.group(2).strip()
    else:
        missing_fields.append('Data type')

    # SNR: try list first (more specific), then single
    m = RE_SNR_LIST.search(text)
    if m:
        try:
            vals = [_round(v.strip(), decimals) for v in m.group(1).split(',') if v.strip()]
            if not vals:
                raise ValueError('empty SNR list')
            result['snr'] = vals
            result['snr_min'] = min(vals)
            result['is_multi_output'] = True
        except ValueError as e:
            result['status'] = 'parse_error'
            result['error'] = f'SNR list parse failed: {e}'
            return result
    else:
        m = RE_SNR_SINGLE.search(text)
        if m:
            v = _round(m.group(1), decimals)
            result['snr'] = v
            result['snr_min'] = v
            result['is_multi_output'] = False
        else:
            missing_fields.append('SNR')

    if 'snr' not in result:
        result['status'] = 'parse_error'
        result['error'] = f'missing fields: {missing_fields}'

    return result


def main():
    args = parse_args()
    if args.verbose:
        log.setLevel(logging.DEBUG)

    if args.decimals < 0 or args.decimals > 10:
        emit({'status': 'error', 'error_kind': 'invalid_args',
              'errors': ['--decimals must be 0..10']}, EXIT_USER_ERROR)

    result = parse_org_vs_hw(args.input_file, decimals=args.decimals)
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
