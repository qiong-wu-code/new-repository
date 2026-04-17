#!/usr/bin/env python3
"""
Build standard skill directories from skill_manifests/ + scripts/ sources.

For each skill under skill_manifests/<name>/:
  - Read manifest.yaml (list of scripts and lib files needed)
  - Copy SKILL.md as-is
  - Copy declared scripts into <dist>/<name>/scripts/
  - Copy declared lib files into <dist>/<name>/lib/
  - Optionally zip the result for delivery

Usage:
  build.py                                    # build all skills to dist/
  build.py --only parse-snr                   # build one skill
  build.py --zip                              # also produce dist/<name>.zip
  build.py --clean                            # remove dist/ first
  build.py --dry-run                          # show what would happen
  build.py --verify                           # sanity-check built skills
"""
import argparse
import json
import logging
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    print(json.dumps({
        "status": "error",
        "error_kind": "missing_dependency",
        "message": "PyYAML is required. Install with: pip install pyyaml"
    }))
    sys.exit(3)

EXIT_OK = 0
EXIT_USER_ERROR = 2
EXIT_RUNTIME_ERROR = 3
EXIT_PARTIAL = 4

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s',
    stream=sys.stderr,
)
log = logging.getLogger(__name__)

# ============================================================
# Paths (relative to repo root where build.py lives)
# ============================================================
ROOT = Path(__file__).parent.resolve()
MANIFESTS_DIR = ROOT / 'skill_manifests'
SCRIPTS_DIR = ROOT / 'scripts'
LIB_DIR = ROOT / 'lib'
DIST_DIR = ROOT / 'dist'


def parse_args():
    p = argparse.ArgumentParser(
        prog='build',
        description='Build standard skill packages from manifests.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                         Build all skills
  %(prog)s --only parse-snr        Build one skill
  %(prog)s --zip                   Also produce zip archives
  %(prog)s --clean                 Remove dist/ before build
  %(prog)s --dry-run               Preview without writing
  %(prog)s --verify                Sanity-check built skills

Exit codes:
  0 = all ok
  2 = user error (bad manifest, missing source file)
  3 = runtime error
  4 = partial (some skills built, some failed)
""",
    )
    p.add_argument('--only', default=None, metavar='NAME',
                   help='Build only the specified skill')
    p.add_argument('--dist-dir', default=str(DIST_DIR), type=Path, metavar='DIR',
                   help=f'Output directory (default: {DIST_DIR.name}/)')
    p.add_argument('--zip', action='store_true',
                   help='Produce zip archives alongside the directories')
    p.add_argument('--clean', action='store_true',
                   help='Remove dist directory before building')
    p.add_argument('--dry-run', action='store_true',
                   help='Show planned actions without writing')
    p.add_argument('--verify', action='store_true',
                   help='Check built skills for common issues')
    p.add_argument('-v', '--verbose', action='store_true',
                   help='Verbose logging to stderr')
    return p.parse_args()


def emit(payload: dict, exit_code: int = EXIT_OK):
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.exit(exit_code)


# ============================================================
# Manifest loading
# ============================================================
def load_manifest(skill_dir: Path) -> dict:
    """Load and validate a skill's manifest.yaml."""
    manifest_file = skill_dir / 'manifest.yaml'
    skill_md = skill_dir / 'SKILL.md'

    if not skill_md.exists():
        raise ValueError(f"Missing SKILL.md in {skill_dir}")
    if not manifest_file.exists():
        raise ValueError(f"Missing manifest.yaml in {skill_dir}")

    data = yaml.safe_load(manifest_file.read_text()) or {}
    scripts = data.get('scripts', []) or []
    libs = data.get('lib', []) or []

    # Validate all referenced files exist
    missing = []
    for s in scripts:
        if not (ROOT / s).exists():
            missing.append(s)
    for l in libs:
        if not (ROOT / l).exists():
            missing.append(l)
    if missing:
        raise ValueError(f"Files declared in manifest but missing on disk: {missing}")

    return {
        'name': skill_dir.name,
        'skill_md': skill_md,
        'scripts': scripts,
        'libs': libs,
    }


def discover_skills(only: str | None = None) -> list[dict]:
    """Find all skill manifests."""
    if not MANIFESTS_DIR.is_dir():
        raise ValueError(f"Manifests directory not found: {MANIFESTS_DIR}")

    skills = []
    errors = []
    for d in sorted(MANIFESTS_DIR.iterdir()):
        if not d.is_dir():
            continue
        if only and d.name != only:
            continue
        try:
            skills.append(load_manifest(d))
        except Exception as e:
            errors.append({'name': d.name, 'error': str(e)})

    if only and not skills and not errors:
        raise ValueError(f"Skill '{only}' not found in {MANIFESTS_DIR}")

    return skills, errors


# ============================================================
# Build
# ============================================================
def build_one(skill: dict, dist_dir: Path, dry_run: bool = False) -> dict:
    """Build a single skill into dist_dir/<name>/."""
    target = dist_dir / skill['name']
    actions = []

    actions.append(('mkdir', str(target)))
    actions.append(('copy', str(skill['skill_md']), str(target / 'SKILL.md')))

    for s in skill['scripts']:
        src = ROOT / s
        dst = target / 'scripts' / Path(s).name
        actions.append(('copy', str(src), str(dst)))

    for l in skill['libs']:
        src = ROOT / l
        # Preserve lib/ subdirectory structure so imports still work
        dst = target / Path(l)
        actions.append(('copy', str(src), str(dst)))

    if dry_run:
        return {'status': 'would_build', 'name': skill['name'],
                'target': str(target), 'actions': actions}

    # Execute
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    shutil.copy2(skill['skill_md'], target / 'SKILL.md')

    scripts_target = target / 'scripts'
    scripts_target.mkdir(exist_ok=True)
    for s in skill['scripts']:
        shutil.copy2(ROOT / s, scripts_target / Path(s).name)

    for l in skill['libs']:
        dst = target / Path(l)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / l, dst)

    return {
        'status': 'ok',
        'name': skill['name'],
        'target': str(target),
        'files': len(skill['scripts']) + len(skill['libs']) + 1,
    }


def zip_skill(skill_name: str, dist_dir: Path) -> Path:
    """Zip a built skill directory."""
    source = dist_dir / skill_name
    zip_path = dist_dir / f"{skill_name}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in source.rglob('*'):
            if f.is_file():
                zf.write(f, f.relative_to(source.parent))
    return zip_path


# ============================================================
# Verification
# ============================================================
def verify_skill(skill_dir: Path) -> list[str]:
    """Return list of issues found. Empty list = ok."""
    issues = []

    skill_md = skill_dir / 'SKILL.md'
    if not skill_md.exists():
        issues.append("missing SKILL.md")
        return issues

    content = skill_md.read_text(errors='replace')
    if not content.startswith('---'):
        issues.append("SKILL.md missing frontmatter (no leading ---)")
    else:
        # Crude frontmatter check
        end = content.find('---', 3)
        if end == -1:
            issues.append("SKILL.md frontmatter not closed")
        else:
            fm = content[3:end]
            if 'name:' not in fm:
                issues.append("SKILL.md frontmatter missing 'name:'")
            if 'description:' not in fm:
                issues.append("SKILL.md frontmatter missing 'description:'")

    # Check all python files parse
    for py in skill_dir.rglob('*.py'):
        try:
            compile(py.read_text(), str(py), 'exec')
        except SyntaxError as e:
            issues.append(f"syntax error in {py.relative_to(skill_dir)}: {e}")

    return issues


# ============================================================
# Main
# ============================================================
def main():
    args = parse_args()
    if args.verbose:
        log.setLevel(logging.DEBUG)

    dist_dir = Path(args.dist_dir).resolve()

    # Clean
    if args.clean and not args.dry_run:
        if dist_dir.exists():
            log.info(f"Removing {dist_dir}")
            shutil.rmtree(dist_dir)

    # Discover skills
    try:
        skills, discovery_errors = discover_skills(args.only)
    except Exception as e:
        emit({
            'status': 'error',
            'error_kind': 'discovery_failed',
            'message': str(e),
        }, EXIT_USER_ERROR)

    if discovery_errors and not skills:
        emit({
            'status': 'error',
            'error_kind': 'all_manifests_invalid',
            'errors': discovery_errors,
        }, EXIT_USER_ERROR)

    if not skills:
        emit({
            'status': 'error',
            'error_kind': 'no_skills_found',
            'manifests_dir': str(MANIFESTS_DIR),
            'only_filter': args.only,
        }, EXIT_USER_ERROR)

    log.info(f"Found {len(skills)} skill(s) to build")

    # Dry run
    if args.dry_run:
        plans = [build_one(s, dist_dir, dry_run=True) for s in skills]
        emit({
            'status': 'dry_run',
            'dist_dir': str(dist_dir),
            'skills': plans,
            'discovery_errors': discovery_errors,
        }, EXIT_OK)

    # Build
    dist_dir.mkdir(parents=True, exist_ok=True)
    results = []
    build_errors = 0
    for s in skills:
        try:
            r = build_one(s, dist_dir)
            log.info(f"Built {s['name']} ({r['files']} files)")
            if args.zip:
                zp = zip_skill(s['name'], dist_dir)
                r['zip'] = str(zp)
                log.info(f"Zipped {s['name']} -> {zp.name}")
            if args.verify:
                issues = verify_skill(dist_dir / s['name'])
                r['verify_issues'] = issues
                if issues:
                    log.warning(f"{s['name']}: {len(issues)} issue(s)")
            results.append(r)
        except Exception as e:
            log.exception(f"Build failed: {s['name']}")
            build_errors += 1
            results.append({'status': 'failed', 'name': s['name'], 'error': str(e)})

    # Summary
    total_errors = build_errors + len(discovery_errors)
    exit_code = EXIT_PARTIAL if total_errors > 0 else EXIT_OK
    emit({
        'status': 'ok' if exit_code == EXIT_OK else 'partial',
        'dist_dir': str(dist_dir),
        'built': len([r for r in results if r.get('status') == 'ok']),
        'failed': build_errors,
        'discovery_errors': discovery_errors,
        'skills': results,
        'timestamp': datetime.now().isoformat(),
    }, exit_code)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        log.warning("Interrupted")
        sys.exit(130)
    except SystemExit:
        raise
    except Exception as e:
        log.exception("Unhandled exception")
        emit({
            'status': 'error',
            'error_kind': 'unhandled_exception',
            'message': str(e),
        }, EXIT_RUNTIME_ERROR)
