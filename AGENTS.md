# SimosTools instructions

Read [`CLAUDE.md`](CLAUDE.md) before performing ECU-tuning work. It is the
canonical project guide and defines the required boot reading order, safety
constraints, revision workflow, log interpretation rules, and naming
conventions.

Key constraints:

- This repository performs programmatic ECU calibration only. Never flash an
  ECU; flashing and the final review gate are human-only steps.
- Preserve `Code/bin/5G0906259L__0002.bin` as the untouched recovery image.
- Treat existing working-tree changes as user work. Do not revert or overwrite
  them unless explicitly asked.
- `Code/` is an independent nested repository. Check its status separately
  when working on the `simoscal` library.
- For table references, use both the parameter ID and its plain-English
  description as required by `CLAUDE.md`.

Do not create a second rule set here. Update `CLAUDE.md` when project policy or
the detailed workflow changes; keep this file as the Codex entry point.
