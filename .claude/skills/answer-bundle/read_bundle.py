#!/usr/bin/env python3
"""Read a context bundle a section at a time, and validate a reply against it.

A bundle is one JSON file holding a whole tuning session — hundreds of tables
with their decoded values. Opening it whole is not a way to read it: the table
section alone is most of the file, and almost none of it is relevant to any one
question. This tool exists so an answer is written from the parts that matter,
looked up by name.

Every subcommand prints text for a person (or a model) to read, never JSON to be
piped onward, with one exception: ``table`` prints values as JSON because that is
what a recommendation has to restate exactly.

Run it with the library's interpreter, which is the only one that has simoscal:

    Code/.venv/bin/python .claude/skills/answer-bundle/read_bundle.py <cmd> ...

Only ``validate`` actually needs the library; the rest read plain JSON and work
under any Python 3.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _fmt_num(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


# --------------------------------------------------------------------------- #
def cmd_sections(args) -> None:
    """What is in this bundle, and how much of it."""
    b = _load(args.bundle)
    prov = b.get("provenance", {})
    print(f"bundle_version : {b.get('bundle_version')}")
    print(f"profile        : {prov.get('profile')}")
    print(f"spaces         : {', '.join(prov.get('spaces') or [])}")
    print(f"switch patch   : {prov.get('has_switch_patch')}")
    print(f"bin_sha256     : {prov.get('bin_sha256')}")
    print(f"xdf_sha256     : {prov.get('xdf_sha256')}")
    print(f"addresses      : {prov.get('address_note')}")
    if prov.get("recovered"):
        print("recovered      : true (journal replayed onto the source bin)")
    print()
    tables = b.get("tables") or []
    edited = [t for t in tables if "source_values" in t]
    print(f"tables         : {len(tables)}  ({len(edited)} edited this session)")
    print(f"journal        : {len(b.get('journal') or [])} entries "
          f"{b.get('journal_counts') or {}}")
    logs = b.get("logs") or {}
    print(f"logs           : {', '.join(b.get('log_names') or []) or '(none)'}")
    if logs:
        print(f"                 {len(logs.get('pulls') or [])} pulls, "
              f"{len(logs.get('findings') or [])} findings, "
              f"{len(logs.get('skipped') or [])} skipped, "
              f"cal_resolved={logs.get('cal_resolved')}")
    print(f"notes          : {b.get('notes') or '(none)'}")
    print()
    reply = b.get("reply") or {}
    print(f"reply schema   : version {reply.get('schema_version')} "
          f"({reply.get('reference')})")
    print("echo verbatim  : " + ", ".join(reply.get("provenance_to_echo") or []))


def cmd_brief(args) -> None:
    """The safety brief, both halves, exactly as it shipped."""
    print(_load(args.bundle).get("safety_brief") or "(no brief in this bundle)")


def cmd_notes(args) -> None:
    """What the person actually asked, if they said anything."""
    print(_load(args.bundle).get("notes") or "(no notes)")


def cmd_logs(args) -> None:
    """The analysis battery's findings, pulls and — importantly — its skips."""
    logs = _load(args.bundle).get("logs") or {}
    if not logs:
        print("(no logs in this bundle)")
        return

    print("== pulls")
    for p in logs.get("pulls") or []:
        env = p.get("environment") or {}
        print(
            f"  #{p.get('index')} {p.get('file')} gear {p.get('gear')}"
            f"{'' if p.get('gear_resolved', True) else ' (unresolved)'}"
            f"  rows {p.get('start_row')}-{p.get('end_row')}"
            f"  {_fmt_num(p.get('rpm_min'))}-{_fmt_num(p.get('rpm_max'))} rpm"
            f"  {_fmt_num(p.get('duration_s'))} s"
        )
        print(
            f"      boost max {_fmt_num(p.get('max_boost'))}"
            f"  PUT max {_fmt_num(p.get('max_put'))}"
            f"  PUT err max {_fmt_num(p.get('max_put_error'))}"
            f"  knock {_fmt_num(p.get('min_knock'))}"
            f"  HPFP {_fmt_num(p.get('hpfp_eff_max'))}"
            f"  lambda err {_fmt_num(p.get('lambda_error_min'))}"
            f"/{_fmt_num(p.get('lambda_error_max'))}"
        )
        if env:
            print("      " + "  ".join(f"{k} {_fmt_num(v)}" for k, v in sorted(env.items())))

    print()
    print("== findings")
    order = {"High": 0, "Medium": 1, "Low": 2, "Info": 3}
    for f in sorted(logs.get("findings") or [],
                    key=lambda f: order.get(f.get("severity"), 9)):
        print(f"  [{f.get('severity')}] {f.get('title')}  ({f.get('check_id')})")
        print(f"      {f.get('message')}")
        if f.get("pull_refs"):
            print(f"      pulls: {f['pull_refs']}")
        if args.evidence and f.get("evidence"):
            for line in json.dumps(f["evidence"], indent=2, sort_keys=True).splitlines():
                print("      " + line)

    print()
    print("== skipped (a check that did not run is not a check that passed)")
    for s in logs.get("skipped") or []:
        print(f"  {s.get('check_id', s)}: {s.get('reason', '')}"
              if isinstance(s, dict) else f"  {s}")
    if not logs.get("skipped"):
        print("  (none)")

    cov = logs.get("coverage") or {}
    if cov:
        print()
        print("== coverage")
        for line in json.dumps(cov, indent=2, sort_keys=True).splitlines()[:args.coverage_lines]:
            print("  " + line)


def cmd_journal(args) -> None:
    """What this session already changed, in order, with each stated intent."""
    b = _load(args.bundle)
    entries = b.get("journal") or []
    print(f"{len(entries)} entries  {b.get('journal_counts') or {}}")
    for i, e in enumerate(entries):
        if isinstance(e, str):
            print(f"  {i:3d}  {e}")
            continue
        print(f"  {i:3d}  {e}")


def _tables(b: dict, args) -> list:
    out = []
    for t in b.get("tables") or []:
        if args.space and t.get("space") != args.space:
            continue
        if args.owner_only and not t.get("owner"):
            continue
        if args.grep:
            hay = " ".join(str(t.get(k, "")) for k in
                           ("name", "id", "description", "title", "group", "symbol"))
            if args.grep.lower() not in hay.lower():
                continue
        out.append(t)
    return out


def cmd_tables(args) -> None:
    """An index of tables: enough to choose one, never their values."""
    b = _load(args.bundle)
    rows = _tables(b, args)
    print(f"{len(rows)} table(s)")
    for t in rows:
        flags = []
        if t.get("owner"):
            flags.append(f"owner={t['owner']}")
        if t.get("is_axis"):
            flags.append("AXIS")
        if "source_values" in t:
            flags.append("edited")
        if not t.get("reversible"):
            flags.append("not-reversible")
        print(f"  [{t.get('space')}] {t.get('name')}  `{t.get('id')}` — {t.get('description')}")
        print(f"      shape {t.get('shape')}  units {t.get('units') or '-'}"
              + (f"  {' '.join(flags)}" if flags else ""))


def cmd_table(args) -> None:
    """One table in full: axes, current values, and what stock/import held."""
    b = _load(args.bundle)
    matches = [t for t in b.get("tables") or []
               if t.get("name") == args.name
               and (not args.space or t.get("space") == args.space)]
    if not matches:
        print(f"no table named {args.name!r}"
              + (f" in space {args.space!r}" if args.space else ""))
        sys.exit(1)
    for t in matches:
        print(f"[{t.get('space')}] {t.get('name')}")
        print(f"  label       : `{t.get('id')}` — {t.get('description')}")
        print(f"  title       : {t.get('title')}")
        print(f"  symbol      : {t.get('symbol')}")
        print(f"  units       : {t.get('units')}  ({t.get('units_description')})")
        print(f"  shape       : {t.get('shape')}   ndim {t.get('ndim')}")
        print(f"  owner       : {t.get('owner') or '(generic editor)'}")
        print(f"  is_axis     : {t.get('is_axis')}   reversible: {t.get('reversible')}")
        print(f"  group       : {t.get('group')}   categories: {t.get('categories')}")
        for which in ("x_axis", "y_axis"):
            axis = t.get(which)
            if axis:
                print(f"  {which:11s}: {axis.get('label')} [{axis.get('units')}]")
                print(f"               {json.dumps(axis.get('values'))}")
        print("  values      :")
        print(json.dumps(t.get("values"), indent=2))
        if "source_values" in t:
            print("  source_values (what the imported bin held — the grid the logs ran on):")
            print(json.dumps(t.get("source_values"), indent=2))


def cmd_validate(args) -> None:
    """Run the real schema over a reply, and echo-check its provenance."""
    from simoscal.advice import AdviceRejected, parse

    text = Path(args.reply).read_text(encoding="utf-8")
    try:
        parsed = parse(text)
    except AdviceRejected as exc:
        print("REJECTED")
        print(exc)
        sys.exit(1)

    print(f"OK — schema version {parsed.schema_version}, "
          f"{len(parsed.recommendations)} recommendation(s)")
    for rec in parsed.recommendations:
        print(f"  {rec.id}: [{rec.change.space}] {rec.table.name}  {rec.table.label}")
        print(f"      {rec.change.operation} {rec.change.selection.kind}"
              f"{list(rec.change.selection.args) if rec.change.selection.args else ''}"
              f"  risk={rec.risk} confidence={rec.confidence}")
    if parsed.summary:
        print(f"  summary: {parsed.summary}")

    if args.bundle:
        prov = (_load(args.bundle).get("provenance") or {})
        bad = [k for k in ("profile", "bin_sha256", "xdf_sha256")
               if getattr(parsed.provenance, k) != prov.get(k)]
        if bad:
            print(f"PROVENANCE MISMATCH on {', '.join(bad)} — "
                  "the whole file would be refused before any replay")
            sys.exit(1)
        print("  provenance matches the bundle")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def bundle_arg(p):
        p.add_argument("bundle", help="path to the bundle JSON")

    p = sub.add_parser("sections", help="what is in this bundle, and how much")
    bundle_arg(p); p.set_defaults(func=cmd_sections)

    p = sub.add_parser("brief", help="the safety brief, verbatim")
    bundle_arg(p); p.set_defaults(func=cmd_brief)

    p = sub.add_parser("notes", help="what the person asked")
    bundle_arg(p); p.set_defaults(func=cmd_notes)

    p = sub.add_parser("logs", help="pulls, findings and skipped checks")
    bundle_arg(p)
    p.add_argument("--evidence", action="store_true", help="include each finding's structured evidence")
    p.add_argument("--coverage-lines", type=int, default=40)
    p.set_defaults(func=cmd_logs)

    p = sub.add_parser("journal", help="what this session already changed")
    bundle_arg(p); p.set_defaults(func=cmd_journal)

    p = sub.add_parser("tables", help="index of tables (no values)")
    bundle_arg(p)
    p.add_argument("--grep", help="substring over name/id/description/title/group/symbol")
    p.add_argument("--space", help="only this table space")
    p.add_argument("--owner-only", action="store_true", help="only owner-locked tables")
    p.set_defaults(func=cmd_tables)

    p = sub.add_parser("table", help="one table in full, with axes and values")
    bundle_arg(p)
    p.add_argument("name")
    p.add_argument("--space")
    p.set_defaults(func=cmd_table)

    p = sub.add_parser("validate", help="run the real schema over a reply")
    p.add_argument("reply")
    p.add_argument("--bundle", help="also check the provenance echo against this bundle")
    p.set_defaults(func=cmd_validate)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
