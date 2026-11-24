from __future__ import annotations

import argparse
import json
import sys

from .lint import lint_tools, load_tools

ORDER = {"error": 0, "warn": 1, "info": 2}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tool-schema-lint", description=__doc__)
    ap.add_argument("file", help="JSON file with a list of tool definitions")
    ap.add_argument("--json", action="store_true", help="print findings as JSON")
    ap.add_argument("--overlap", type=float, default=0.6, help="description overlap threshold (0-1)")
    ap.add_argument("--fail-on", choices=["error", "warn", "never"], default="error")
    args = ap.parse_args(argv)

    try:
        with open(args.file, encoding="utf-8") as f:
            tools = load_tools(json.load(f))
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    findings = sorted(lint_tools(tools, args.overlap), key=lambda x: (ORDER[x.severity], x.tool, x.rule))
    if args.json:
        print(json.dumps([f.__dict__ for f in findings], indent=2))
    else:
        for f in findings:
            print(f"{f.severity.upper():5} {f.rule} {f.tool}: {f.message}")
        print(f"{len(tools)} tools, {len(findings)} findings")

    if args.fail_on == "never":
        return 0
    bad = {"error"} if args.fail_on == "error" else {"error", "warn"}
    return 1 if any(f.severity in bad for f in findings) else 0
