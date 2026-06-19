-- lib/reskin.lua
-- Finds Nullius prototypes by name pattern, infers tier from the trailing
-- digit, and replaces their graphics with layered animations built from
-- Spritter output. Fluid box POSITIONS/volumes/connections, collision and
-- selection boxes are left untouched so existing factories, blueprints, and pipe
-- connections keep working. The cosmetic connection art on each fluid box
-- (pipe_picture + pipe_covers) IS replaced with correctly-sized engine-native
-- art -- the engine then draws/orients/caps it per connection (see the pipe art
-- block in apply_to_proto and lib/pipe_sprites.lua); there is no runtime script.

local sprite = require("lib.sprite")
local tiers = require("lib.tiers")
local pipe_art = require("lib.pipe_sprites")

local reskin = {}

local STRICT = settings.startup["nvo-strict"]
  and settings.startup["nvo-strict"].value or false

-- Whether to install the mod's own fluid-connection art (underground stub +
-- end-cap) on each reskinned building. "off" leaves the building's connection
-- art stripped (bare). Any other value installs the engine-native art (the old
-- "dynamic"/"baked" distinction is gone -- there is no runtime script anymore).
local STUBS_OFF = (settings.startup["nvo-pipe-stub-mode"]
  and settings.startup["nvo-pipe-stub-mode"].value) == "off"

-- Prototype types Nullius uses for the buildings in scope (shared with lib/debug).
local SEARCH_TYPES = require("lib.search_types")

local function note(msg)
  log("[nullius-hurricane-reskins] " .. msg)
end

local function fail_or_note(msg)
  if STRICT then error("[nullius-hurricane-reskins] " .. msg) end
  note(msg)
end

-- Resolve the tint colour for a tier: the building's per-tier override if it
-- has one, else the shared tier palette (clamped to the last defined colour for
-- tiers beyond the palette). Used by the mask, split-emission, and icon layers.
local function tier_color(cfg, tier)
  return (cfg.tint_override and cfg.tint_override[tier])
    or tiers.colors[tier] or tiers.colors[#tiers.colors]
end

-- Infer tier from prototype name: trailing "-N". Defaults to 1.
local function tier_of(name)
  local n = name:match("%-(%d+)$")
  return n and tonumber(n) or 1
end

-- Collect all prototypes matching a Lua pattern across SEARCH_TYPES.
function reskin.find_targets(pattern)
  local found = {}
  for _, t in ipairs(SEARCH_TYPES) do
    local group = data.raw[t]
    if group then
      for name, proto in pairs(group) do
        if name:find("^nullius%-") and name:find(pattern) then
          found[#found + 1] = { proto = proto, type = t, name = name, tier = tier_of(name) }
        end
      end
    end
  end
  return found
end

-- Build the layer stack for one entity at one tier.
local function build_layers(cfg, tier, scale_mult)
  local base_def = sprite.load_def(cfg.source, "base")
  if not base_def then return nil end

  local layers = {}
  local speed = cfg.animation_speed

  layers[#layers + 1] = sprite.build_layer(base_def, {
    scale_mult = scale_mult, animation_speed = speed, extra_shift = cfg.shift,
  })

  local mask_def = sprite.load_def(cfg.source, "mask")
  if mask_def then
    local color = tier_color(cfg, tier)
    layers[#layers + 1] = sprite.build_layer(mask_def, {
      scale_mult = scale_mult, animation_speed = speed, tint = color,
      extra_shift = cfg.shift,
    })
  else
    note(cfg.source .. ": no mask/color layer found; tiers will not be color-differentiated")
  end

  local shadow_def = sprite.load_def(cfg.source, "shadow")
  if shadow_def then
    layers[#layers + 1] = sprite.build_layer(shadow_def, {
      scale_mult = scale_mult, animation_speed = speed, shadow = true,
      extra_shift = cfg.shift,
    })
  else
    note(cfg.source .. ": no shadow layer found")
  end

  return sprite.equalize_frames(layers)
end

-- Optional emission/lights as a working visualisation (only lit while crafting).
-- Emission sheets are opaque black with baked-in glows; additive blending makes
-- the black invisible and only adds the light. When the emission has been split
-- by the tier mask (tools/mask_tool.py split-emission -> -emission-outside +
-- -emission-mask), the inside-mask glow is tinted per tier so the tier colour
-- survives where the building lights up; the outside glow stays natural.
-- Otherwise the single full emission is drawn untinted (the old behaviour).
--
-- A second working visualisation is added when the source ships a recipe paint
-- layer (color2 -> -recipe): a normal-blend layer with apply_recipe_tint so the
-- engine tints it by the current recipe's crafting_machine_tint while crafting.
-- Returns a list of working_visualisation entries, or nil if none apply.
-- Build the emission/glow as equalized additive layers, tier-tinted inside the
-- mask when the emission was split (-emission-outside + -emission-mask) and
-- untinted otherwise. Returns a layer list or nil. Shared by the
-- working_visualisation path (crafting machines, mining drills) and the reactor
-- path (where the glow becomes working_light_picture instead).
local function build_emission_layers(cfg, tier, scale_mult)
  local function em_layer(def, tint)
    return sprite.build_layer(def, {
      scale_mult = scale_mult,
      glow = true,
      blend_mode = "additive",
      animation_speed = cfg.animation_speed,
      extra_shift = cfg.shift,
      tint = tint,
    })
  end

  local outside = sprite.load_def(cfg.source, "emission_outside")
  local masked = sprite.load_def(cfg.source, "emission_mask")
  if outside and masked then
    -- The tier palette carries alpha 0.5 for the normal-blend colour mask
    -- (FFF-218, see lib/tiers.lua). This is an *additive* glow, so colourise it
    -- with the full hue at alpha 1.0 -- a 0.5 alpha here would just dim the glow.
    local c = tier_color(cfg, tier)
    local color = { r = c.r, g = c.g, b = c.b, a = 1.0 }
    return sprite.equalize_frames({ em_layer(outside, nil), em_layer(masked, color) })
  end
  local em = sprite.load_def(cfg.source, "emission")
  return em and sprite.equalize_frames({ em_layer(em, nil) }) or nil
end

local function build_working_vis(cfg, tier, scale_mult)
  local vis = {}

  local em_layers = build_emission_layers(cfg, tier, scale_mult)
  if em_layers then
    vis[#vis + 1] = {
      fadeout = true,
      animation = { layers = em_layers },
    }
  end

  -- Recipe-driven paint layer (color2): drawn only while crafting and tinted by
  -- the recipe's crafting_machine_tint. Unlike the emission layers this is paint,
  -- not light, so it is a normal-blend layer (no glow/additive) with no explicit
  -- tint -- apply_recipe_tint supplies the colour from whatever is being made.
  local recipe_def = sprite.load_def(cfg.source, "recipe_tint")
  if recipe_def then
    local recipe_layer = sprite.build_layer(recipe_def, {
      scale_mult = scale_mult,
      animation_speed = cfg.animation_speed,
      extra_shift = cfg.shift,
    })
    vis[#vis + 1] = {
      apply_recipe_tint = cfg.recipe_tint_slot or "primary",
      fadeout = true,
      animation = { layers = sprite.equalize_frames({ recipe_layer }) },
    }
  end

  if #vis == 0 then return nil end
  return vis
end

-- Some Nullius prototypes (certain mirror-variant tiers) are stubs with no
-- collision box or graphics. Reskinning them is pointless and risky.
local function is_stub(proto)
  return proto.collision_box == nil
end

-- Convert an Animation (with layers) into a static Sprite (with layers) by
-- stripping animation-only fields. Reactor "picture" is a Sprite and will
-- not accept frame_count etc. Multi-file sheets collapse to the first file
-- (frame at top-left is used).
local function anim_to_sprite(anim)
  local out = { layers = {} }
  for _, l in ipairs(anim.layers) do
    local s = util.table.deepcopy(l)
    if s.filenames then
      s.filename = s.filenames[1]
      s.filenames = nil
    end
    s.frame_count = nil
    s.line_length = nil
    s.lines_per_file = nil
    s.frame_sequence = nil
    s.animation_speed = nil
    s.repeat_count = nil
    out.layers[#out.layers + 1] = s
  end
  return out
end

-- Fluid boxes live under different keys depending on prototype type
-- (fluid_boxes on crafting machines, fluid_box/output_fluid_box on boilers
-- and generators, input/output_fluid_box on mining drills).
local function each_fluid_box(proto)
  local list = {}
  for _, fb in ipairs(proto.fluid_boxes or {}) do list[#list + 1] = fb end
  for _, k in ipairs({ "fluid_box", "input_fluid_box", "output_fluid_box" }) do
    if proto[k] then list[#list + 1] = proto[k] end
  end
  return list
end

-- Resolve the scale multiplier for an entity.
local function scale_for(cfg, entry)
  if cfg.scale_mult then
    if type(cfg.scale_mult) == "table" then
      return cfg.scale_mult[entry.tier] or cfg.scale_mult[1] or 1
    end
    return cfg.scale_mult
  end
  -- Auto-fit to collision box width.
  local box = entry.proto.collision_box
  local base_def = sprite.load_def(cfg.source, "base")
  if box and base_def then
    local tiles_w = math.ceil(box[2][1] - box[1][1])
    return sprite.fit_scale(base_def, tiles_w * (cfg.fit_factor or 1.0))
  end
  return 1
end

-- Apply graphics to one prototype, handling the structural differences
-- between prototype types.
local function apply_to_proto(entry, cfg)
  local proto, ptype = entry.proto, entry.type
  local scale_mult = scale_for(cfg, entry)
  local layers = build_layers(cfg, entry.tier, scale_mult)
  if not layers then
    fail_or_note(cfg.source .. ": base sprite definition missing; skipped " .. entry.name)
    return false
  end
  local anim = { layers = layers }
  local wv = build_working_vis(cfg, entry.tier, scale_mult)

  -- Engine-native fluid-connection art. We hand each fluid box a correctly-sized
  -- underground stub (pipe_picture, a Sprite4Way the engine orients per
  -- connection) and the base-game end-cap (pipe_covers), and push them under the
  -- body with secondary_draw_orders so the body covers the inner half while the
  -- mouth pokes out. The engine then draws these at every ACTIVE connection --
  -- oriented for rotation/mirror, capped while open, hidden once a pipe connects,
  -- recipe-filtered -- with no runtime script, so nothing goes stale on recipe
  -- change or pipe connect/disconnect. The shipped art was sized for the old
  -- silhouette (it overlapped or floated); replacing it is the fix.
  --
  -- This is the same mechanism vanilla Nullius uses (pipe_picture + pipe_covers
  -- + secondary_draw_orders per fluid box); we just supply art that fits the new
  -- body. Cosmetic only: fluidbox positions, volumes, and connections are
  -- untouched, so blueprints and existing factories keep every connection.
  if STUBS_OFF or cfg.pipe_stubs == false then
    -- Stubs off / opted out: strip the old (mispositioned) art so nothing floats.
    for _, fb in ipairs(each_fluid_box(proto)) do
      fb.pipe_picture = nil
    end
  else
    local pic = pipe_art.stub_picture()
    local covers = pipe_art.covers()
    local order = { north = -1, east = -1, south = -1, west = -1 }
    for _, fb in ipairs(each_fluid_box(proto)) do
      fb.pipe_picture = pic
      fb.pipe_covers = covers
      fb.secondary_draw_orders = order
    end
  end

  if ptype == "assembling-machine" or ptype == "furnace" then
    proto.graphics_set = proto.graphics_set or {}
    proto.graphics_set.animation = anim
    proto.graphics_set.idle_animation = nil
    proto.graphics_set.always_draw_idle_animation = nil
    proto.graphics_set.working_visualisations = wv
    proto.graphics_set_flipped = nil
  elseif ptype == "mining-drill" then
    proto.graphics_set = proto.graphics_set or {}
    proto.graphics_set.animation = anim
    proto.graphics_set.working_visualisations = wv
    proto.wet_mining_graphics_set = nil
  elseif ptype == "burner-generator" or ptype == "reactor" then
    if ptype == "reactor" then
      -- Reactors animate NATIVELY through working_light_picture, which accepts a
      -- layered Animation and is played + brightness-modulated by the reactor's
      -- temperature by the engine -- no runtime script, and it survives mine/
      -- rebuild for free (it is pure prototype data). This is the technique
      -- reskins-nullius uses for the same building.
      --
      -- `picture` is the always-present cold body (a static frame); the engine
      -- fades the animated working_light_picture in on top as the reactor heats,
      -- so the body comes alive and the trim glows while it is generating heat.
      proto.picture = anim_to_sprite(anim)

      -- Lit body = animated base + mask (drop the shadow; picture carries it),
      -- plus the emission as an additive layer so the trim glows when hot.
      local lit = {}
      for _, l in ipairs(anim.layers) do
        if not l.draw_as_shadow then
          local c = util.table.deepcopy(l)
          c.animation_speed = c.animation_speed or 0.5
          lit[#lit + 1] = c
        end
      end
      local em_layers = build_emission_layers(cfg, entry.tier, scale_mult)
      if em_layers then
        for _, l in ipairs(em_layers) do
          -- draw_as_glow restricts a layer to the light pass; inside
          -- working_light_picture the engine already handles the heat fade, so
          -- keep it a plain additive layer (the emission sheet is opaque
          -- near-black, additive drops the black and adds only the highlights).
          l.draw_as_glow = nil
          l.animation_speed = l.animation_speed or 0.5
          lit[#lit + 1] = l
        end
      end
      proto.working_light_picture = { layers = sprite.equalize_frames(lit) }

      -- working_light_picture (and the reactor's point `light`) fade in from the
      -- heat buffer's minimum_glow_temperature (Nullius sets 150, near the 250
      -- max), so they stay dark through most of the heat-up. Lower it so the
      -- animated body and glow appear as soon as the reactor is generating heat.
      -- Cosmetic only; heat mechanics are untouched.
      if proto.heat_buffer then
        proto.heat_buffer.minimum_glow_temperature = 25
      end
    else
      proto.animation = anim
      proto.idle_animation = nil
    end
  elseif ptype == "boiler" then
    -- 2.0 boiler: pictures per direction. Reuse the same animation for all
    -- four; pipe connection art remains from fluid box pipe_pictures.
    proto.pictures = {
      north = { structure = anim },
      east = { structure = anim },
      south = { structure = anim },
      west = { structure = anim },
    }
  elseif ptype == "generator" then
    proto.horizontal_animation = anim
    proto.vertical_animation = anim
  else
    fail_or_note(entry.name .. " has unhandled type " .. ptype .. "; skipped")
    return false
  end

  -- Intentionally untouched: collision_box, selection_box, fluid box
  -- positions/volumes, energy_source, pipe covers.
  return true
end

local PIPS = settings.startup["nvo-tier-pips"]
  and settings.startup["nvo-tier-pips"].value
local MOD = "__nullius-hurricane-reskins__"

-- Tier pips: a stack of tier-coloured dots (one per tier) in the icon's
-- top-left corner -- the reskins-framework "dots" tier labels, reproduced
-- exactly. The art (graphics/icon/tiers/dots/, reused from reskins-framework
-- under MIT) is a colour-agnostic white dot + dark outline, mipmapped. Like the
-- framework, it is drawn as two layers: untinted for the outline, then the same
-- art tinted with the tier colour at 0.75 alpha for the fill. icon_size/scale
-- are left to match the building icon layers so the pips register identically.
-- There is no pip art beyond tier 4, so higher tiers simply get none.
local function append_pips(icons, tier)
  if not PIPS or not tier or tier < 1 or tier > 4 then return icons end
  local pc = tiers.pip_colors or tiers.colors
  local color = pc[tier] or pc[#pc]
  local pip = MOD .. "/graphics/icon/tiers/dots/" .. tier .. ".png"
  icons[#icons + 1] = { icon = pip, icon_size = 64 }
  icons[#icons + 1] = { icon = pip, icon_size = 64,
    tint = { r = color.r, g = color.g, b = color.b, a = 0.75 } }
  return icons
end

-- Build the icons table for a building. With a mask (cfg.icon_mask) the icon is
-- tinted per tier like the sprites; otherwise it is a single flat icon
-- (matching the current maskless asset set). Tier pips are appended last so
-- they sit on top.
local function build_icons(cfg, tier)
  local dir = MOD .. "/graphics/icon/" .. cfg.source .. "/"
  local size = cfg.icon_size or 64
  local icons
  if cfg.icon_mask then
    local color = tier_color(cfg, tier)
    icons = {
      { icon = dir .. cfg.source .. "-icon-base.png", icon_size = size },
      { icon = dir .. cfg.source .. "-icon-mask.png", icon_size = size, tint = color },
    }
  else
    icons = { { icon = dir .. cfg.source .. "-icon.png", icon_size = size } }
  end
  return append_pips(icons, tier)
end

local function set_icons(proto, icons)
  proto.icons = util.table.deepcopy(icons)
  proto.icon = nil
  proto.icon_size = nil
end

-- Replace icons on the entity AND on the item/recipe that build it. Nullius
-- names the item/recipe differently from the entity (entity
-- nullius-surge-compressor-1 -> item/recipe nullius-compressor-1), so resolve
-- the real item name from placeable_by/minable instead of using the entity
-- name. Recipes with no icon inherit the product's, but we set them explicitly
-- to also cover recipes that carry their own icon.
local function apply_icons(entry, cfg)
  if not cfg.icon then return end
  local icons = build_icons(cfg, entry.tier)
  set_icons(entry.proto, icons)

  local pb = entry.proto.placeable_by
  local item_name = (pb and pb.item)
    or (entry.proto.minable and entry.proto.minable.result)
  if not item_name then
    note(entry.name .. ": could not resolve item name for icon; entity icon only")
    return
  end
  for _, group in ipairs({ "item", "recipe" }) do
    local p = data.raw[group] and data.raw[group][item_name]
    if p then set_icons(p, icons) end
  end
end

-- Entry point: process one building config.
function reskin.run(cfg)
  local targets = reskin.find_targets(cfg.pattern)
  if #targets == 0 then
    fail_or_note("no Nullius prototypes matched pattern '" .. cfg.pattern .. "'")
    return
  end
  local non_stub = {}
  for _, entry in ipairs(targets) do
    if is_stub(entry.proto) then
      note("skipping stub prototype " .. entry.name .. " (no collision box/graphics)")
    elseif apply_to_proto(entry, cfg) then
      apply_icons(entry, cfg)
      non_stub[#non_stub + 1] = entry
      note(("reskinned %s (type=%s, tier=%d) with %s")
        :format(entry.name, entry.type, entry.tier, cfg.source))
    end
  end

  -- If this building has a recipe paint layer (color2 -> -recipe) but its
  -- recipes ship no crafting_machine_tint, synthesize one from each recipe's
  -- fluid colour so apply_recipe_tint has something to draw. No-op unless
  -- recipe_tint_fallback is enabled (default on) and the layer exists.
  if cfg.recipe_tint_fallback ~= false
    and #non_stub > 0
    and sprite.load_def(cfg.source, "recipe_tint") then
    require("lib.recipe_tint").populate(non_stub)
  end
end

return reskin
