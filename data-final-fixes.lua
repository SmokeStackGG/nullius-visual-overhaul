-- data-final-fixes.lua
-- Runs after Nullius (and reskins-nullius, if present) so our overrides win.

if not data.raw["assembling-machine"] then return end

-- Bail cleanly if Nullius isn't actually loaded (belt-and-braces; the
-- dependency in info.json should guarantee it).
if not mods["nullius"] then
  log("[nullius-visual-overhaul] Nullius not present; nothing to do")
  return
end

if settings.startup["nvo-debug-dump"]
  and settings.startup["nvo-debug-dump"].value then
  require("lib.debug")()
end

local reskin = require("lib.reskin")
local buildings = require("config.buildings")

for _, cfg in ipairs(buildings) do
  reskin.run(cfg)
end
