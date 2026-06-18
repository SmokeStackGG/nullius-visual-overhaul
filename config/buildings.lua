-- config/buildings.lua
-- One entry per building line. Fields:
--   pattern        Lua pattern matched against Nullius prototype names
--                  (already constrained to names starting "nullius-").
--                  Tier is inferred from the trailing digit.
--   source         folder name under graphics/entity/ holding the
--                  Spritter-generated sheets + .lua defs.
--   scale_mult     optional manual scale multiplier (number, or table keyed
--                  by tier). Omit to auto-fit to collision box width.
--   fit_factor     optional tweak on the auto-fit (e.g. 1.05). Default 1.0.
--   animation_speed  optional, default from Spritter def.
--   shift          optional {x, y} offset in tiles applied to ALL sprite
--                  layers (negative y = up). Visual only; collision,
--                  selection, and fluid connections do not move.
--   pipe_stubs     false to skip the mod's fluid-connection art for this
--                  building (its pipe_picture is stripped, ports render bare);
--                  default installs the engine-native stub + cap. The global
--                  on/off switch is the nvo-pipe-stub-mode startup setting.
--   icon           true to also replace entity/item/recipe icons. Uses a
--                  single flat icon graphics/icon/<source>/<source>-icon.png.
--   icon_mask      true if a tinted base+mask icon pair is supplied instead
--                  (<source>-icon-base.png + <source>-icon-mask.png).
--   icon_size      icon pixel size (default 64).
--   tint_override  optional per-tier color table overriding lib/tiers.lua.
--   recipe_tint_slot  optional crafting_machine_tint slot ("primary" default,
--                  "secondary"/"tertiary"/"quaternary") for the recipe paint
--                  layer (color2). Confirm the slot from the [nvo-dump]
--                  recipe lines before overriding.
--   recipe_tint_fallback  set false to NOT synthesize crafting_machine_tint
--                  from recipe fluid colours when Nullius ships none (default:
--                  synthesize, so color2 is coloured). Only relevant when the
--                  source has a -recipe layer.
--
-- Patterns CONFIRMED against the Nullius 2.0.9 prototype dump (2026-06-11).
-- Footprints listed for sprite-sizing reference; auto-fit targets the
-- collision box width, art may overhang vertically.

return {
  -- nullius-surge-compressor-1..3 + nullius-priority-compressor-1..3
  -- 3.4x3.4 tiles, 2 fluid connections (diagonal corners)
  -- Nudged up so the art meets the rear (NW) pipe connection; the front
  -- (SE) connection has enough plumbing in the art to absorb the offset.
  { pattern = "compressor",     source = "chemical-stager", icon = true, icon_mask = true },

  -- nullius-foundry-1..3 | 2.6x2.6, 2 fluid connections
  -- Tier mask from color1; shadow rescaled to animation scale. Tinted icon
  -- pair derived from base+mask frame 0.
  { pattern = "foundry",        source = "manufacturer", icon = true, icon_mask = true },

  -- nullius-{surge,priority}-electrolyzer-1..3 + mirror variants
  -- 3.6x3.6, 4 fluid connections (corners)
  -- First building with the artist's real paint exports: color1 -> tier mask
  -- (per-tier tint), color2 -> recipe paint layer (apply_recipe_tint, only while
  -- crafting). recipe_tint_slot defaults to "primary"; confirm against the
  -- [nvo-dump] recipe lines.
  { pattern = "electrolyzer",   source = "oxidizer", icon = true, icon_mask = true },

  -- nullius-hydro-plant-1..3 + mirror | 4.4x4.4, 4 fluid connections
  -- Auto-fit already targets a 5-tile width (ceil(4.4)=5), filling the 5x5
  -- footprint; nudged up half a tile so the body sits centered on the grid.
  -- No artist paint export: tier mask authored from base art (option-2 stencil
  -- workflow, --brighten 1.8 --peel 0.25,0.60). Tinted icon pair derived from
  -- base+mask frame 0.
  { pattern = "hydro%-plant",   source = "thermal-plant", shift = {0, -0.5}, icon = true, icon_mask = true },

  -- nullius-air-filter-1..3 | 2.2x2.2, 1 fluid connection
  { pattern = "air%-filter",    source = "scrubber", icon = true, icon_mask = true },

  -- nullius-nanofabricator-1..2 + mirror | 3.5x3.5, 4 fluid connections
  -- NOTE: only tiers 1-2 exist (yellow/red)
  -- Artist paint export: color1 -> tier mask (per-tier tint). No color2/recipe
  -- layer. emission1+emission2 combined into one -emission glow (lit only while
  -- crafting). Tinted icon pair derived from base+mask frame 0.
  { pattern = "nanofabricator", source = "atom-forge", icon = true, icon_mask = true },

  -- nullius-vacuum-chamber-1..3 | 2.4x2.4, 4 fluidboxes / 6 connections
  -- color1 (tier paint) shipped BLANK, so the tier mask was authored from base
  -- art (option-2 stencil on the yellow tank;
  -- rebuild_mask.sh fuel-refinery all --brighten 1.3 -- no peel: the tank's own
  -- shading reads cleaner as solid paint; peel mottled the mid-tones).
  -- color2 -> recipe paint layer (small glowing-tip region, apply_recipe_tint
  -- while crafting). emission1+emission2 combined into one -emission glow, then
  -- split by the stencil (-emission-outside natural + -emission-mask tinted).
  -- Tinted icon pair derived from base+mask frame 0. Single static shadow
  -- (centered; verify shift in-game).
  { pattern = "vacuum",         source = "fuel-refinery", icon = true, icon_mask = true },

  -- nullius-crusher-1..3 | 2.4x2.4, 2 fluid connections
  -- Artist paint export: 80-frame animation across two source sheets
  -- (animation-1 8x8 + animation-2 8x2, 270x310 frames). color1 -> tier mask
  -- (per-tier tint). color2/color3/color4 are the recipe paint layers, reserved
  -- for recipe-specific colouring (not yet wired; no -recipe layer). emission1
  -- (warm molten-glass glow) + emission2 (green indicator/pipe glow) combined
  -- additively into one untinted -emission, drawn as a working_visualisation
  -- (lit only while crafting). Tinted icon pair derived from base+mask frame
  -- (icon = true, icon_mask = true).
  { pattern = "crusher",        source = "glass-furnace", icon = true, icon_mask = true },

  -- nullius-flotation-cell-1..3 + mirror | 3.5x3.5, 4 fluid connections
  -- No artist paint export: tier mask authored from base art (option-2 stencil
  -- workflow). 8x8 sheet, 60 real frames (cells 60-63 empty, trimmed). Emission
  -- split by stencil. Tinted icon pair derived from base+mask frame 0.
  { pattern = "flotation",      source = "pathogen-lab", icon = true, icon_mask = true },

  -- nullius-geothermal-build-1..3 (mining-drill, animated) AND
  -- nullius-geothermal-reactor-1..3 (reactor) | 4.8x4.8
  -- Animation 8x7 sheet, 50 real frames (cells 50-55 empty, trimmed from base
  -- AND emission); single static shadow; emission split by stencil. Tier mask
  -- authored from base art (option-2 stencil workflow). Tinted icon pair derived
  -- from base+mask frame 0 (icon = true, icon_mask = true).
  --
  -- The in-world entity is the REACTOR (geothermal-build is a placement stub
  -- Nullius swaps for geothermal-reactor on the same tick). Reactors animate
  -- natively via working_light_picture (an Animation the engine plays + fades by
  -- temperature) -- no runtime script; see README "Reactor body animation". The
  -- item/recipe both resolve to nullius-geothermal-plant-N for the icon.
  { pattern = "geothermal",     source = "arc-furnace", icon = true, icon_mask = true },
}
