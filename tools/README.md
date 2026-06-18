# tools/ — tier-mask authoring

Helpers for authoring the per-tier **color/mask** layer (and tinting the
emission glow to match) for Nullius: Visual Overhaul, plus previewing the result
in the tier colors without launching Factorio. See the repo `README.md`
("Authoring masks") for how this fits the asset pipeline; this file is the
reference for the tools themselves.

## Requirements

Python 3 with `pillow`, `numpy`, `scipy`:

```
pip3 install pillow numpy scipy
```

Packing the authored frames into sprite sheets uses
[Spritter](https://github.com/fgardt/factorio-spritter) (`spritter` on PATH),
the same tool the rest of the assets are built with.

## The model

Tier coloring works by drawing a grayscale **mask** layer (transparent except
the trim you want colored) on top of the base art, tinted per tier at load time
(`lib/tiers.lua`). You author it as a two-stage **stencil** flow:

1. Paint a **binary stencil** ONCE on a single base frame (white = paint region).
2. **Bake** the stencil across the base frames → grayscale mask frames, then
   pack with Spritter.

A single static stencil is enough for trim that doesn't move; the loader cycles a
1-frame mask across the whole animation.

```
base sheet ──split──► .work/<src>/base/*.png
                            │
   paint stencil (GUI) ─────► <src>-stencil.png      (binary, authored once)
                            │
apply_stencil.py ───────────► .work/<src>/mask/*.png (luma inside, transparent out)
                            │
spritter ───────────────────► graphics/entity/<src>/<src>-mask.png + .lua
```

## Quick start

Once a building's stencil exists at `sprites/<source>/<source>-stencil.png`,
one command rebuilds everything (mask + emission split) and packs it:

```
tools/rebuild_mask.sh chemical-stager
```

Then **restart Factorio** (sprites load at startup). Variations:

```
tools/rebuild_mask.sh chemical-stager all          # bake mask across all frames
tools/rebuild_mask.sh chemical-stager 12           # author off base frame 12
tools/rebuild_mask.sh chemical-stager 0 --brighten 1.6   # punchier tint
tools/rebuild_mask.sh chemical-stager 0 --feather 0      # hard (non-AA) edge
tools/rebuild_mask.sh chemical-stager 0 --solid          # flat color, no shading
```

## Files

| File | What it is |
|---|---|
| `mask_ui.py` | GUI stencil **painter** (tkinter). Author and export the binary stencil. |
| `Mask UI.command` | Double-click launcher for `mask_ui.py`. |
| `apply_stencil.py` | Bake a stencil across base frames into grayscale mask frames. |
| `mask_tool.py` | CLI: headless stencil, frame extraction, previews, emission split, icons. |
| `mask_ops.py` | Pure (GUI-free) image ops shared by the above; unit-tested. |
| `rebuild_mask.sh` | One-command rebuild: bake + pack mask, split + pack emission. |
| `test_*.py` | `pytest` suite for the pure logic. |

Module layering is acyclic: `mask_ops` (pure numpy/scipy) ← `apply_stencil` /
`mask_tool` ← `mask_ui` (GUI).

## mask_ui.py — the painter

Double-click `Mask UI.command` or run `python3 tools/mask_ui.py`. Opens frame 0
of the chemical-stager base sheet by default; use **Open base…** for another.

To **edit an existing stencil**, just open its base: the painter auto-loads a
matching `<source>-stencil.png` (sibling of the base, or `sprites/<source>/`) as
the starting selection, so you tweak it and re-export. **Import stencil…** loads
any stencil PNG onto the current frame (resized to fit if needed); **Clear**
starts fresh.

- **Magic wand** — Contiguous or By-colour, Tolerance slider. Click = replace,
  Shift+click = add, Alt/Option+click = subtract. **Edge-aware** (default on)
  stops the flood at panel seams as well as colour limits; "show" overlays the
  detected edges and "Edge sensitivity" tunes the threshold.
- **Brush / Eraser** with a size slider.
- **Refine** — Grow / Shrink 1px, Invert, Clear, and **De-speck / Fill holes /
  Smooth**; Undo (Cmd/Ctrl+Z).
- **Zoom** (scrollable).
- **Preview** dropdown — Edit overlay, grayscale Mask, or any tier color from
  `lib/tiers.lua` (with swatch).
- **Export stencil…** — writes the binary `<source>-stencil.png`.

## apply_stencil.py

```
python3 tools/apply_stencil.py --stencil S.png --frames FRAMES_DIR --out OUT_DIR
                               [--brighten 1.3] [--solid] [--feather 1.0]
```

For each base frame, copies grayscale luminance inside the stencil (so shading
shows through the tint), transparent elsewhere. `--feather` anti-aliases the
boundary (`0` = hard binary). `--solid` fills flat white. The stencil is
auto-resized (nearest) to the frame size if needed.

## mask_tool.py subcommands

Run `python3 tools/mask_tool.py <cmd> -h` for full flags.

| Subcommand | Purpose |
|---|---|
| `frame` | Extract one frame from a packed Spritter sheet (reads geometry from the sibling `.lua`). |
| `bootstrap` | Headless stencil maker — select by `--rect X,Y,W,H` and/or `--near R,G,B --tol N`, write a binary stencil. |
| `preview` | Composite base + tinted mask per tier → PNGs + a side-by-side strip. |
| `preview-anim` | Animated version — a looping GIF per tier plus a combined side-by-side GIF. |
| `preview-emission` | Compare emission-glow treatments (no-glow / current untinted / whole-tinted / mask-only-tinted), one strip per tier, from the packed graphics. |
| `split-emission` | Split the packed emission into `outside` (natural) + `masked` (tinted per tier) frame folders. |
| `derive-icon` | Make the tinted icon pair (`-icon-base.png` + `-icon-mask.png`) from a base frame + its baked mask. |

## Emission glow

Additive emission would wash the tier color out of any trim that lights up.
`split-emission` (run automatically by `rebuild_mask.sh`) splits the glow so the
part **inside** the mask is tinted per tier while the rest stays natural; the
loader (`lib/reskin.lua`) draws `<src>-emission-outside` untinted and
`<src>-emission-mask` tinted, falling back to the single untinted
`<src>-emission` if the split pair is absent. Compare options first with
`preview-emission`. The original `<src>-emission.png` stays as the re-split
source and can be left out of the release zip once the split pair exists.

## Tests

```
python3 -m pytest tools/
```

Covers the pure logic in `mask_ops.py` and `apply_stencil.py` (selection,
feathering, cleanup, emission split, frame placement). GUI code in `mask_ui.py`
is not unit-tested.

## Notes

- Author the stencil on an **actual base animation frame** (the in-game
  top-down view), not a promo/beauty render — a stencil on a different camera
  angle won't line up.
- Keep `.work/` and the downloaded source packs OUT of the mod folder; only the
  packed `.png` + `.lua` pairs in `graphics/entity/<source>/` ship.
