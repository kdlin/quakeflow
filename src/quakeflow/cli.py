from __future__ import annotations

import argparse
import sys
from pathlib import Path

from quakeflow.config import FEEDS, ProjectPaths
from quakeflow.dashboard import build_dashboard
from quakeflow.pipeline import run_pipeline
from quakeflow.quality import run_quality_checks
from quakeflow.warehouse import connect, initialize


def _paths(root: str | None) -> ProjectPaths:
    return ProjectPaths.from_root(Path(root) if root else None)


def command_run(args: argparse.Namespace) -> int:
    summary = run_pipeline(_paths(args.root), feed=args.feed)
    print(f"run_id:     {summary.run_id}")
    print(f"feed:       {summary.feed}")
    print(f"extracted:  {summary.extracted}")
    print(f"accepted:   {summary.accepted}")
    print(f"rejected:   {summary.rejected}")
    print(f"bronze:     {summary.bronze_path}")
    print(f"silver:     {summary.silver_path}")
    print(f"dashboard:  {summary.dashboard_path}")
    print(f"quality:    {'PASS' if summary.quality_passed else 'WARNING'}")
    return 0 if summary.quality_passed else 2


def command_quality(args: argparse.Namespace) -> int:
    paths = _paths(args.root)
    connection = connect(paths)
    initialize(connection, paths)
    checks = run_quality_checks(connection, freshness_hours=args.freshness_hours)
    connection.close()
    for check in checks:
        marker = "PASS" if check.passed else "FAIL"
        print(f"[{marker}] {check.name}: {check.observed} ({check.expectation})")
    return 0 if all(check.passed for check in checks) else 2


def command_dashboard(args: argparse.Namespace) -> int:
    paths = _paths(args.root)
    connection = connect(paths)
    initialize(connection, paths)
    target = build_dashboard(connection, paths.docs / "index.html")
    connection.close()
    print(target)
    return 0


def command_stats(args: argparse.Namespace) -> int:
    paths = _paths(args.root)
    connection = connect(paths, read_only=True)
    rows = connection.execute(
        """
        SELECT region, event_count, maximum_magnitude
        FROM gold_region_metrics LIMIT ?
        """,
        [args.limit],
    ).fetchall()
    connection.close()
    print(f"{'REGION':<28} {'EVENTS':>8} {'MAX MAG':>8}")
    for region, count, maximum in rows:
        print(f"{region[:28]:<28} {count:>8} {maximum:>8.1f}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quakeflow",
        description="Run and inspect the QuakeFlow earthquake data pipeline.",
    )
    parser.add_argument("--root", help="Project root override, primarily for testing")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run extraction through dashboard generation")
    run_parser.add_argument("--feed", choices=FEEDS, default="all_day")
    run_parser.set_defaults(handler=command_run)

    quality_parser = subparsers.add_parser("quality", help="Run warehouse quality checks")
    quality_parser.add_argument("--freshness-hours", type=int, default=48)
    quality_parser.set_defaults(handler=command_quality)

    dashboard_parser = subparsers.add_parser("dashboard", help="Rebuild the static dashboard")
    dashboard_parser.set_defaults(handler=command_dashboard)

    stats_parser = subparsers.add_parser("stats", help="Print the most active regions")
    stats_parser.add_argument("--limit", type=int, default=10)
    stats_parser.set_defaults(handler=command_stats)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        sys.exit(args.handler(args))
    except KeyboardInterrupt:
        print("Pipeline interrupted", file=sys.stderr)
        sys.exit(130)
    except Exception as error:
        print(f"QuakeFlow failed: {error}", file=sys.stderr)
        sys.exit(1)
