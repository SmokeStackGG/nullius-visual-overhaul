data:extend({
  {
    type = "bool-setting",
    name = "nvo-debug-dump",
    setting_type = "startup",
    default_value = false, -- diagnostic prototype dump; off for release, flip on to debug
    order = "a",
  },
  {
    type = "bool-setting",
    name = "nvo-strict",
    setting_type = "startup",
    default_value = false,
    order = "b",
    -- when true, a missing sprite definition raises an error instead of
    -- logging and skipping. Useful once the asset set is complete.
  },
  {
    -- Fluid-connection art on reskinned buildings:
    --   on  - install the mod's engine-native underground stub + end-cap on each
    --         fluid box (pipe_picture + pipe_covers, drawn/oriented/capped by the
    --         engine per connection). Default.
    --   off - strip the connection art; ports render bare.
    -- (Legacy "dynamic"/"baked" values are treated as "on"; there is no longer a
    -- runtime script.)
    type = "string-setting",
    name = "nvo-pipe-stub-mode",
    setting_type = "startup",
    default_value = "on",
    allowed_values = { "on", "off" },
    order = "c",
  },
  {
    -- Tier pips on item/recipe/entity icons: a small stack of tier-coloured dots
    -- (1 dot = tier 1, 2 = tier 2, ...) in the icon's bottom-left corner, like
    -- the reskins-nullius mod. Only added to buildings the mod already reskins.
    type = "bool-setting",
    name = "nvo-tier-pips",
    setting_type = "startup",
    default_value = true,
    order = "d",
  },
})
