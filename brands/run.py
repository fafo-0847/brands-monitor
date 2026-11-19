"""Run brand scrapers one at a time, diff against each baseline and email changes.

    python -m brands.run --brand gul-ahmed-ideas --dry-run
    python -m brands.run --brand gul-ahmed-ideas --state data/state.json --report data/changes.json
    python -m brands.run --all --limit 20                # smoke test; never saves baselines or emails
    python -m brands.run --matrix                        # JSON list of brands for GitHub Actions
"""
import argparse
import importlib
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

from brands.engine import Unavailable
from brands.mailer import notify
from monitor import atomic_json, changes_between, email_body, fingerprint

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LOG = ROOT / 'logs' / 'brands.log'
EXCLUDED_FROM_ACTIONS = {'mango'}  # global site answers datacenter IPs with 429 on the first request


def log(message):
    line = f'{time.strftime("%H:%M:%S")} {message}'
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open('a', encoding='utf-8') as fh:
        fh.write(line + '\n')


def site(url):
    host = urlsplit(url or '').hostname or ''
    return host.removeprefix('www.')


def run_brand(slug, config, args, tag):
    module = importlib.import_module(f'brands.scrapers.{config["module"]}')
    data_dir = ROOT / 'data' / 'brands' / slug
    state_path = args.state or data_dir / 'state.json'
    report_path = args.report or data_dir / 'changes.json'
    old = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else None
    if old is not None and (old.get('schema_version') != 1 or not old.get('products')):
        raise ValueError('Invalid or incompatible baseline; inspect it before proceeding')
    if old is not None and old.get('source') != config['all_products_url']:
        # A scraping-strategy change on the same site keys products differently; diffing would email
        # thousands of fake add/remove changes, so start a fresh baseline instead. Another site = misrestore.
        if site(old.get('source')) != site(config['all_products_url']):
            raise ValueError(f'Baseline source {old.get("source")} is not this brand; inspect it before proceeding')
        log(f'{tag}   baseline from older strategy ({old.get("source")}); re-baselining without email')
        old = None
    current = module.scrape(limit=args.limit, pause=args.pause, log=lambda m: log(f'{tag}   {m}'), old=old)
    if old and current['currency'] != old['currency']:
        raise ValueError('Currency changed; baseline preserved')
    changes = changes_between(old or {'products': {}}, current) if old or args.email_on_first_run else []
    report = {'checked_at': current['checked_at'], 'baseline_created': old is None,
              'product_count': len(current['products']), 'change_count': len(changes), 'changes': changes}
    store = SimpleNamespace(name=config['name'])
    if args.dry_run or args.limit:
        atomic_json(state_path.with_name('preview-state.json'), current)
        atomic_json(report_path.with_name('preview-changes.json'), report)
        report_path.with_name('preview-email.html').write_text(email_body(changes, store), encoding='utf-8')
        return report
    if changes:
        from playwright.sync_api import sync_playwright
        event_key = fingerprint([old.get('checked_at') if old else 'initial-baseline',
                                 old['products'] if old else {}, current['products']])
        with sync_playwright() as playwright:
            emails = notify(playwright, changes, event_key, store)
        log(f'{tag}   emailed {len(changes)} changes in {emails} email(s)')
    # Never advance the baseline until every notification is accepted.
    atomic_json(report_path, report)
    atomic_json(state_path, current)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--brand', nargs='*', default=[])
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--matrix', action='store_true', help='Print the GitHub Actions brand matrix and exit')
    parser.add_argument('--legacy-state', metavar='SLUG',
                        help='Print the pre-migration monitor-state baseline path of this brand (or nothing)')
    parser.add_argument('--state', type=Path, help='Baseline path (single brand only)')
    parser.add_argument('--report', type=Path, help='Report path (single brand only)')
    parser.add_argument('--limit', type=int, help='Stop after N products (smoke test; never saves or emails)')
    parser.add_argument('--pause', type=float, default=0.35)
    parser.add_argument('--between', type=float, default=5, help='Seconds to wait between brands')
    parser.add_argument('--dry-run', action='store_true', help='Scan and write preview files; no email, baseline unchanged')
    parser.add_argument('--email-on-first-run', action='store_true')
    args = parser.parse_args()
    configs = json.loads((HERE / 'scrapers.json').read_text(encoding='utf-8'))
    if args.legacy_state:
        print(configs[args.legacy_state].get('legacy_state', ''))
        return 0
    if args.matrix:
        print(json.dumps([s for s, c in configs.items()
                          if c['strategy'] != 'unavailable' and s not in EXCLUDED_FROM_ACTIONS]))
        return 0
    slugs = list(configs) if args.all else args.brand
    if not slugs:
        parser.error('pass --brand SLUG [SLUG...] or --all')
    if (args.state or args.report) and len(slugs) != 1:
        parser.error('--state/--report need exactly one --brand')
    if args.pause < 0:
        parser.error('--pause must be nonnegative')
    summary, failed = {}, False
    for index, slug in enumerate(slugs, 1):
        tag = f'[{index:02d}/{len(slugs)}] {slug}'
        config = configs[slug]
        log(f'{tag} ... in progress ({config["strategy"]})')
        started = time.time()
        try:
            report = run_brand(slug, config, args, tag)
            result = f'DONE {report["product_count"]} products, {report["change_count"]} changes'
        except Unavailable as exc:
            result = f'SKIPPED {exc}'
        except Exception as exc:
            result = f'FAILED {type(exc).__name__}: {str(exc)[:200]}'
            failed = True
        summary[slug] = result
        log(f'{tag} {result} [{time.time() - started:.1f}s]')
        if index < len(slugs):
            time.sleep(args.between)
    atomic_json(ROOT / 'logs' / 'brands-summary.json', summary)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
