# Nullius: Hurricane Reskins

Reskins Nullius buildings with [Hurricane046](https://www.figma.com/proto/y1IQG08ZG2jIeJ5sTyF4MP/Factorio-Buildings)'s
high-resolution animated sprites. Tier coloring (1 = yellow, 2 = red, 3 = blue)
is applied at load time by tinting the sprite's color/mask layer, so one sprite
set serves all tiers.

## Building → sprite mapping

| Nullius building | Replacement sprite | source folder | status |
|---|---|---|---|
| Compressor | Chemical Stager | `chemical-stager` | Done |
| Foundry | Manufacturer | `manufacturer` | Done (tier mask from color1 + emission; recipe layer pending) |
| Electrolyzer | Oxidizer | `oxidizer` | Done | 
| Hydro plant | Thermal Plant | `thermal-plant` | Done (tier mask from base-art stencil + emission + icons) |
| Air filter | Scrubber | `scrubber` | Done |
| Nanofabricator | Gravity Assembler | `atom-forge` | Done |
| Vacuum chamber | Fuel Refinery | `fuel-refinery` | Done (color1 blank, so tier mask authored from base-art stencil + emission split + recipe color2 + icons; verify shadow shift in-game) |
| Crusher | Glass Furnace | `glass-furnace` | Done (tier mask + emission + icons; recipe layer pending) |
| Flotation cell | Pathogen Lab | `pathogen-lab` | Done |
| Geothermal plant | Arc Furnace | `arc-furnace` | Done (tier mask from base-art stencil + split emission + tinted icons; in-world entity is a reactor, animated natively via working_light_picture — see "Reactor body animation") |

## Preparing assets (per building)

1. Download the sprite pack from the artist's Drive folder. You want, per
   building: the **base** animation frames, **shadow** frames, **color/mask**
   frames (the "paint job" layer), and optionally **emission/lights** frames.

2. The packs ship pre-assembled sheets (e.g. `chemical-stager-hr-animation-1.png`,
   `chemical-stager-hr-shadow.png`, `chemical-stager-hr-emission-1.png`), so
   the flow is split-then-rebuild with
   [Spritter](https://github.com/fgardt/factorio-spritter):

   ```
   # explode each sheet into frames (cols rows from the sheet grid)
   spritter split chemical-stager-hr-animation-1.png 10 10 .work/chemical-stager/base
   spritter split chemical-stager-hr-shadow.png       4  3 .work/chemical-stager/shadow
   spritter split chemical-stager-hr-emission-1.png  10 10 .work/chemical-stager/emission

   # rebuild with lua defs; NOTE the trailing hyphen on -p, the source
   # folder name supplies the layer suffix
   spritter spritesheet -l -t 64 .work/chemical-stager/base     graphics/entity/chemical-stager -p chemical-stager-
   spritter spritesheet -l -t 64 .work/chemical-stager/shadow   graphics/entity/chemical-stager -p chemical-stager-
   spritter spritesheet -l -t 64 .work/chemical-stager/emission graphics/entity/chemical-stager -p chemical-stager-
   ```

   Target file names: `<source>-base`, `<source>-shadow`, `<source>-mask`,
   `<source>-emission` (.png + .lua each). Accepted aliases:
   `mask`/`color`/`paint`, `emission`/`light`/`glow`, `shadow`/`sh`,
   `base`/`main`/`animation`.

   The loader tolerates Spritter defs without a `filename` (it synthesizes
   the path), relative filenames, `size` instead of width/height, and
   mismatched frame counts between layers (a 12-frame shadow under a
   100-frame base gets cycled automatically).

   Keep the downloaded source packs and the `.work/` frame folders OUTSIDE
   the mod folder; only the rebuilt `.png` + `.lua` pairs belong in
   `graphics/entity/`. Anything else inflates the release zip.

3. Drop the resulting `.png` + `.lua` pairs into
   `graphics/entity/<source>/`. Nothing else to wire up; the mod requires the
   `.lua` defs directly.

4. Icons (optional): put a single 64px `<source>-icon.png` in
   `graphics/icon/<source>/` and set `icon = true` on that building's entry in
   `config/buildings.lua`. This replaces the icon on the entity AND on the item
   and recipe that build it, so it shows in the inventory, crafting menu, and
   tech tree. The item/recipe names are resolved from the entity's
   `placeable_by`/`minable` (Nullius names them differently from the entity,
   e.g. entity `nullius-surge-compressor-1` → item/recipe `nullius-compressor-1`).
   For a tier-tinted icon, supply `<source>-icon-base.png` +
   `<source>-icon-mask.png` and set `icon_mask = true` instead.

## Tier pips on icons

Reskinned icons (those with `icon = true`) get a small stack of tier-coloured
dots in the **top-left** corner — one dot for tier 1, two for tier 2, three for
tier 3 — the same at-a-glance tier marker the `reskins-nullius` mod uses, made
to look identical. The loader adds them as two extra icon layers on top of
whatever icon it built (flat or tier-masked): the dot art untinted for the dark
outline, then the same art tinted with the tier colour at 0.75 alpha for the
fill, so one colour-agnostic PNG set serves every tier (`lib/reskin.lua`
`append_pips`).

The art in `graphics/icon/tiers/dots/<n>.png` (n = 1..4, the "dots" tier labels)
is reused from **reskins-framework** (MIT, © 2023 Kirazy — see Attribution
below); they are 64px mipmapped icons. The pip colours in `lib/tiers.lua`
(`pip_colors`) are matched to that mod's default tier colours so the dots read
identically; swap them for the building `colors` if you'd rather the pips match
this mod's body tints. Toggle the whole feature with the **`nvo-tier-pips`**
startup setting (default on). Pips are only added to buildings the mod already
re-icons; tiers above 4 get none (no art).

## Attribution

The tier-pip dot icons (`graphics/icon/tiers/dots/`) are taken from
[Artisanal Reskins: Framework](https://mods.factorio.com/mod/reskins-framework)
by Kirazy, used under the MIT License:

> MIT License — Copyright (c) 2023 Kirazy. Permission is hereby granted, free of
> charge, to any person obtaining a copy of this software and associated
> documentation files… (full text at the reskins-framework distribution).

## First test run

1. Install alongside Nullius. The startup setting **"Dump Nullius prototype
   info to log"** is on by default; launch the game once and open
   `factorio-current.log`.
2. Search the log for `[nvo-dump]`. You'll get every Nullius building with
   its exact prototype name, type, tile footprint, and fluid connection
   positions.
3. Correct the `pattern` fields in `config/buildings.lua` to match the real
   names (the shipped patterns are first-pass guesses).
4. Search the log for `[nullius-hurricane-reskins]` lines to see which
   buildings were reskinned and which were skipped (missing sprites, no
   pattern match, unhandled prototype type).
5. In game, place each tier of each building and check: footprint fit, tier
   colors, animation, shadow registration, and pipe connections.

## Sizing

By default each sprite is auto-scaled so its rendered width matches the
entity's collision-box width. If a building overhangs or underfills, set
`fit_factor` (e.g. `1.05`) or a manual `scale_mult` on its config entry.

## Pipes and fluid connections

Fluid box **positions, volumes, and connections** are deliberately left
untouched, so existing factories and blueprints keep all connections. What the
mod *does* change is the **cosmetic connection art** on each fluid box, and it
does so the **engine-native** way — the same mechanism vanilla Nullius itself
uses (`pipe_picture` + `pipe_covers` + `secondary_draw_orders` per fluid box).
For every reskinned building, [`lib/reskin.lua`](lib/reskin.lua) sets on each
fluid box:

- **`pipe_picture`** — an underground-pipe **stub**, a `Sprite4Way` built from the
  base-game pipe-to-ground art ([`lib/pipe_sprites.lua`](lib/pipe_sprites.lua)).
  The engine draws it at each connection and **orients it per connection**, so it
  follows rotation (R) *and* flipping (H/V) automatically.
- **`pipe_covers`** — the base-game end-**cap** (`pipecoverspictures()`). The
  engine draws it while a connection is **open** and removes it the instant a pipe
  connects (re-adding on disconnect).
- **`secondary_draw_orders = -1`** — pushes the stub **under the body**, so the
  body covers the inner half while the mouth pokes out toward the neighbour.

Because the **engine** draws these, everything is handled with **no runtime
script**: stubs/caps are drawn only at the connections the **current recipe**
actually uses, re-orient on rotate/flip, cap/uncap on pipe connect/disconnect,
and update on recipe change — none of which can go stale. (An earlier
script-drawn version reconstructed all this from live `entity.fluidbox` state but
could only re-sync on build/mine/rotate/flip, so it went stale on recipe and
connection changes; that pipe script was removed. The mod's only remaining
`control.lua` is a one-time cleanup stub — see "Reactor body animation".)

The shipped Nullius art was sized for the *original*, smaller silhouettes, so it
overlapped or floated under the larger replacement bodies; supplying art that
fits the new body is the whole fix. Everything here is **cosmetic** — fluidbox
positions, volumes, and connections are untouched, so blueprints and existing
factories keep every connection.

The **`nvo-pipe-stub-mode`** startup setting controls this:

- **`on`** (default) — install the stub + cap art described above.
- **`off`** — strip the connection art; ports render bare.

(Legacy `dynamic`/`baked` values are treated as `on`.) Set `pipe_stubs = false`
on a config entry to skip the art for one building (e.g. if its base art has
bespoke connector art); its connection art is then stripped like `off`.

A recipe-**inactive** port (one the current recipe doesn't use) shows a normal
**capped stub**, exactly as vanilla Nullius renders it — the engine draws the
stub and cap together, so there are no orphan caps.

## Reactor body animation (geothermal plant)

What the player places is `nullius-geothermal-build-N` (a mining-drill), but
Nullius destroys it on the same tick and spawns `nullius-geothermal-reactor-N` in
its place — so the in-world entity is a **reactor**. `ReactorPrototype` has no
`animation` field, but its **`working_light_picture` accepts a layered
`Animation`**, and the engine **plays it and modulates its brightness by
temperature**. That is the whole mechanism — the same one reskins-nullius uses
for this building — and it needs **no runtime script**:

- **`picture`** is the always-present cold body (a static frame from the base +
  mask + shadow). It's what shows before the reactor heats up.
- **`working_light_picture`** ([`lib/reskin.lua`](lib/reskin.lua), reactor
  branch) is built as an `Animation` from the animated **base + mask** (the body,
  shadow dropped — `picture` carries it) plus the **emission** as an additive
  layer (the trim glow). As the reactor heats, the engine fades this animated,
  glowing body in over the cold `picture` and plays it — so the plant visibly
  comes alive while it is generating heat, with the glow lit. When it cools, it
  fades back to the static `picture`.
- The fade is engine-gated on the heat buffer's `minimum_glow_temperature`
  (Nullius sets 150°, near the 250° max), so it would stay dark through most of
  the heat-up. The reactor branch lowers it to ~25° (just above ambient) so the
  animation and glow appear as soon as the reactor is generating heat. Cosmetic
  only; heat mechanics are untouched.

Because this is pure prototype data, it **survives mine/rebuild automatically** —
there is nothing to track or re-attach. (An earlier version drove the animation
from a script-managed render overlay keyed on the reactor's live temperature;
that worked but broke on rebuild — Nullius swaps the placeable stub for the
reactor inside its own build handler, before ours runs, so the new reactor was
never picked up. Going native removed the problem entirely.)

The mod has no meaningful runtime script: [`control.lua`](control.lua) only
clears the render overlays left by that earlier version when an existing save
migrates to this one. The fluid-connection art and everything else are
engine-native.

## Recipe-tinted color layer (artist paint exports)

Some newer packs ship the artist's real paint exports as **two** color layers
with different meaning — the **oxidizer** (electrolyzer) is the first:

- **`*-color1`** → the **tier** paint. Desaturated to grayscale and packed as
  the usual `<source>-mask`, then tinted yellow/red/blue per tier at load.
- **`*-color2`** → the **recipe** paint (the chemical/liquid showing in the
  machine). Desaturated and packed as a NEW `<source>-recipe` layer, drawn as a
  `working_visualisation` with `apply_recipe_tint` so the engine tints it by the
  current recipe's `crafting_machine_tint` — **only while crafting**.

Because these ship pre-painted in a low-saturation reference tone (not neutral
gray), they must be desaturated to luminance before packing or the tint reads
muddy. `tools/prep_color_layer.py` does this (the color-layer analogue of
`apply_stencil.py`):

```
spritter split oxidizer-hr-color1-1.png 8 8 .work/oxidizer/color1
spritter split oxidizer-hr-color2-1.png 8 8 .work/oxidizer/color2
python3 tools/prep_color_layer.py --frames .work/oxidizer/color1 --out .work/oxidizer/mask
python3 tools/prep_color_layer.py --frames .work/oxidizer/color2 --out .work/oxidizer/recipe
spritter spritesheet -l -t 64 .work/oxidizer/mask   graphics/entity/oxidizer -p oxidizer-
spritter spritesheet -l -t 64 .work/oxidizer/recipe graphics/entity/oxidizer -p oxidizer-
```

NOTE on frame count: the oxidizer sheets are an 8x8 grid (64 cells) but the
animation is only **60 frames** — the last 4 cells are empty. `spritter split`
writes all 64; drop the 4 trailing empties (`60.png`..`63.png`) from EVERY
animated layer (base, mask, recipe, emission) before packing so they all pack to
60 aligned frames. Leaving them in makes the building blink out on those frames
(the animation cycles through the blank cells). Confirm the empties first, e.g.:
`python3 - <<'PY'` over each layer checking `alpha.max()==0`. Emission may carry
spurious glow in those cells, so trim it to match the base's real length too.

NOTE on multi-sheet sources: some packs split one layer across **two** source
sheets (the **glass-furnace** ships `*-animation-1.png` + `*-animation-2.png`
and `*-color1-1.png` + `*-color1-2.png`; 270x310 frames, an 8x8 sheet of 64
frames plus an 8x2 sheet of 16 = **80 frames**). `spritter split` writes
`0.png`, `1.png`, ... per sheet, so split each sheet into its OWN folder, then
concatenate into one frame folder with zero-padded sequential names
(`0000.png`..`0079.png`, sheet-1 frames first) before packing — otherwise the
two sheets collide and the second half is lost or mis-ordered. Pack the merged
folder exactly like a single-sheet layer. Glass-furnace used color1 for the tier
mask this way; color2/color3/color4 are reserved for recipe colouring.

Accepted aliases for the recipe layer: `recipe`/`fluid`/`color2`. Which
`crafting_machine_tint` slot carries the fluid colour is reported by the
`[nvo-dump] recipe=...` lines (see "First test run"); override the default
`primary` with `recipe_tint_slot` on the building's `config/buildings.lua`
entry if needed. A building with no `-recipe` layer is unaffected.

Nullius's electrolyzer recipes ship **no** `crafting_machine_tint` (every
recipe line reports `tint=no`), so `apply_recipe_tint` would draw color2
colourless. `lib/recipe_tint.lua` covers this: at data stage it synthesizes
`crafting_machine_tint.primary` for each recipe in the building's crafting
categories from that recipe's representative fluid colour (brightest product
fluid, else ingredient; hue preserved, value lifted). It only touches recipes
that lack a tint, and the change is invisible to machines that don't apply it.
Set `recipe_tint_fallback = false` on the config entry to disable. The
`[nvo-dump]` / `recipe-tint:` log lines show exactly which colour each recipe
received.

## Missing color masks

Buildings WITHOUT artist paint exports (everything except the oxidizer so far)
ship animation, shadow, emission, and icons, but NO color/mask layer. Without it, tier coloring cannot work; all tiers render
identically and the log notes "no mask/color layer found". Options, in order
of preference: (1) ask the artist for the paint-layer exports he described
for newer designs, (2) author masks from the base art (isolate trim/panel
regions to a grayscale layer), (3) pre-bake three recolored base sheets per
building and ship them as separate sprite sets. The mod runs fine without
masks in the meantime.

### Authoring masks (option 2)

The mask is authored as a two-stage **stencil** workflow: paint a binary
stencil ONCE on a single frame (white = paint region), then bake it across
every base frame and pack it with Spritter. `tools/` needs Python 3 with
`pillow`, `numpy`, `scipy` (`pip3 install pillow numpy scipy`). See
[`tools/README.md`](tools/README.md) for the full tool reference; the steps
below are the end-to-end workflow.

> **Shortcut:** once a stencil exists at `sprites/<source>/<source>-stencil.png`,
> `tools/rebuild_mask.sh <source>` bakes + packs the mask and splits + packs the
> emission in one command — everything below except painting the stencil (step 2)
> and deriving icons (step 5).

1. **Split the base sheet into frames** (same Spritter step as above), e.g.
   `spritter split chemical-stager-hr-animation-1.png 10 10 .work/chemical-stager/base`.

2. **Paint a stencil** on one frame:
   - **GUI** — double-click `tools/Mask UI.command` (or `python3 tools/mask_ui.py`).
     It opens frame 0 of the base sheet. Default tool is the **Magic wand**
     (Contiguous or By-colour, Tolerance slider; click = replace, Shift+click
     adds, Alt/Option+click subtracts). **Edge-aware** is on by default so the
     wand stops at panel seams as well as colour limits (toggle "show" to overlay
     the detected edges; "Edge sensitivity" tunes it). Also **Brush**/**Eraser**,
     **Grow/Shrink 1px**, **Invert**, **Clear**, the cleanup buttons
     **De-speck / Fill holes / Smooth**, **Undo**, and **Zoom**. The **Preview**
     dropdown shows the selection as a grayscale mask or tinted in any tier
     colour from `lib/tiers.lua`. Hit **Export stencil…** to save
     `<source>-stencil.png`. To revise an existing stencil, just open its base —
     the painter auto-loads a matching `<source>-stencil.png` to edit (or use
     **Import stencil…**).
   - **CLI** — `python3 tools/mask_tool.py bootstrap --base FRAME.png --rect
     X,Y,W,H` (and/or `--near R,G,B --tol N`) `--out <source>-stencil.png` does
     the same headlessly. Run `python3 tools/mask_tool.py -h` for the other
     subcommands (`frame`, `preview`, `derive-icon`).

3. **Bake the stencil across every frame** into a `mask` folder:
   ```
   python3 tools/apply_stencil.py \
     --stencil chemical-stager-stencil.png \
     --frames .work/chemical-stager/base \
     --out    .work/chemical-stager/mask
   ```
   Inside the stencil each frame's grayscale luminance is copied (so shading
   shows through the tint); everything else is transparent. The mask edge is
   anti-aliased by `--feather` (default 1.0 px; use `0` for a hard binary edge).
   `--solid` fills flat white instead; `--brighten` (default 1.3) lifts the
   grayscale.

   When the mask is derived from the **base art** (option 2) rather than a real
   paint export, the painted region inherits the base's luminance — and on dark,
   weathered, rusty art that comes out muddy and uniform once tinted (the
   chemical-stager's masked region averages ~half the brightness of the
   scrubber's real paint layer). Two knobs fix this:
   - **`--brighten`** — raise it (e.g. `1.9`–`2.0`) so the tint reads vivid
     instead of dark. This is a uniform multiply that keeps the weathered shading.
   - **`--peel LO,HI`** — fade the paint out of the region's *dark/grimy* pixels
     so the bare metal shows through there, while the paint stays on the lit
     panel faces. This gives a "paint has peeled off the worn areas" look instead
     of a flat colour fill. The region's luminance is percentile-normalised to
     0..1 and run through `smoothstep(LO, HI)`: pixels below `LO` lose all paint,
     pixels above `HI` keep it fully. A **soft** peel of `0.15,0.55` worn the
     grime back while keeping the tier colour clearly readable; widen the band
     (`0.30,0.70` and up) for a more eroded look — but too aggressive a peel
     makes the tier hard to identify at a glance, which defeats the colouring.
     Off by default. Example (the chemical-stager bake):
     ```
     python3 tools/apply_stencil.py \
       --stencil chemical-stager-stencil.png \
       --frames .work/chemical-stager/base \
       --out    .work/chemical-stager/mask \
       --brighten 2.0 --peel 0.15,0.55
     ```

4. **Pack the mask folder** like any other layer (the folder name supplies the
   `-mask` suffix via the `mask`/`color`/`paint` alias):
   ```
   spritter spritesheet -l -t 64 .work/chemical-stager/mask \
     graphics/entity/chemical-stager -p chemical-stager-
   ```
   The loader picks up `<source>-mask.png` and tints it per tier across every
   animation frame. A single static stencil is enough for sections that don't
   move (the loader cycles the mask across the base frames).

   NOTE on alignment: this matters only when the stencil was baked onto the
   **already-cropped** `<source>-base.png` (as `rebuild_mask.sh` does — it pulls
   frames from the packed sheet). Spritter then measures the mask `shift` against
   that cropped frame, not the original cell, so it drops the base's own crop
   offset and the tier tint renders shifted off the body. `rebuild_mask.sh`
   re-registers it automatically (correct `shift` = `<source>-base.lua`'s `shift`
   plus whatever Spritter recorded for the mask); if you bake/pack the mask by
   hand from `base.png`, add the base's `shift` onto the mask's. (Baking on the
   original `.work/<source>/base` frames instead avoids this — there the shift is
   already measured against the full cell.) This is the same crop-offset issue as
   the split-emission note below.

5. **Icon** (optional) — derive the tinted icon pair from a base frame + its
   baked mask frame so the building stays the single source of truth:
   ```
   python3 tools/mask_tool.py derive-icon \
     --frame .work/chemical-stager/base/0.png \
     --mask  .work/chemical-stager/mask/0.png \
     --source chemical-stager --outdir graphics/icon/chemical-stager
   ```
   Then set `icon = true, icon_mask = true` on that building's `config/buildings.lua`
   entry. (Set `icon_mask` only once the `-icon-base.png`/`-icon-mask.png` pair
   exists, or the load will fail on the missing files.)

6. **Emission glow** (only if the building has an emission layer) — additive
   glow would otherwise wash the tier colour out of any trim that lights up. Split
   the emission by the stencil so the glow *inside* the mask is tinted per tier
   while the rest stays natural:
   ```
   python3 tools/mask_tool.py split-emission --source chemical-stager \
     --stencil chemical-stager-stencil.png \
     --out-natural .work/chemical-stager/emission-outside \
     --out-masked  .work/chemical-stager/emission-mask
   spritter spritesheet -l -t 64 .work/chemical-stager/emission-outside graphics/entity/chemical-stager -p chemical-stager-
   spritter spritesheet -l -t 64 .work/chemical-stager/emission-mask    graphics/entity/chemical-stager -p chemical-stager-
   ```
   The loader draws `<source>-emission-outside` untinted and `<source>-emission-mask`
   tinted per tier; if those two files are absent it falls back to the single
   untinted `<source>-emission`. Compare treatments first with
   `python3 tools/mask_tool.py preview-emission --source chemical-stager`. The
   original `<source>-emission.png` stays as the re-split source — it can be left
   out of the release zip once the split pair exists.

   (`tools/rebuild_mask.sh <source>` runs this split as part of the one-command
   rebuild noted at the top of this section.)

   NOTE on alignment: `split-emission` reads the **already-cropped**
   `<source>-emission.png`, so when the two split sheets are re-packed Spritter
   measures their `shift` against that cropped frame and resets it to ~`(0,0)`,
   dropping the emission's own crop offset. Left uncorrected the split glow
   renders shifted off the body and tier mask (you see a region lit *or* tinted
   but not both, the glow appearing nudged to one side). `rebuild_mask.sh`
   re-registers it automatically (correct `shift` = the emission's `shift` plus
   whatever Spritter recorded for the split); if you pack the split emission by
   hand, copy `<source>-emission.lua`'s `shift` onto both
   `<source>-emission-outside.lua` and `<source>-emission-mask.lua`.

Preview without launching the game:

- **Static**, one frame per tier:
  `python3 tools/mask_tool.py preview --base FRAME.png --mask MASKFRAME.png --out /tmp/preview`.
- **Animated**, the running building in every tier (a GIF per tier + a combined
  side-by-side GIF):
  ```
  python3 tools/mask_tool.py preview-anim \
    --frames .work/chemical-stager/base \
    --mask   .work/chemical-stager/mask \
    --out /tmp/cs-anim --fps 20 --scale 0.6
  ```
  `--mask` takes either the baked mask folder or a single mask PNG (cycled
  across the base animation). Lower `--scale` for smaller GIFs.

Note on alignment: the stencil must be painted on an actual **base animation
frame** (the in-game top-down view), not a promo/beauty render — a stencil drawn
on a different camera angle will not line up with the sprite.

## Known limitations (first pass)

- Generator/boiler-type buildings use the same animation for all rotations. If
  a real prototype turns out to be a plain generator with distinct
  horizontal/vertical art expectations, it may need a bespoke entry. (The
  geothermal plant turned out to be a mining-drill placement stub + a reactor,
  not a generator — see "Reactor body animation".)
- `working_visualisations` from the original buildings are removed (they
  reference old sprite geometry). Emission layers replace them where the
  asset pack provides one.
- Frozen-state graphics (Space Age) are not set.

## Releasing

The release zip must contain ONLY the files Factorio loads — `info.json`,
`control.lua`, `data-final-fixes.lua`, `settings.lua`, `changelog.txt`,
`thumbnail.png`, `README.md`, `LICENSE`, and the `config/`, `lib/`, `locale/`,
`graphics/` folders. Everything else in the repo (`sprites/`, `.work/`,
`showcase/`, `tools/`) is authoring material and must be excluded; the
`package.ignore` list in `info.json` encodes this for `fmtk`/the Factorio mod
tool, and the zip command below mirrors it.

1. Confirm `nvo-debug-dump` defaults to `false` in `settings.lua` (it does).
2. Bump `version` in `info.json` and add a matching `changelog.txt` block.
3. Confirm the bundled art's license still permits redistribution with
   attribution (Hurricane046 art is CC BY 4.0; see `LICENSE`).
4. Zip the folder so the archive root is `nullius-hurricane-reskins_<version>`:

   ```
   cd ..
   zip -r -X nullius-hurricane-reskins_0.1.2.zip nullius-hurricane-reskins_0.1.2 \
     -x '*/.work/*' '*/sprites/*' '*/showcase/*' '*/tools/*' \
        '*/.claude/*' '*/.git/*' '*/.gitignore' '*/.pytest_cache/*' \
        '*/__pycache__/*' '*.DS_Store' '*/.DS_Store'
   ```

The mod's internal name is `nullius-hurricane-reskins`, so the unzipped dev
folder and the zip's root folder must both be named
`nullius-hurricane-reskins_<version>` or the game will not load it.
