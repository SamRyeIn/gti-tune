#!/usr/bin/env python3
"""The courier back-test: would Claude have recommended what Sam actually did?

Stage 2 of "Tune with Claude" is gated on evidence, and this is the rig that
produces it. For a revision that already happened, it reconstructs the session
as it stood *before* that revision — the bin that was flashed, the logs that came
back from driving it — exports a context bundle exactly as the app would, and
lets a model with no knowledge of what happened next answer it. The reply is then
replayed through the library's real guards, and each recommendation is sorted
into one of four buckets against what the revision actually did.

**Reconstruction is deliberately faithful to the app, not to the repository.** A
session opens on an imported bin with an empty journal, because that is what the
app does: a person imports the bin they are running and starts editing. So the
bundle carries no lineage history, and the answering side sees exactly what a
real user's answering side would see. Where that costs a recommendation, that is
a finding about the courier rather than a flaw in the rig.

Four commands, run in order:

    Code/.venv/bin/python Docs/backtest/backtest.py list
    Code/.venv/bin/python Docs/backtest/backtest.py export R15
    Code/.venv/bin/python Docs/backtest/backtest.py answer R15
    Code/.venv/bin/python Docs/backtest/backtest.py replay R15

**The answer is produced blind, and that is enforced rather than promised.**
``answer`` copies the bundle, the answering guide, the schema reference and the
bundle reader into a throwaway directory *outside this repository*, and runs a
fresh ``claude -p`` there. That session has no repository, no CLAUDE.md, no
auto-memory and no lineage — so it cannot know what the next revision turned out
to be. Its full tool transcript is kept alongside the reply, and ``replay``
audits it: a session that reached outside its sandbox is reported, not hidden.

Scope: SC8S50 only, and every bundle says so in its own provenance. A second
registered profile has no tune lineage and no logs, so it cannot contribute to
this evidence even in principle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CODE = REPO / "Code"
BACKTEST = REPO / "Docs" / "backtest"

XDF = CODE / "xdf" / "SC8S50.V1.0.xdf"
SWITCH_XDF = REPO / "BinToolz-main" / "definitions" / "S50 Switch Patch.29.33.V2.xdf"
TUNE_OUT = REPO / "Tunes" / "TuningBasicsGuide" / "TUNE_Basics_Guide_out"
LOGS = REPO / "Logs"

#: The same question in every case, and deliberately a plain one. A prompt
#: written per revision would be a prompt written knowing the answer — the rig
#: would be steering the thing it is measuring.
NOTES = (
    "I flashed this calibration and drove it; these are the logs from that "
    "session. What should the next revision change?"
)


@dataclass(frozen=True)
class Case:
    """One back-tested revision: the state before it, and what it turned out to be."""

    rev: str
    #: The bin that was flashed and driven — the session's imported bin.
    state_bin: Path
    #: The logs recorded on that bin.
    logs_dir: Path
    #: What the revision actually did, in one line. Read *after* the reply
    #: exists, never before.
    actual: str
    #: Anything about this reconstruction a reader should know before trusting
    #: its bucket counts.
    caveat: str = ""


CASES = {
    c.rev: c for c in (
        Case(
            rev="R10",
            state_bin=(TUNE_OUT / "R09_20260712-213556"
                       / "5G0906259L_0002_BasicsGuide_R09.bin"),
            logs_dir=LOGS / "BasicsGuide_R09",
            actual=(
                "Reshaped `IP_PQ_CHA_MAX` — Maximum allowed pressure quotient at "
                "turbo charger compressor to 1.70 @ 1000 rpm and a flat 3.1 from "
                "2000-7000 rpm, to clear the code-128 torque-limiter cap that was "
                "trimming the R09 26 psi shelf."
            ),
        ),
        Case(
            rev="R14",
            state_bin=(TUNE_OUT / "R13_20260719-213357"
                       / "CB_HSL_SP2933_5G0906259L_0002_BasicsGuide_R13.bin"),
            logs_dir=LOGS / "BasicsGuide_R11",
            actual=(
                "Reordered the switch-patch slots least->most aggressive and made "
                "slot 1 a stock map by setting its `PUT setpoint` grid to the "
                "factory `IP_PUT_SP` — Pressure up throttle setpoint curve read "
                "live from the stock bin. Only the four per-slot PUT setpoint "
                "grids moved."
            ),
            caveat=(
                "The bundled logs were recorded on the R11 bin, while the session "
                "opens on R13. R12 (slot-5 valet cap) and R13 (no calibration "
                "change) sit between them — the same mismatch Sam worked under, "
                "since no logs were taken on R12 or R13."
            ),
        ),
        Case(
            rev="R15",
            state_bin=(TUNE_OUT / "R14_20260810-111002"
                       / "CB_HSL_SP2933_5G0906259L_0002_BasicsGuide_R14.bin"),
            logs_dir=LOGS / "BasicsGuide_R14",
            actual=(
                "Walked back five cells of `IP_FAC_BPA_SP[0]` / `[1]` — Map for "
                "boost pressure actuator setpoint (wastegate position "
                "feedforward, VVL 0 / VVL 1) toward their R07 values, every cell "
                "bounded at its R07 level, to close the measured 4000-4500 rpm "
                "boost shortfall the wastegate integral was carrying."
            ),
        ),
        Case(
            rev="R16",
            state_bin=(TUNE_OUT / "R15_20260817-073236"
                       / "CB_HSL_SP2933_5G0906259L_0002_BasicsGuide_R15.bin"),
            logs_dir=LOGS / "BasicsGuide_R15",
            actual=(
                "First MainTune revision. Laid in the exact guide-author Spark "
                "IAT axis/grid, migrated the Reference IGA correction onto the "
                "shared axis without changing its curve, and wrote the EQT "
                "Stage 2 log's 5000-rpm-up `Ignition Table Output` curve across "
                "the 1050/1200/1400 mg/stk rows of all nine "
                "`IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition "
                "angle, VVL 0 port-flap-low maps."
            ),
            caveat=(
                "R16 was never flashed — R17 superseded it as a candidate, "
                "removing the EQT high-rpm advance this case grades against. So "
                "`actual` here is what the next revision was *authored* to be, "
                "not what the car ran, and the timing half of it was later "
                "judged wrong by Sam himself. A recommendation that declines to "
                "add high-rpm advance is not automatically in the Wrong bucket."
            ),
        ),
    )
}


# --------------------------------------------------------------------------- #
# reconstruction
# --------------------------------------------------------------------------- #
def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _open_session(case: Case):
    """The session as the app would hold it: one imported bin, empty journal."""
    from simoscal.tune import SC8S50, Tune
    from simoscal.tune.domains.switchpatch import PATCH_SPACE
    from simoscal.tune.profiles.switchpatch_2933 import SWITCH_PATCH_2933

    for path in (case.state_bin, XDF, SWITCH_XDF, case.logs_dir):
        if not path.exists():
            sys.exit(f"missing input for {case.rev}: {path}")

    tune = Tune.open(
        SC8S50, xdf=XDF, bin=case.state_bin,
        extra_spaces={PATCH_SPACE: (SWITCH_PATCH_2933, SWITCH_XDF)},
    )
    tune.switchpatch.require_sanity()
    provenance = {
        "profile": SC8S50.name,
        "bin_sha256": _sha256(case.state_bin),
        "xdf_sha256": _sha256(XDF),
        "has_switch_patch": True,
    }
    return tune, provenance


def _log_files(case: Case) -> list[Path]:
    return sorted(p for p in case.logs_dir.glob("simostools-*.csv"))


def case_dir(case: Case) -> Path:
    return BACKTEST / case.rev


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def cmd_list(args) -> None:
    for case in CASES.values():
        print(f"{case.rev}")
        print(f"  state bin : {case.state_bin.relative_to(REPO)}")
        print(f"  logs      : {case.logs_dir.relative_to(REPO)} "
              f"({len(_log_files(case))} csv)")
        print(f"  exported  : {'yes' if (case_dir(case) / 'bundle.json').exists() else 'no'}")
        print(f"  answered  : {'yes' if (case_dir(case) / 'reply.json').exists() else 'no'}")
        if case.caveat:
            print(f"  caveat    : {case.caveat}")


def cmd_export(args) -> None:
    from simoscal.advice.bundle import bundle, logs_section, render, write_bundle

    case = CASES[args.rev]
    tune, provenance = _open_session(case)
    paths = _log_files(case)
    if not paths:
        sys.exit(f"no simostools-*.csv in {case.logs_dir}")

    logs = logs_section(paths, names={str(p): p.stem for p in paths})
    payload = bundle(
        tune, provenance=provenance, logs=logs,
        log_names=[p.stem for p in paths], notes=NOTES,
    )

    dest = case_dir(case) / "bundle.json"
    written = write_bundle(payload, dest)

    # D7 is the property the whole rig rests on: the same session state exported
    # twice must be the same bytes, or a back-test cannot be re-run.
    again = bundle(
        tune, provenance=provenance, logs=logs,
        log_names=[p.stem for p in paths], notes=NOTES,
    )
    deterministic = render(again) == render(payload)

    (case_dir(case) / "state.json").write_text(json.dumps({
        "revision": case.rev,
        "state_bin": str(case.state_bin.relative_to(REPO)),
        "logs_dir": str(case.logs_dir.relative_to(REPO)),
        "log_files": [p.name for p in paths],
        "provenance": provenance,
        "bundle_sha256": written.sha256,
        "deterministic": deterministic,
        "notes": NOTES,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"{case.rev}: wrote {dest.relative_to(REPO)}")
    print(f"  {written.bytes_written:,} bytes  sha256 {written.sha256[:16]}…")
    print(f"  deterministic re-render: {'PASS' if deterministic else 'FAIL'}")
    for key, value in written.summary.items():
        print(f"  {key}: {value}")


#: What the blind session is told. It names the bundle, the guide and the
#: reader, and nothing about this car's history — there is nothing here for the
#: rig to leak, because the rig itself never reads the answer's subject matter.
ANSWER_PROMPT = """You are answering a "Tune with Claude" context bundle.

`bundle.json` in this directory describes somebody's open ECU tuning session:
every table their calibration resolves with its current physical values, the
edit journal, the analysis battery's findings for the datalogs they picked, and
the safety brief for their car. Write them one recommendations file back.

Do this:

1. Read `advice-answering-guide.md` in full. It is the method. Then read
   `advice-schema.md` for the exact field shapes.
2. Read the bundle **only** through the reader — it is far too large to open
   whole:
       {python} read_bundle.py sections bundle.json
       {python} read_bundle.py notes bundle.json
       {python} read_bundle.py brief bundle.json
       {python} read_bundle.py logs bundle.json --evidence
       {python} read_bundle.py journal bundle.json
       {python} read_bundle.py tables bundle.json --grep <pattern>
       {python} read_bundle.py table bundle.json <name>
3. Write your answer to `reply.json` in this directory.
4. Validate it and fix everything it names:
       {python} read_bundle.py validate reply.json --bundle bundle.json
   Repeat until it prints OK.

Work only inside this directory. Everything you need is here; there is no
repository to consult and nothing outside is part of this question.

Answer from the bundle alone. An empty `recommendations` list with a `summary`
explaining why is a valid and useful answer — a better one than a change you
cannot defend from the evidence in front of you.
"""


def cmd_answer(args) -> None:
    """Run a fresh, repository-free session against one exported bundle."""
    import shutil
    import subprocess
    import tempfile

    case = CASES[args.rev]
    bundle_path = case_dir(case) / "bundle.json"
    if not bundle_path.exists():
        sys.exit(f"export first: {bundle_path.relative_to(REPO)} does not exist")

    reader = REPO / ".claude" / "skills" / "answer-bundle" / "read_bundle.py"
    python = str(CODE / ".venv" / "bin" / "python")

    sandbox = Path(tempfile.mkdtemp(prefix=f"backtest-{case.rev}-"))
    for src in (bundle_path, reader,
                CODE / "docs" / "advice-answering-guide.md",
                CODE / "docs" / "advice-schema.md"):
        shutil.copy2(src, sandbox / src.name)

    prompt = ANSWER_PROMPT.format(python=python)
    # Narrow on purpose. The session may read and write inside its throwaway
    # directory and may run the bundle reader; it has no allowance for anything
    # else, so straying outside is refused rather than merely audited after the
    # fact. The audit stays, because "refused" is a claim that should be
    # checkable too.
    cmd = [
        "claude", "-p", prompt,
        "--model", args.model,
        "--permission-mode", "acceptEdits",
        "--allowedTools", f"Bash({python} read_bundle.py:*)", "Read", "Write", "Edit",
        "--output-format", "stream-json", "--verbose",
    ]

    (case_dir(case) / "answer_command.txt").write_text(
        "# Run from a throwaway directory holding only bundle.json,\n"
        "# read_bundle.py, advice-answering-guide.md and advice-schema.md.\n"
        f"cd {sandbox}\n" + " ".join(_shell_quote(a) for a in cmd) + "\n\n"
        "# The prompt, in full:\n"
        + "".join(f"# {line}\n" for line in prompt.splitlines()),
        encoding="utf-8",
    )

    print(f"{case.rev}: answering in {sandbox}")
    transcript = case_dir(case) / "answer_transcript.jsonl"
    with transcript.open("w", encoding="utf-8") as fh:
        proc = subprocess.run(cmd, cwd=sandbox, stdout=fh, text=True)
    if proc.returncode != 0:
        sys.exit(f"claude exited {proc.returncode}; transcript in {transcript}")

    reply = sandbox / "reply.json"
    if not reply.exists():
        sys.exit(f"the session wrote no reply.json (transcript in {transcript})")
    shutil.copy2(reply, case_dir(case) / "reply.json")
    print(f"  wrote {(case_dir(case) / 'reply.json').relative_to(REPO)}")
    print(f"  transcript {transcript.relative_to(REPO)}")
    # Written now, while the sandbox path is still known — the directory is
    # throwaway and the audit has to outlive it.
    # Claude Code spills an over-long tool result to a file under its own
    # session directory in ~/.claude/projects/<mangled cwd>/ and reads it back.
    # That is the session reading its own output, so the mangled form of the
    # sandbox path is permitted alongside the interpreter.
    audit = audit_transcript(transcript, sandbox, allowed=(
        python, str(Path.home() / ".claude" / "projects" / _mangled(sandbox)),
    ))
    (case_dir(case) / "answer_audit.txt").write_text(
        "\n".join(audit) + "\n", encoding="utf-8")
    for line in audit:
        print(f"  {line}")


def _mangled(sandbox: Path) -> str:
    """The sandbox path as Claude Code names its own session directory.

    Slashes and underscores both become hyphens, so
    ``/private/var/.../backtest_R15`` is stored under
    ``~/.claude/projects/-private-var-...-backtest-R15``.
    """
    return str(sandbox.resolve()).replace("/", "-").replace("_", "-")


def _shell_quote(arg: str) -> str:
    import shlex
    return shlex.quote(arg)


def audit_transcript(
    transcript: Path, sandbox: Path, allowed: tuple[str, ...] = ()
) -> list[str]:
    """Did the blind session stay inside its sandbox? Reported, never hidden.

    Reads the tool calls the session actually made and flags any that name a
    path outside the throwaway directory. This is what makes "the answer was
    written blind" a checkable claim rather than an assurance.

    ``allowed`` are strings blanked out of each call before it is judged — the
    interpreter path is inside this repository and appears in every legitimate
    reader invocation, so leaving it in would flag all of them and the audit
    would say nothing.
    """
    if not transcript.exists():
        return ["no transcript to audit"]
    outside: list[str] = []
    tools: dict[str, int] = {}
    for raw in transcript.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        message = event.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            name = block.get("name", "?")
            tools[name] = tools.get(name, 0) + 1
            blob = json.dumps(block.get("input") or {})
            # Deleted, not masked: a command that legitimately runs the reader
            # *and* also reaches into the repository must still trip the check,
            # so only the permitted substring itself disappears.
            for permitted in allowed:
                blob = blob.replace(permitted, "")
            for token in (str(REPO), str(Path.home() / ".claude")):
                if token in blob and str(sandbox) not in blob:
                    outside.append(f"{name}: {blob[:200]}")
    lines = ["tool calls: " + ", ".join(f"{k}×{v}" for k, v in sorted(tools.items()))]
    if outside:
        lines.append(f"REACHED OUTSIDE THE SANDBOX ({len(outside)}):")
        lines += ["  " + o for o in outside[:10]]
    else:
        lines.append("sandbox audit: no tool call named a path outside it")
    return lines


def _preview_lines(preview) -> list[str]:
    def head(seq, n=8):
        # A 2D table's preview arrives as rows of cells, a 1D one as bare
        # numbers. Flatten so a matrix edit prints as values rather than
        # raising on a tuple, and say how many there were either way.
        flat = []
        for item in seq:
            if isinstance(item, (list, tuple)):
                flat.extend(item)
            else:
                flat.append(item)
        shown = ", ".join(f"{v:g}" for v in flat[:n])
        return shown + (f", … ({len(flat)} values)" if len(flat) > n else "")

    lines = [
        f"      before   : {head(preview.before)}",
        f"      requested: {head(preview.requested)}",
        f"      encoded  : {head(preview.encoded)}",
    ]
    if preview.quantized:
        lines.append(f"      quantized: max |error| {preview.max_abs_quantization:g}")
    if preview.warning:
        lines.append(f"      warning  : {preview.warning}")
    return lines


def cmd_replay(args) -> None:
    from simoscal.advice.review import review
    from simoscal.advice.schema import AdviceRejected

    case = CASES[args.rev]
    reply_path = case_dir(case) / "reply.json"
    if not reply_path.exists():
        sys.exit(f"no reply yet: {reply_path.relative_to(REPO)}")

    tune, provenance = _open_session(case)
    before = len(tune.journal.entries)
    try:
        result = review(tune, reply_path.read_text(encoding="utf-8"),
                        provenance=provenance)
    except AdviceRejected as exc:
        sys.exit(f"the whole file was refused:\n{exc}")
    assert len(tune.journal.entries) == before, "review must not journal"

    out = [
        f"# {case.rev} back-test — replay",
        "",
        f"Reply replayed against the session as it stood before {case.rev}: "
        f"`{case.state_bin.name}` with `{case.logs_dir.name}`.",
        "",
        f"**Counts** — {result.counts}",
        "",
        f"**Reply summary** — {result.summary or '(none)'}",
        "",
    ]

    out += ["## Queued — the guards accepted these", ""]
    for item in result.queued or []:
        rec = item.recommendation
        out += [
            f"### `{rec.id}` — {rec.table.label}",
            "",
            f"- table `{rec.table.name}` in space `{rec.change.space}`, "
            f"routed via {item.routed_via}",
            f"- {rec.change.operation} on {rec.change.selection.kind}"
            f"{list(rec.change.selection.args) if rec.change.selection.args else ''}",
            f"- risk **{rec.risk}**, confidence **{rec.confidence}**",
            f"- intent: {rec.intent}",
            f"- evidence: {rec.evidence}",
            f"- prediction: {rec.prediction}",
            "",
            "```",
            *_preview_lines(item.preview),
            "```",
            "",
        ]
        if item.note:
            out += [f"> {item.note}", ""]
        if item.overlaps:
            out += [f"> Overlaps: {', '.join(item.overlaps)}", ""]
    if not result.queued:
        out += ["(none)", ""]

    out += ["## Dropped — the guards refused these, in their own words", ""]
    for item in result.dropped or []:
        rec = item.recommendation
        out += [
            f"### `{rec.id}` — {rec.table.label}",
            "",
            f"- table `{rec.table.name}` in space `{rec.change.space}`"
            + (f", would have routed via {item.routed_via}" if item.routed_via else ""),
            f"- intent: {rec.intent}",
            f"- **refused:** {item.reason}",
            "",
        ]
    if not result.dropped:
        out += ["(none)", ""]

    out += ["## Malformed — rejected by the schema before any replay", ""]
    for bad in result.malformed or []:
        out += [f"### record {bad.index} (`{bad.id or 'no id'}`)", ""]
        out += [f"- {p}" for p in bad.problems] + [""]
    if not result.malformed:
        out += ["(none)", ""]

    (case_dir(case) / "replay.md").write_text("\n".join(out), encoding="utf-8")
    (case_dir(case) / "replay.json").write_text(json.dumps({
        "revision": case.rev,
        "counts": result.counts,
        "summary": result.summary,
        "schema_version": result.schema_version,
        "queued": [
            {
                "id": q.recommendation.id,
                "table": q.recommendation.table.name,
                "label": q.recommendation.table.label,
                "space": q.recommendation.change.space,
                "operation": q.recommendation.change.operation,
                "routed_via": q.routed_via,
                "risk": q.recommendation.risk,
                "confidence": q.recommendation.confidence,
                "quantized": q.preview.quantized,
                "overlaps": list(q.overlaps),
                "note": q.note,
            }
            for q in result.queued
        ],
        "dropped": [
            {
                "id": d.recommendation.id,
                "table": d.recommendation.table.name,
                "label": d.recommendation.table.label,
                "routed_via": d.routed_via,
                "reason": d.reason,
            }
            for d in result.dropped
        ],
        "malformed": [
            {"index": m.index, "id": m.id, "problems": [str(p) for p in m.problems]}
            for m in result.malformed
        ],
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"{case.rev}: {result.counts}")
    print(f"  wrote {(case_dir(case) / 'replay.md').relative_to(REPO)}")
    print(f"  journal unchanged: {len(tune.journal.entries)} entries")
    audit = case_dir(case) / "answer_audit.txt"
    if audit.exists():
        for line in audit.read_text(encoding="utf-8").splitlines():
            print(f"  {line}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="the back-tested revisions and their state")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("export", help="export the bundle for one revision")
    p.add_argument("rev", choices=sorted(CASES))
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("answer", help="run a blind claude -p session against the bundle")
    p.add_argument("rev", choices=sorted(CASES))
    p.add_argument("--model", default="opus")
    p.set_defaults(func=cmd_answer)

    p = sub.add_parser("replay", help="replay that revision's reply through the guards")
    p.add_argument("rev", choices=sorted(CASES))
    p.set_defaults(func=cmd_replay)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
