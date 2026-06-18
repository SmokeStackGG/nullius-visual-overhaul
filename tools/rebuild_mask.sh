#!/bin/bash
# Re-bake and re-pack a building's tier mask from its stencil.
#
# Usage:
#   tools/rebuild_mask.sh <source> [frame-index|all] [--solid] [--brighten N]
#
#   tools/rebuild_mask.sh chemical-stager          # single static mask (frame 0)
#   tools/rebuild_mask.sh chemical-stager all      # animated mask (all base frames)
#   tools/rebuild_mask.sh chemical-stager 12       # static mask from frame 12
#
# Looks for the stencil at sprites/<source>/<source>-stencil.png (falls back to
# graphics/entity/<source>/<source>-stencil.png). Writes
# graphics/entity/<source>/<source>-mask.png + .lua. Restart Factorio to see it.
set -euo pipefail
cd "$(dirname "$0")/.."

SRC="${1:?usage: rebuild_mask.sh <source> [frame-index|all] [--solid] [--brighten N]}"
MODE="${2:-0}"; [[ "$MODE" == --* ]] && MODE=0 || shift || true
shift || true                      # drop <source>; remaining args pass through
EXTRA=("$@")

SHEET="graphics/entity/$SRC/$SRC-base.png"
[[ -f "$SHEET" ]] || { echo "no base sheet: $SHEET" >&2; exit 1; }

STENCIL="sprites/$SRC/$SRC-stencil.png"
[[ -f "$STENCIL" ]] || STENCIL="graphics/entity/$SRC/$SRC-stencil.png"
[[ -f "$STENCIL" ]] || { echo "no stencil for $SRC (looked in sprites/ and graphics/)" >&2; exit 1; }

BASE=".work/$SRC/base"; MASK=".work/$SRC/mask"
rm -rf "$BASE" "$MASK"; mkdir -p "$BASE"

if [[ "$MODE" == "all" ]]; then
  N=$(python3 -c "import sys;sys.path.insert(0,'tools');from mask_tool import lua_num;print(int(lua_num(open('${SHEET%.png}.lua').read(),'sprite_count')))")
  echo "splitting all $N base frames…"
  for ((i=0;i<N;i++)); do
    python3 tools/mask_tool.py frame --sheet "$SHEET" --index "$i" \
      --out "$BASE/$(printf %04d "$i").png" >/dev/null
  done
else
  echo "extracting base frame $MODE (single static mask)…"
  python3 tools/mask_tool.py frame --sheet "$SHEET" --index "$MODE" --out "$BASE/0000.png"
fi

echo "baking mask…"
python3 tools/apply_stencil.py --stencil "$STENCIL" --frames "$BASE" --out "$MASK" ${EXTRA[@]+"${EXTRA[@]}"}

echo "packing with Spritter…"
spritter spritesheet -l -t 64 "$MASK" "graphics/entity/$SRC" -p "$SRC-"

# The stencil was baked onto the ALREADY-CROPPED base.png frames (see the
# `mask_tool.py frame --sheet "$SHEET"` calls above), so spritter measures the
# mask shift against that cropped frame and loses the base's own crop offset.
# Left uncorrected the tier tint renders shifted off the body. Restore it:
# correct shift = base_shift + spritter's recorded mask shift.
echo "re-registering mask shift to the base crop offset…"
python3 - "$SRC" <<'PY'
import sys, re, os
src = sys.argv[1]
d = f"graphics/entity/{src}"
def shift(lua):
    m = re.search(r'\["shift"\]\s*=\s*\{\s*([-\d.]+)\s*/\s*64\s*,\s*([-\d.]+)\s*/\s*64\s*\}',
                  open(lua).read())
    return float(m.group(1)), float(m.group(2))
bx, by = shift(f"{d}/{src}-base.lua")
p = f"{d}/{src}-mask.lua"
sx, sy = shift(p)
nx, ny = bx + sx, by + sy
fx = lambda v: str(int(v)) if v == int(v) else repr(v)
t = re.sub(r'(\["shift"\]\s*=\s*\{)[^}]*(\})',
           lambda m: f'{m.group(1)}{fx(nx)} / 64, {fx(ny)} / 64{m.group(2)}',
           open(p).read(), count=1)
open(p, "w").write(t)
print(f"  mask: shift -> {fx(nx)}/64, {fx(ny)}/64")
PY

# If this building has an emission layer, split it by the stencil so the glow
# inside the mask is tinted per tier (natural elsewhere) and pack both parts.
EM="graphics/entity/$SRC/$SRC-emission.png"
if [[ -f "$EM" ]]; then
  echo "splitting emission by stencil…"
  EMO=".work/$SRC/emission-outside"; EMM=".work/$SRC/emission-mask"
  rm -rf "$EMO" "$EMM"
  python3 tools/mask_tool.py split-emission --source "$SRC" --stencil "$STENCIL" \
    --out-natural "$EMO" --out-masked "$EMM"
  spritter spritesheet -l -t 64 "$EMO" "graphics/entity/$SRC" -p "$SRC-"
  spritter spritesheet -l -t 64 "$EMM" "graphics/entity/$SRC" -p "$SRC-"
  # split-emission re-packs the ALREADY-CROPPED emission sheet, so spritter
  # measures shift relative to that cropped frame and loses the emission's own
  # crop offset -- the split glow then renders shifted off the body/tier mask.
  # Restore it: correct shift = emission_shift + spritter's split shift (the
  # latter covers any extra border crop spritter applied to the split).
  echo "re-registering split emission shift to the emission crop offset…"
  python3 - "$SRC" <<'PY'
import sys, re, os
src = sys.argv[1]
d = f"graphics/entity/{src}"
def shift(lua):
    t = open(lua).read()
    m = re.search(r'\["shift"\]\s*=\s*\{\s*([-\d.]+)\s*/\s*64\s*,\s*([-\d.]+)\s*/\s*64\s*\}', t)
    return float(m.group(1)), float(m.group(2))
ex, ey = shift(f"{d}/{src}-emission.lua")
for layer in ("emission-outside", "emission-mask"):
    p = f"{d}/{src}-{layer}.lua"
    if not os.path.exists(p): continue
    sx, sy = shift(p)
    nx, ny = ex + sx, ey + sy
    t = open(p).read()
    fx = lambda v: str(int(v)) if v == int(v) else repr(v)
    t = re.sub(r'(\["shift"\]\s*=\s*\{)[^}]*(\})',
               lambda m: f'{m.group(1)}{fx(nx)} / 64, {fx(ny)} / 64{m.group(2)}', t, count=1)
    open(p, "w").write(t)
    print(f"  {layer}: shift -> {fx(nx)}/64, {fx(ny)}/64")
PY
fi

echo "done -> graphics/entity/$SRC/$SRC-mask.png  (restart Factorio to see it)"
