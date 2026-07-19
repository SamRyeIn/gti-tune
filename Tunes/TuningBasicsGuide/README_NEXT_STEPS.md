# Next steps — TuningBasicsGuide

Living scratchpad for **what we want to change in upcoming tune revisions**, before
the work is scripted. One section per planned revision, newest ideas appended as
they come up. When a revision is actually built, its authoritative record moves to
`REV_LOG.md` (per-revision rationale) and the `TUNE_Basics_Guide_R<NN>.py` header
history — this file is the pre-work idea queue, not the change log.

Current lineage tip: **R12** (see `REV_LOG.md`).

Conventions: name every table as `` `ID` — Description `` (both, always). Switch-patch
tables are patch-added and have **no A2L IDs** — reference them by title. See
[[sc8s50-switchpatch-xdf]] for the switch-patch structure and per-slot table set.

---

## After the R12 human review and flash log

R12 is CAL-flash eligible because this ECU already has the R07 patch set. A full
flash is only needed if that patch/code set changes or its installed state cannot
be verified.

- Characterize the patch-added **`PUT setpoint`** grid's unlabelled Y axis
  (raw 0–7 at `0xC836`) before considering any non-tiled treatment.
- Confirm slot selection and the R09-proven `min()` behavior in-car, beginning
  with slot 1 before exercising slot 3 and finally the new slot-5 valet cap.
  Review `IP_PUT_SP` — Pressure up throttle setpoint tracking against each
  selected slot's explicit cap; slot 5 must not exceed 10 psi gauge at WOT.
- Review turbo speed, HPFP effective volume and rail hold, lambda, knock,
  `IP_PQ_CHA_MAX` — Maximum allowed pressure quotient at turbo charger
  compressor limiting, and P0234 margin. R12 retains slot 3's former 26 psi
  target and adds no fuel-system or compressor headroom.

## Future revision-script hardening

The R11 flash-guidance and checksum-report fixes are currently local to
`TUNE_Basics_Guide_R11.py`. A future script copied from R11 inherits them, but a
script copied from R07–R10 or written independently could reintroduce either
error. Before the next revision script is created:

- Centralize or explicitly enforce the flash-mode rule: a matching-patch tune is
  CAL-flash eligible only when the verified R07 patch set is already installed;
  use FULL when installing or changing the patch/code set, or when its installed
  state cannot be verified.
- Make every generated report derive its checksum wording from the final
  verification result. A failed check must say **STALE — DO NOT FLASH** and must
  never leave a report that claims `CAL_CRC` and `ECM3` are clean.
- Add a focused regression check or shared report helper so future tune scripts
  cannot silently regress either behavior, including when based on an older
  revision.
