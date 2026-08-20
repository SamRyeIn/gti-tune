#!/usr/bin/env bash
#
# sync_tunes_to_drive.sh — on-demand backup of patched tune bins + REV_LOGs to
# Google Drive (a locally-synced Finder folder, so plain file copies sync up).
#
# What it backs up:
#   1. Patched flashable bins  ->  <DRIVE>/patched/
#      Selection rule: files named  CB_HSL_SP2933_*.bin  anywhere under Tunes/,
#      EXCLUDING  _stage_*  build intermediates and the  Test/  model sandbox.
#      When a revision has several timestamped runs, only the NEWEST run's bin
#      is kept (they share a filename, so the flat folder holds one per rev).
#   2. Each tune's REV_LOG.md  ->  <DRIVE>/   (root of the simoscal tunes folder)
#      Single tune -> REV_LOG.md ; multiple tunes -> <TuneName>_REV_LOG.md.
#
# Usage:
#   ./sync_tunes_to_drive.sh            # do the backup
#   ./sync_tunes_to_drive.sh --dry-run  # show what WOULD copy, change nothing
#
# Safe by design: it only ever adds/updates files in Drive. It never deletes
# from Drive (no rsync --delete), so nothing already archived can be lost.

set -euo pipefail

REPO="/Users/sam/SimosTools"
TUNES_DIR="$REPO/Tunes"
# The Drive folder is discovered, not hardcoded. macOS names the CloudStorage
# mount after the account's email address, and this repository is public — so a
# literal path here publishes that address. Override with SIMOSCAL_DRIVE to point
# at a different account, a second Drive, or a scratch folder for testing.
DRIVE_SUBPATH="My Drive/Simos Tools/simoscal tunes"
if [[ -n "${SIMOSCAL_DRIVE:-}" ]]; then
    DRIVE="$SIMOSCAL_DRIVE"
else
    DRIVE=""
    for candidate in "$HOME/Library/CloudStorage/GoogleDrive-"*; do
        [[ -d "$candidate/$DRIVE_SUBPATH" ]] || continue
        if [[ -n "$DRIVE" ]]; then
            echo "sync_tunes_to_drive: more than one mounted Google Drive account has a" >&2
            echo "  '$DRIVE_SUBPATH' folder. Set SIMOSCAL_DRIVE to the one you mean." >&2
            exit 1
        fi
        DRIVE="$candidate/$DRIVE_SUBPATH"
    done
    if [[ -z "$DRIVE" ]]; then
        echo "sync_tunes_to_drive: no mounted Google Drive account has a" >&2
        echo "  '$DRIVE_SUBPATH' folder. Mount Drive in Finder, or set SIMOSCAL_DRIVE" >&2
        echo "  to the folder to back up into." >&2
        exit 1
    fi
fi
PATCHED_DIR="$DRIVE/patched"

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

run() {  # echo + execute (or just echo in dry-run)
    if [[ $DRY_RUN -eq 1 ]]; then
        printf '  [dry-run] %s\n' "$*"
    else
        "$@"
    fi
}

FAILED=0   # set if any Drive write was blocked (online-only folder)

# Copy one file into a Drive destination. Uses cp (not rsync) because rsync
# opens the destination dir to compare, which Google Drive blocks when a folder
# is in online-only "stream" state.
#   mode=immutable  -> skip if the dest already exists (patched bins are
#                      write-once per revision; a given filename never changes)
#   mode=overwrite  -> always (re)write (REV_LOG.md changes every revision)
# Never aborts the run: a blocked write is recorded in FAILED and reported once.
copyfile() {  # copyfile <src> <dest> <immutable|overwrite>
    local src="$1" dest="$2" mode="$3"
    if [[ "$mode" == "immutable" && -e "$dest" ]]; then
        echo "      (already in Drive — skipped)"
        return 0
    fi
    if [[ $DRY_RUN -eq 1 ]]; then
        printf '      [dry-run] cp -> %s\n' "$dest"
        return 0
    fi
    if ! cp -f "$src" "$dest" 2>/dev/null; then
        echo "      BLOCKED: Drive would not accept this write" >&2
        FAILED=1
    fi
}

echo "== SimosTools -> Google Drive backup =="
echo "Source : $TUNES_DIR"
echo "Drive  : $DRIVE"
[[ $DRY_RUN -eq 1 ]] && echo "(dry-run: no files will be written)"
echo

# --- sanity checks -----------------------------------------------------------
[[ -d "$TUNES_DIR" ]] || { echo "ERROR: Tunes dir not found: $TUNES_DIR" >&2; exit 1; }
# Confirm Drive is reachable/writable (the top folder can be un-listable while
# still being writable, so probe with a real write, not `ls`).
probe="$DRIVE/.sync_probe_$$"
if ! ( mkdir -p "$DRIVE" && : > "$probe" ) 2>/dev/null; then
    echo "ERROR: cannot write to Drive folder. Is Google Drive mounted?" >&2
    echo "       $DRIVE" >&2
    exit 1
fi
rm -f "$probe"
run mkdir -p "$PATCHED_DIR"

# --- 1. patched bins: newest run per revision --------------------------------
echo "-- Patched bins --"
# Build "rev <TAB> mtime <TAB> path" rows, then keep the newest mtime per rev.
# (bash 3.2 has no associative arrays; source paths under Tunes/ have no spaces.)
rows="$(
    find "$TUNES_DIR" \
        -path '*/Test/*' -prune -o \
        -type f -name 'CB_HSL_SP2933_*.bin' ! -name '_stage_*' -print |
    while IFS= read -r f; do
        base="${f##*/}"
        rev="$base"
        [[ "$base" =~ (R[0-9]+) ]] && rev="${BASH_REMATCH[1]}"
        printf '%s\t%s\t%s\n' "$rev" "$(stat -f %m "$f")" "$f"
    done |
    sort -t "$(printf '\t')" -k1,1 -k2,2nr |   # group by rev, newest first
    awk -F'\t' '!seen[$1]++'                    # keep first (newest) per rev
)"

if [[ -z "$rows" ]]; then
    echo "  (no patched bins found)"
else
    while IFS="$(printf '\t')" read -r rev mtime src; do
        [[ -z "$rev" ]] && continue
        echo "  $rev  <-  ${src#$REPO/}"
        copyfile "$src" "$PATCHED_DIR/${src##*/}" immutable
    done <<< "$(printf '%s' "$rows" | sort -t "$(printf '\t')" -k1,1)"
fi
echo

# --- 2. REV_LOG.md per tune --------------------------------------------------
echo "-- REV_LOG.md --"
revlogs="$(find "$TUNES_DIR" -maxdepth 2 -type f -name 'REV_LOG.md' | sort)"
count=$(printf '%s\n' "$revlogs" | grep -c . || true)
multi=0
[[ "$count" -gt 1 ]] && multi=1
if [[ "$count" -eq 0 ]]; then
    echo "  (no REV_LOG.md found)"
else
    while IFS= read -r rl; do
        [[ -z "$rl" ]] && continue
        tune="$(basename "$(dirname "$rl")")"
        if [[ $multi -eq 1 ]]; then
            dest="$DRIVE/${tune}_REV_LOG.md"
        else
            dest="$DRIVE/REV_LOG.md"
        fi
        echo "  ${tune}/REV_LOG.md  ->  $(basename "$dest")"
        copyfile "$rl" "$dest" overwrite
    done <<< "$revlogs"
fi
echo

if [[ $DRY_RUN -eq 1 ]]; then
    echo "Dry run complete — nothing was written."
elif [[ $FAILED -eq 1 ]]; then
    echo "Backup FINISHED WITH BLOCKED WRITES."
    echo
    echo "Some files could not be written because their Drive folder is set to"
    echo "'online only' (stream). New files copy fine, but existing files (e.g. an"
    echo "updated REV_LOG.md) cannot be overwritten in that state. One-time fix:"
    echo "  Finder -> Google Drive -> 'Simos Tools' (or 'simoscal tunes')"
    echo "  -> right-click -> Offline access -> Available offline, then re-run."
    exit 1
else
    echo "Backup complete."
fi
