-- Tier colors applied to the sprite's color/mask layer.
-- Level 1 = yellow, level 2 = red, level 3 = blue (per project spec).
-- Level 4 included as a fallback because some Nullius lines have a 4th tier.
return {
  colors = {
    [1] = { r = 0.95, g = 0.74, b = 0.13, a = 1.0 }, -- yellow #CEA300
    [2] = { r = 0.85, g = 0.18, b = 0.12, a = 1.0 }, -- red # #FF1D00
    [3] = { r = 0.20, g = 0.46, b = 0.90, a = 1.0 }, -- blue #06C2F6
    [4] = { r = 0.58, g = 0.24, b = 0.78, a = 1.0 }, -- green #1DE635
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
