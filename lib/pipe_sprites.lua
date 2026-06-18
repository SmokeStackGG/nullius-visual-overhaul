-- lib/pipe_sprites.lua
-- Data-stage builders for engine-native fluid-connection art. We hand the engine
-- two per-fluidbox sprites and let it do everything:
--   * pipe_picture -- an underground-pipe stub, a Sprite4Way the engine orients
--     per connection (so it follows rotation AND mirroring), drawn only at the
--     ACTIVE connections of the current recipe.
--   * pipe_covers  -- the base-game end-cap, drawn while a connection is open and
--     removed the instant a pipe connects (and re-added on disconnect).
-- Because the engine manages these, there is no runtime script and nothing can
-- go stale on recipe change, pipe connect/disconnect, rotation, or flip.

local M = {}

local PTG = "__base__/graphics/entity/pipe-to-ground/"

-- Sprite4Way underground stub: each direction's art opens that way (up = north),
-- matching how the engine keys a Sprite4Way by the connection's facing. Each is
-- shifted one tile INWARD (opposite the mouth direction) so the stub sits a tile
-- further into the body, with the mouth meeting the building edge.
function M.stub_picture()
  local function spr(file, shift)
    return {
      filename = PTG .. file,
      priority = "extra-high",
      width = 128,
      height = 128,
      scale = 0.5,
      shift = shift,
    }
  end
  return {
    north = spr("pipe-to-ground-up.png",    { 0,  1 }),
    east  = spr("pipe-to-ground-right.png", { -1, 0 }),
    south = spr("pipe-to-ground-down.png",  { 0, -1 }),
    west  = spr("pipe-to-ground-left.png",  { 1,  0 }),
  }
end

-- Base-game pipe end-caps (Sprite4Way), via the global base defines. nil if the
-- base helper is somehow unavailable (then ports simply show no cap).
function M.covers()
  if type(pipecoverspictures) == "function" then return pipecoverspictures() end
  return nil
end

return M
