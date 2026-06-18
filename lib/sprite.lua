-- lib/sprite.lua
-- Loads sprite definitions produced by fgardt/factorio-spritter (--lua flag)
-- and normalizes them into Factorio Animation layers.
--
-- Expected on-disk layout per building (SOURCE = config "source" field):
--   graphics/entity/SOURCE/SOURCE-base.png      + SOURCE-base.lua
--   graphics/entity/SOURCE/SOURCE-shadow.png    + SOURCE-shadow.lua
--   graphics/entity/SOURCE/SOURCE-mask.png      + SOURCE-mask.lua      (color/paint layer)
--   graphics/entity/SOURCE/SOURCE-emission.png  + SOURCE-emission.lua  (lights/glow, optional)
--
-- The loader is deliberately tolerant of the generated def's shape:
--   - missing filename is synthesized from the known path convention
--   - relative filenames get the __mod__ path prefixed
--   - defs nested under "animation"/"sprite"/"sheet"/"layers" are unwrapped
--   - "size" (number or {w,h}) is passed through when width/height absent
--
-- Alternate layer file names are tolerated: "color"/"paint" for "mask",
-- "light"/"glow" for "emission", "sh" for "shadow".

local MOD = "__nullius-hurricane-reskins__"

local sprite = {}

local layer_aliases = {
  base = { "base", "main", "animation" },
  shadow = { "shadow", "sh" },
  mask = { "mask", "color", "colour", "paint" },
  -- Recipe-driven paint layer (color2): a second paint region tinted at runtime
  -- by the recipe's crafting_machine_tint via a working_visualisation, so it
  -- shows the colour of whatever the machine is currently crafting. Distinct
  -- from "mask" (color1), which is the static per-tier paint.
  recipe_tint = { "recipe", "fluid", "color2" },
  emission = { "emission", "light", "glow", "lights" },
  -- Emission split by the tier mask: the part outside the mask (natural glow)
  -- and the part inside it (tinted per tier). See tools/mask_tool.py split-emission.
  emission_outside = { "emission-outside" },
  emission_mask = { "emission-mask" },
}

local function dir_for(source)
  return MOD .. "/graphics/entity/" .. source .. "/"
end

-- Strip any path, keep the bare file name.
local function basename(path)
  return (path:gsub("^.*/", ""))
end

-- Make a Spritter def usable regardless of its exact shape.
local function normalize_def(def, source, alias)
  -- Unwrap one level of nesting if the def wraps the sprite table.
  for _, k in ipairs({ "animation", "sprite", "sheet" }) do
    if type(def[k]) == "table" then
      def = def[k]
      break
    end
  end
  if type(def.layers) == "table" and def.layers[1] then
    def = def.layers[1]
  end

  local dir = dir_for(source)
  if type(def.filenames) == "table" then
    for i, f in ipairs(def.filenames) do
      if not f:find("^__") then def.filenames[i] = dir .. basename(f) end
    end
  elseif type(def.filename) == "string" then
    if not def.filename:find("^__") then
      def.filename = dir .. basename(def.filename)
    end
  else
    -- Spritter's lua output cannot know the mod path; synthesize it from
    -- our naming convention (the .png sits next to the .lua, same name).
    def.filename = dir .. source .. "-" .. alias .. ".png"
  end
  return def
end

-- Try to require a Spritter-generated definition. Returns table or nil.
local function try_require(source, layer_name)
  local path = MOD .. "/graphics/entity/" .. source .. "/" .. source .. "-" .. layer_name
  local ok, def = pcall(require, path)
  if ok and type(def) == "table" then
    return normalize_def(def, source, layer_name)
  end
  return nil
end

-- Find a definition for a logical layer, trying alias file names.
function sprite.load_def(source, logical_layer)
  for _, alias in ipairs(layer_aliases[logical_layer] or { logical_layer }) do
    local def = try_require(source, alias)
    if def then return def end
  end
  return nil
end

function sprite.frame_width(def)
  if def.width then return def.width end
  if type(def.size) == "table" then return def.size[1] end
  return def.size
end

-- Normalize a Spritter def + options into a Factorio Animation layer.
-- opts: { scale_mult, tint, shadow, glow, animation_speed, repeat_count }
function sprite.build_layer(def, opts)
  opts = opts or {}
  local layer = {
    filename = def.filename,
    filenames = def.filenames,
    lines_per_file = def.lines_per_file,
    slice = def.slice,
    width = def.width,
    height = def.height,
    size = (not def.width) and def.size or nil,
    -- Spritter names the field "sprite_count"; accept both.
    frame_count = def.frame_count or def.sprite_count or 1,
    line_length = def.line_length,
    frame_sequence = def.frame_sequence,
    shift = def.shift,
    scale = (def.scale or 0.5) * (opts.scale_mult or 1),
    animation_speed = opts.animation_speed or def.animation_speed,
    repeat_count = opts.repeat_count,
    draw_as_shadow = opts.shadow or nil,
    draw_as_glow = opts.glow or nil,
    blend_mode = opts.blend_mode,
    tint = opts.tint,
  }
  -- Scale the shift along with the sprite so layers stay registered when
  -- we resize a building to fit its footprint.
  if layer.shift and opts.scale_mult and opts.scale_mult ~= 1 then
    layer.shift = { layer.shift[1] * opts.scale_mult, layer.shift[2] * opts.scale_mult }
  end
  -- Whole-sprite offset in tiles (config "shift"), applied after scaling so
  -- it means the same on-screen distance at any sprite scale.
  if opts.extra_shift then
    local s = layer.shift or { 0, 0 }
    layer.shift = { s[1] + opts.extra_shift[1], s[2] + opts.extra_shift[2] }
  end
  return layer
end

-- Compute a scale multiplier so the base sprite's rendered width matches a
-- target footprint width in tiles. Rendered px at zoom 1 = width * scale;
-- one tile = 32 px.
function sprite.fit_scale(def, target_tiles_w)
  local w = sprite.frame_width(def)
  local rendered_tiles = (w or 0) * (def.scale or 0.5) / 32
  if rendered_tiles <= 0 then return 1 end
  return target_tiles_w / rendered_tiles
end

local function effective_frames(l)
  if l.frame_sequence then return #l.frame_sequence end
  return l.frame_count or 1
end

-- Equalize frame counts across layers. Factorio requires every layer of an
-- animation to have the same total frame count:
--   - static layers (1 frame) get repeat_count
--   - shorter animated layers (e.g. a 12-frame shadow under a 100-frame
--     base) get a frame_sequence cycling their frames up to the target
function sprite.equalize_frames(layers)
  local max_frames = 1
  for _, l in ipairs(layers) do
    local n = effective_frames(l)
    if n > max_frames then max_frames = n end
  end
  if max_frames > 1 then
    for _, l in ipairs(layers) do
      local n = effective_frames(l)
      if n == 1 then
        l.repeat_count = max_frames
      elseif n < max_frames then
        local seq = l.frame_sequence
        local fs = {}
        for i = 1, max_frames do
          if seq then
            fs[i] = seq[((i - 1) % #seq) + 1]
          else
            fs[i] = ((i - 1) % n) + 1
          end
        end
        l.frame_sequence = fs
      end
    end
  end
  return layers
end

return sprite
