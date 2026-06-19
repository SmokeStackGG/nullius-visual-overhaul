-- Tier colors applied to the sprite's color/mask layer.
-- Level 1 = yellow, level 2 = red, level 3 = blue (per project spec).
-- Level 4 included as a fallback because some Nullius lines have a 4th tier.
--
-- Alpha is 0.5, not 1.0. A color-mask layer is tinted by its alpha: at 1.0 the
-- (desaturated) mask is multiplied by the colour, which oversaturates/darkens;
-- at 0.0 it draws fully additive. The base game keeps colour masks at 0.5 alpha
-- so the tint reads as a true paint colour rather than a muddy/oversaturated
-- multiply (Factorio FFF-218). This relies on our masks -- and the masked region
-- of the base under them -- being desaturated grayscale, which they are. The
-- additive emission glow is the exception: it forces alpha back to 1.0 at use
-- (lib/reskin.lua build_emission_layers), because there the tint colourises a
-- glow and wants the full hue, not a 0.5 multiply.
return {
  colors = {
    [1] = { r = 0.95, g = 0.74, b = 0.13, a = 0.5 }, -- yellow #CEA300
    [2] = { r = 0.85, g = 0.18, b = 0.12, a = 0.5 }, -- red # #FF1D00
    [3] = { r = 0.20, g = 0.46, b = 0.90, a = 0.5 }, -- blue #06C2F6
    [4] = { r = 0.58, g = 0.24, b = 0.78, a = 0.5 }, -- green #1DE635
  },
  -- Icon tinting uses the same palette unless overridden here.
  icon_colors = nil,
  -- Tier-pip dot colors. Matched to the reskins-framework "dots" default tier
  -- colors so the pips read identically to that mod (its art is reused under
  -- MIT; see graphics/icon/tiers/dots/). Swap these for `colors` above if you'd
  -- rather the pips match this mod's body tints exactly.
  pip_colors = {
    [1] = { r = 1.00, g = 0.718, b = 0.149 }, -- #ffb726
    [2] = { r = 0.949, g = 0.137, b = 0.094 }, -- #f22318
    [3] = { r = 0.20, g = 0.706, b = 1.00 }, -- #33b4ff
    [4] = { r = 0.706, g = 0.349, b = 1.00 }, -- #b459ff
  },
}
