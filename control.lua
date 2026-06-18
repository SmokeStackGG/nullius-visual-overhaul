-- control.lua
-- The geothermal reactor now animates NATIVELY: lib/reskin.lua sets the reactor's
-- working_light_picture to a layered Animation (body + emission), which the
-- engine plays and brightness-modulates by temperature. That needs no runtime
-- script and survives mine/rebuild for free (it is pure prototype data) -- the
-- same approach reskins-nullius uses.
--
-- This script exists only to clean up the render-object overlays drawn by the
-- previous (script-driven) version of this mod when an existing save migrates to
-- this one. Without this, those overlays would linger, frozen, on top of the new
-- native animation. The mod creates no render objects of its own anymore.
local function cleanup()
  -- Destroy every render object this mod created (the stale overlays); we make
  -- none now, so this is safe and idempotent. Guarded so an API hiccup can never
  -- crash load -- worst case a leftover overlay survives.
  pcall(function() rendering.clear("nullius-visual-overhaul") end)
  -- Drop the old tracking tables; harmless if already absent.
  storage.nvo_reactors = nil
  storage.nvo_pending = nil
  storage.nvo_rescan = nil
end

script.on_init(cleanup)
script.on_configuration_changed(cleanup)
