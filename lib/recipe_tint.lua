-- lib/recipe_tint.lua
-- Fallback for buildings whose recipe paint layer (color2 -> -recipe) uses
-- apply_recipe_tint but whose recipes ship NO crafting_machine_tint (confirmed
-- for the Nullius electrolyzer: every electrolysis recipe reports tint=no in the
-- [nvo-dump]). Without a tint the layer would draw colourless, so we synthesize
-- crafting_machine_tint.primary from each recipe's representative fluid colour.
--
-- Scope: only recipes in the reskinned building's own crafting categories, and
-- only when they don't already define a tint. Setting crafting_machine_tint on a
-- recipe is harmless to machines that don't apply_recipe_tint, so this never
-- affects other buildings' visuals.

local recipe_tint = {}

local function note(msg)
  log("[nullius-visual-overhaul] " .. msg)
end

-- Normalize a Color (named or array form) to {r,g,b,a} floats in 0..1.
local function as_rgba(c)
  if not c then return nil end
  local r = c.r or c[1] or 0
  local g = c.g or c[2] or 0
  local b = c.b or c[3] or 0
  local a = c.a or c[4] or 1
  -- Factorio accepts 0..255 colours; treat >1 on any channel as 8-bit.
  if r > 1 or g > 1 or b > 1 then r, g, b = r / 255, g / 255, b / 255 end
  return { r = r, g = g, b = b, a = a }
end

-- Scale a colour so its brightest channel is 1, preserving hue. Fluid
-- base_colors are often dark; apply_recipe_tint multiplies the (already dim)
-- grayscale paint by the tint, so a dark tint would vanish. Full-value keeps
-- the chemical's hue while staying readable.
local function vivid(c)
  local m = math.max(c.r, c.g, c.b)
  if m <= 0 then return c end
  local k = 1 / m
  return { r = c.r * k, g = c.g * k, b = c.b * k, a = c.a or 1 }
end

-- Representative fluid colour for a recipe: prefer the highest-amount fluid
-- product, else the highest-amount fluid ingredient. Returns {r,g,b,a} or nil.
local function recipe_fluid_color(recipe)
  local function best_fluid(list)
    local best, best_amt
    for _, it in ipairs(list or {}) do
      if it.type == "fluid" and it.name then
        local f = data.raw.fluid and data.raw.fluid[it.name]
        if f then
          local amt = it.amount or it.amount_max or 1
          if not best_amt or amt > best_amt then best, best_amt = f, amt end
        end
      end
    end
    return best
  end
  local f = best_fluid(recipe.results) or best_fluid(recipe.ingredients)
  if not f then return nil end
  local c = as_rgba(f.base_color) or as_rgba(f.flow_color)
  return c and vivid(c) or nil
end

-- Union of crafting categories used by a set of building prototypes.
local function categories_of(targets)
  local set = {}
  for _, entry in ipairs(targets) do
    for _, cat in ipairs(entry.proto.crafting_categories or {}) do
      set[cat] = true
    end
  end
  return set
end

-- Populate crafting_machine_tint.primary on every recipe in `targets`' crafting
-- categories that lacks a tint, derived from the recipe's fluid colour.
function recipe_tint.populate(targets)
  local cats = categories_of(targets)
  if not next(cats) then
    note("recipe-tint: no crafting categories on targets; skipped")
    return
  end
  local cat_list = {}
  for c in pairs(cats) do cat_list[#cat_list + 1] = c end
  note("recipe-tint: categories " .. table.concat(cat_list, ", "))

  local applied, skipped = 0, 0
  for name, r in pairs(data.raw.recipe or {}) do
    local cat = r.category or "crafting"
    if cats[cat] and not r.crafting_machine_tint then
      local color = recipe_fluid_color(r)
      if color then
        r.crafting_machine_tint = { primary = color }
        applied = applied + 1
        note(string.format("recipe-tint: %s <- (%.2f,%.2f,%.2f)",
          name, color.r, color.g, color.b))
      else
        skipped = skipped + 1
      end
    end
  end
  note(string.format("recipe-tint: applied %d, no-fluid %d", applied, skipped))
end

return recipe_tint
