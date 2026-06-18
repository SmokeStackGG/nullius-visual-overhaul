Icon sprites per building (set icon = true on the config entry):

  Single flat icon (default):   <source>/<source>-icon.png        (64x64)
  Tier-tinted (icon_mask=true): <source>/<source>-icon-base.png + -icon-mask.png

The icon replaces the entity, item, and recipe icons (inventory, crafting
menu, tech tree). Item/recipe names are resolved from the entity's
placeable_by/minable, not the entity name.
