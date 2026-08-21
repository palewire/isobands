"""Command-line diagnostics for isobands."""

from __future__ import annotations

import argparse
import json
from typing import TYPE_CHECKING

from isobands._diagnostics import CheckReport, check

if TYPE_CHECKING:
    from collections.abc import Sequence


def _print_human(report: CheckReport) -> None:
    for result in report.checks:
        status = "ok" if result.ok else "failed"
        print(f"[{status}] {result.name}: {result.message}")
        if not result.ok:
            print(f"  Guidance: {result.guidance}")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the package command-line interface."""
    parser = argparse.ArgumentParser(prog="python -m isobands")
    subcommands = parser.add_subparsers(dest="command", required=True)
    check_parser = subcommands.add_parser(
        "check", help="check GDAL and contour support"
    )
    check_parser.add_argument(
        "--json", action="store_true", help="print the JSON report"
    )
    args = parser.parse_args(argv)

    if args.command == "check":
        report = check()
        if args.json:
            print(json.dumps(report.to_dict(), sort_keys=True))
        else:
            _print_human(report)
        return 0 if report.ok else 1
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
