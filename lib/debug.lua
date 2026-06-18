-- lib/debug.lua
-- Dumps every Nullius prototype in the crafting/power types to
-- factorio-current.log, with footprint and fluidbox info. Run once with the
-- "nvo-debug-dump" startup setting enabled, then read the log to correct
-- the patterns in config/buildings.lua.

local SEARCH_TYPES = require("lib.search_types")

local function box_tiles(box)
  if not box then return "?" end
  local w = box[2][1] - box[1][1]
  local h = box[2][2] - box[1][2]
  return string.format("%.1fx%.1f", w, h)
end

local function fluidbox_summary(proto)
  local fbs = proto.fluid_boxes
  if not fbs then
    -- furnaces/AMs may use fluid_boxes; boilers use fluid_box + output_fluid_box
    local n = 0
    if proto.fluid_box then n = n + 1 end
    if proto.output_fluid_box then n = n + 1 end
    return tostring(n)
  end
  local n = 0
  local conns = {}
  for _, fb in pairs(fbs) do
    if type(fb) == "table" then
      n = n + 1
      for _, pc in ipairs(fb.pipe_connections or {}) do
        local pos = pc.position or pc.positions and pc.positions[1]
        if pos then
          conns[#conns + 1] = string.format("(%.1f,%.1f)", pos[1] or pos.x, pos[2] or pos.y)
        end
      end
    end
  end
  return n .. " [" .. table.concat(conns, " ") .. "]"
end

-- Format a crafting_machine_tint slot as "r,g,b,a" or "-" when absent.
local function tint_str(c)
  if not c then return "-" end
  return string.format("%.2f,%.2f,%.2f,%.2f",
    c.r or c[1] or 0, c.g or c[2] or 0, c.b or c[3] or 0, c.a or c[4] or 1)
end

-- Dump crafting_machine_tint for recipes whose name matches a pattern, so we can
-- see which slot (primary/secondary/...) carries the fluid colour that the
-- oxidizer's recipe paint layer (color2, apply_recipe_tint) should track.
local function dump_recipe_tints(pattern)
  local recipes = data.raw["recipe"]
  if not recipes then return end
  for name, r in pairs(recipes) do
    if name:find("^nullius%-") and name:find(pattern) then
      local t = r.crafting_machine_tint
      log(string.format(
        "[nvo-dump] recipe=%s tint=%s primary=%s secondary=%s tertiary=%s quaternary=%s",
        name, t and "yes" or "no",
        tint_str(t and t.primary), tint_str(t and t.secondary),
        tint_str(t and t.tertiary), tint_str(t and t.quaternary)))
    end
  end
end

return function()
  log("[nvo-dump] ==== Nullius prototype dump start ====")
  for _, t in ipairs(SEARCH_TYPES) do
    local group = data.raw[t]
    if group then
      for name, proto in pairs(group) do
        if name:find("^nullius%-") then
          log(string.format(
            "[nvo-dump] type=%s name=%s footprint=%s fluidboxes=%s gset=%s",
            t, name, box_tiles(proto.collision_box), fluidbox_summary(proto),
            proto.graphics_set and "yes" or "no"))
        end
      end
    end
  end
  -- Verify which recipe-tint slot the electrolyzer recipes use (drives the
  -- oxidizer recipe paint layer's apply_recipe_tint; see config/buildings.lua).
  dump_recipe_tints("electrolyzer")
  log("[nvo-dump] ==== Nullius prototype dump end ====")
end
