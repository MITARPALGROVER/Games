"""PythonCraft: an original, streamed voxel sandbox built with Ursina."""

from collections import deque
from math import cos, floor, inf, sin
from random import Random

from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
from ursina.shaders import unlit_shader


WORLD_SEED = 20260714
CHUNK_SIZE = 16
ACTIVE_CHUNK_RADIUS = 1
# A deeper sea gives the player enough volume to wade and swim below the surface.
SEA_LEVEL = 6
MAX_BUILD_HEIGHT = 24
REACH = 8
ATLAS = "assets/textures/block_atlas.png"
WATER_TEXTURE = "assets/textures/water.png"
SKY_COLOR = color.rgba(0.416, 0.682, 0.867, 1)

BLOCKS = ("grass", "dirt", "stone", "wood", "leaves", "sand", "water")
BLOCK_ICONS = {
    "grass": "assets/textures/grass_top.png",
    "dirt": "assets/textures/dirt.png",
    "stone": "assets/textures/stone.png",
    "wood": "assets/textures/oak_bark.png",
    "leaves": "assets/textures/oak_leaves.png",
    "sand": "assets/textures/sand.png",
    "water": WATER_TEXTURE,
}
SLOTS = {
    "grass_top": 0,
    "grass_side": 1,
    "dirt": 2,
    "stone": 3,
    "wood": 4,
    "leaves": 5,
    "sand": 6,
}

FACES = (
    ((0, 0, 1), ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1))),
    ((0, 0, -1), ((1, 0, 0), (0, 0, 0), (0, 1, 0), (1, 1, 0))),
    ((1, 0, 0), ((1, 0, 1), (1, 0, 0), (1, 1, 0), (1, 1, 1))),
    ((-1, 0, 0), ((0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0))),
    ((0, 1, 0), ((0, 1, 1), (1, 1, 1), (1, 1, 0), (0, 1, 0))),
    ((0, -1, 0), ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1))),
)
FULL_UVS = (Vec2(0, 0), Vec2(1, 0), Vec2(1, 1), Vec2(0, 1))

world_blocks = {}
chunk_positions = {}
chunk_entities = {}
loaded_chunks = set()
chunk_changes = {}
water_frontier = deque()
water_levels = {}
water_timer = 0.0
water_animation = 0.0
selected_block = "grass"
inventory = {block: 32 for block in BLOCKS}
inventory["water"] = 8
MAX_OXYGEN = 10.0
oxygen = MAX_OXYGEN
health = 20.0
hotbar_slots = []
hotbar_counts = []
inventory_open = False
current_center_chunk = None
inventory_dirty = True
camera_mode = "first"
orbit_yaw = 0.0
orbit_pitch = -8.0
orbit_target_yaw = 0.0
orbit_target_pitch = -8.0


def grid_key(position):
    return tuple(int(value) for value in position)


def chunk_key(position):
    return floor(position[0] / CHUNK_SIZE), floor(position[2] / CHUNK_SIZE)


def terrain_height(x, z):
    """Stable, continuous terrain: the same coordinates always make the same land."""
    broad_hills = sin(x * 0.14) * 2.6 + cos(z * 0.12) * 2.4
    ridges = sin((x - z) * 0.28) * 0.9
    detail = sin((x + z) * 0.55) * 0.45
    return max(1, round(4 + broad_hills + ridges + detail))


def tree_at(x, z):
    seed = (x * 92821) ^ (z * 68917) ^ WORLD_SEED
    return Random(seed).random() < 0.017


def add_chunk_block(key, position, block_type):
    """Add generated data only when it belongs to the chunk being loaded."""
    if chunk_key(position) != key:
        return
    override = chunk_changes.get(key, {}).get(position, "__generated__")
    if override is None:
        return
    actual_type = block_type if override == "__generated__" else override
    world_blocks[position] = actual_type
    chunk_positions[key].add(position)
    if actual_type == "water":
        water_levels[position] = 0 if position[1] == SEA_LEVEL else 1
        if position[1] == SEA_LEVEL:
            queue_water(position, 0)


def populate_chunk(key):
    """Generate data for one chunk. No rendering is done in this function."""
    if key in loaded_chunks:
        return

    chunk_positions[key] = set()
    chunk_x, chunk_z = key
    start_x, start_z = chunk_x * CHUNK_SIZE, chunk_z * CHUNK_SIZE

    for x in range(start_x, start_x + CHUNK_SIZE):
        for z in range(start_z, start_z + CHUNK_SIZE):
            height = terrain_height(x, z)
            beach = height <= SEA_LEVEL
            for y in range(height + 1):
                if y == height:
                    block_type = "sand" if beach else "grass"
                elif y >= height - 2:
                    block_type = "sand" if beach else "dirt"
                else:
                    block_type = "stone"
                add_chunk_block(key, (x, y, z), block_type)

            for y in range(height + 1, SEA_LEVEL + 1):
                add_chunk_block(key, (x, y, z), "water")

            if height > SEA_LEVEL + 1 and abs(x) > 4 and abs(z) > 4 and tree_at(x, z):
                for y in range(1, 5):
                    add_chunk_block(key, (x, height + y, z), "wood")
                top = height + 4
                for dx in range(-2, 3):
                    for dz in range(-2, 3):
                        for dy in range(-1, 3):
                            if abs(dx) + abs(dz) + abs(dy) <= 3:
                                position = (x + dx, top + dy, z + dz)
                                if position not in world_blocks:
                                    add_chunk_block(key, position, "leaves")

    # Player edits can also be in empty space above the generated terrain.
    for position, override in chunk_changes.get(key, {}).items():
        chunk_positions[key].add(position)
        if override is None:
            world_blocks.pop(position, None)
        else:
            world_blocks[position] = override
            if override == "water":
                water_levels[position] = 0
                queue_water(position, 0)
    loaded_chunks.add(key)


def uv_for(slot):
    """Return texture atlas UVs with a small inset to prevent seam bleeding."""
    column, row = slot % 4, slot // 4
    inset = 0.004
    left, right = column / 4 + inset, (column + 1) / 4 - inset
    bottom, top = 1 - (row + 1) / 2 + inset, 1 - row / 2 - inset
    return (Vec2(left, bottom), Vec2(right, bottom), Vec2(right, top), Vec2(left, top))


def texture_slot(block_type, normal):
    if block_type == "grass":
        if normal == (0, 1, 0):
            return SLOTS["grass_top"]
        if normal == (0, -1, 0):
            return SLOTS["dirt"]
        return SLOTS["grass_side"]
    return SLOTS[block_type]


def add_face(geometry, local_position, corners, uvs):
    vertices, triangles, texture_coords = geometry
    start = len(vertices)
    x, y, z = local_position
    vertices.extend(Vec3(x + dx, y + dy, z + dz) for dx, dy, dz in corners)
    triangles.extend((start, start + 1, start + 2, start, start + 2, start + 3))
    texture_coords.extend(uvs)


def make_mesh(geometry):
    vertices, triangles, texture_coords = geometry
    if not vertices:
        return None
    return Mesh(vertices=vertices, triangles=triangles, uvs=texture_coords, mode="triangle", static=True)


def rebuild_chunk(key):
    """Render a chunk as only exposed faces: one solid mesh plus one water mesh."""
    old_entities = chunk_entities.pop(key, ())
    for entity in old_entities:
        destroy(entity)
    if key not in loaded_chunks:
        return

    chunk_x, chunk_z = key
    origin_x, origin_z = chunk_x * CHUNK_SIZE, chunk_z * CHUNK_SIZE
    solid_geometry = ([], [], [])
    water_geometry = ([], [], [])

    for x in range(origin_x, origin_x + CHUNK_SIZE):
        for z in range(origin_z, origin_z + CHUNK_SIZE):
            for y in range(MAX_BUILD_HEIGHT + 1):
                position = (x, y, z)
                block_type = world_blocks.get(position)
                if block_type is None:
                    continue
                for normal, corners in FACES:
                    nx, ny, nz = normal
                    neighbor = world_blocks.get((x + nx, y + ny, z + nz))
                    if block_type == "water":
                        if neighbor is not None or normal == (0, -1, 0):
                            continue
                        add_face(
                            water_geometry,
                            (x - origin_x, y, z - origin_z),
                            corners,
                            FULL_UVS,
                        )
                    else:
                        if neighbor is not None:
                            continue
                        add_face(
                            solid_geometry,
                            (x - origin_x, y, z - origin_z),
                            corners,
                            uv_for(texture_slot(block_type, normal)),
                        )

    entities = []
    solid_mesh = make_mesh(solid_geometry)
    if solid_mesh:
        entities.append(
            Entity(
                parent=scene,
                model=solid_mesh,
                texture=ATLAS,
                position=(origin_x, 0, origin_z),
                collider="mesh",
                shader=unlit_shader,
                double_sided=True,
            )
        )

    water_mesh = make_mesh(water_geometry)
    if water_mesh:
        entities.append(
            Entity(
                parent=scene,
                model=water_mesh,
                texture=WATER_TEXTURE,
                position=(origin_x, 0, origin_z),
                color=color.rgba(1, 1, 1, 0.88),
                shader=unlit_shader,
                double_sided=True,
                transparent=True,
                is_water_mesh=True,
            )
        )
    chunk_entities[key] = tuple(entities)


def impacted_chunk_keys(position):
    """Return chunks whose visible edge faces can change after a block edit."""
    x, _, z = position
    keys = {chunk_key(position)}
    if x % CHUNK_SIZE == 0:
        keys.add(chunk_key((x - 1, 0, z)))
    elif x % CHUNK_SIZE == CHUNK_SIZE - 1:
        keys.add(chunk_key((x + 1, 0, z)))
    if z % CHUNK_SIZE == 0:
        keys.add(chunk_key((x, 0, z - 1)))
    elif z % CHUNK_SIZE == CHUNK_SIZE - 1:
        keys.add(chunk_key((x, 0, z + 1)))
    return keys


def rebuild_keys(keys):
    for key in keys:
        if key in loaded_chunks:
            rebuild_chunk(key)


def set_block(position, block_type=None, rebuild=True):
    """Store a player edit, so it survives chunk unloading and reloading."""
    position = grid_key(position)
    key = chunk_key(position)
    if key not in loaded_chunks:
        return False
    chunk_changes.setdefault(key, {})[position] = block_type
    chunk_positions[key].add(position)
    if block_type is None:
        world_blocks.pop(position, None)
        water_levels.pop(position, None)
    else:
        world_blocks[position] = block_type
        if block_type == "water":
            water_levels[position] = 0
        else:
            water_levels.pop(position, None)
    # Opening a wall lets neighbouring water sources flow into the new space.
    if block_type is None:
        for normal, _ in FACES:
            dx, dy, dz = normal
            neighbor = (position[0] + dx, position[1] + dy, position[2] + dz)
            if world_blocks.get(neighbor) == "water":
                queue_water(neighbor, water_levels.get(neighbor, 0))
    if rebuild:
        rebuild_keys(impacted_chunk_keys(position))
    return True


def unload_chunk(key):
    for entity in chunk_entities.pop(key, ()):
        destroy(entity)
    for position in chunk_positions.pop(key, set()):
        world_blocks.pop(position, None)
        water_levels.pop(position, None)
    loaded_chunks.discard(key)


def wanted_chunks(center):
    cx, cz = center
    return {
        (x, z)
        for x in range(cx - ACTIVE_CHUNK_RADIUS, cx + ACTIVE_CHUNK_RADIUS + 1)
        for z in range(cz - ACTIVE_CHUNK_RADIUS, cz + ACTIVE_CHUNK_RADIUS + 1)
    }


def stream_chunks(center):
    """Keep a moving square of preloaded terrain around the player forever."""
    required = wanted_chunks(center)
    removed = loaded_chunks - required
    added = required - loaded_chunks
    refresh = set()

    for key in removed:
        unload_chunk(key)
        x, z = key
        refresh.update(((x - 1, z), (x + 1, z), (x, z - 1), (x, z + 1)))
    for key in added:
        populate_chunk(key)
        x, z = key
        refresh.add(key)
        refresh.update(((x - 1, z), (x + 1, z), (x, z - 1), (x, z + 1)))
    rebuild_keys(refresh)


def raycast_block(max_distance=REACH):
    """Grid DDA targeting avoids per-block engine colliders."""
    if camera_mode == "third":
        # Aim from the avatar outward along the orbit direction so the body
        # cannot sit between the camera and the block being targeted.
        origin = Vec3(player.x, player.y + 1.55, player.z)
        direction = third_camera_pivot.forward.normalized()
    else:
        origin = camera.world_position
        direction = camera.forward.normalized()
    x, y, z = floor(origin.x), floor(origin.y), floor(origin.z)
    step_x = 1 if direction.x >= 0 else -1
    step_y = 1 if direction.y >= 0 else -1
    step_z = 1 if direction.z >= 0 else -1
    delta_x = abs(1 / direction.x) if direction.x else inf
    delta_y = abs(1 / direction.y) if direction.y else inf
    delta_z = abs(1 / direction.z) if direction.z else inf
    max_x = ((x + 1 - origin.x) if step_x > 0 else (origin.x - x)) * delta_x
    max_y = ((y + 1 - origin.y) if step_y > 0 else (origin.y - y)) * delta_y
    max_z = ((z + 1 - origin.z) if step_z > 0 else (origin.z - z)) * delta_z

    for _ in range(128):
        if max_x < max_y and max_x < max_z:
            x += step_x
            travelled, max_x, normal = max_x, max_x + delta_x, (-step_x, 0, 0)
        elif max_y < max_z:
            y += step_y
            travelled, max_y, normal = max_y, max_y + delta_y, (0, -step_y, 0)
        else:
            z += step_z
            travelled, max_z, normal = max_z, max_z + delta_z, (0, 0, -step_z)
        if travelled > max_distance:
            return None, None
        position = (x, y, z)
        if position in world_blocks:
            return position, normal
    return None, None


def add_to_inventory(block_type, amount=1):
    global inventory_dirty
    inventory[block_type] = min(99, inventory.get(block_type, 0) + amount)
    inventory_dirty = True


def queue_water(position, level=0):
    if world_blocks.get(position) != "water":
        return
    previous = water_levels.get(position)
    if previous is None or level < previous:
        water_levels[position] = level
    water_frontier.append((position, level))


def advance_water():
    """Bounded cellular-fluid simulation shared by generated and placed water."""
    global water_timer
    water_timer += time.dt
    if water_timer < 0.12 or not water_frontier:
        return
    water_timer = 0.0
    changed = set()
    for _ in range(min(12, len(water_frontier))):
        position, level = water_frontier.popleft()
        if world_blocks.get(position) != "water" or chunk_key(position) not in loaded_chunks:
            continue
        level = min(level, water_levels.get(position, level))
        x, y, z = position
        below = (x, y - 1, z)
        if y > 0 and below not in world_blocks and chunk_key(below) in loaded_chunks:
            if set_block(below, "water", rebuild=False):
                water_levels[below] = level
                queue_water(below, level)
                changed.update(impacted_chunk_keys(below))
            continue
        if level >= 4:
            continue
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            next_position = (x + dx, y, z + dz)
            if next_position not in world_blocks and chunk_key(next_position) in loaded_chunks:
                if set_block(next_position, "water", rebuild=False):
                    water_levels[next_position] = level + 1
                    queue_water(next_position, level + 1)
                    changed.update(impacted_chunk_keys(next_position))
    rebuild_keys(changed)


def player_intersects_block(position):
    """Prevent placing a block inside the player without blocking nearby placement."""
    x, y, z = position
    return (
        abs((x + 0.5) - player.x) < 0.55
        and abs((z + 0.5) - player.z) < 0.55
        # A block directly below the feet is allowed, which enables jumping/scaffolding.
        and y < player.y + 1.85
        and y + 1 > player.y + 0.22
    )


def column_surface_height(x, z):
    """Find the highest non-water block in a loaded column for a movement failsafe."""
    for y in range(MAX_BUILD_HEIGHT, -1, -1):
        block_type = world_blocks.get((x, y, z))
        if block_type is not None and block_type != "water":
            return y + 1
    return 0


def player_is_in_water():
    x, z = floor(player.x), floor(player.z)
    lower = floor(player.y)
    return any(world_blocks.get((x, lower + offset, z)) == "water" for offset in range(3))


def player_head_in_water():
    """Check the eye position, not just the feet, for drowning."""
    if camera_mode == "first":
        eye = camera.world_position
    else:
        eye = Vec3(player.x, player.y + 1.6, player.z)
    return world_blocks.get((floor(eye.x), floor(eye.y), floor(eye.z))) == "water"


def water_surface_height():
    """Find the top of the connected water column around the player."""
    x, z = floor(player.x), floor(player.z)
    y = floor(player.y)
    while y <= MAX_BUILD_HEIGHT and world_blocks.get((x, y, z)) == "water":
        y += 1
    return y


app = Ursina(title="PythonCraft")
window.borderless = False
window.exit_button.visible = False
window.fps_counter.enabled = False
window.entity_counter.enabled = False
window.collider_counter.enabled = False
camera.clip_plane_far = 240
camera.fov = 90
window.color = SKY_COLOR
camera.background_color = SKY_COLOR

# An untextured inner sky shell is reliable on the graphics drivers that failed Sky().
Entity(
    parent=camera,
    model="sphere",
    scale=180,
    color=SKY_COLOR,
    shader=unlit_shader,
    double_sided=True,
)

spawn_chunk = chunk_key((0, 0, -3))
stream_chunks(spawn_chunk)
current_center_chunk = spawn_chunk

player = FirstPersonController(position=(0, terrain_height(0, -3) + 3, -3), speed=5)
player.gravity = 0.7
player.jump_height = 1.2
player.rotation_y = 18
player.camera_pivot.rotation_x = -18
player.cursor.color = color.white
player.cursor.enabled = False

# An original voxel explorer, shown in third-person mode.
avatar = Entity(parent=player, enabled=False)
head = Entity(parent=avatar, model="cube", position=(0, 1.45, 0), scale=(0.58, 0.58, 0.58), color=color.rgba(0.95, 0.71, 0.49, 1), shader=unlit_shader)
Entity(parent=head, model="cube", position=(0, 0.2, -0.05), scale=(0.62, 0.16, 0.62), color=color.rgba(0.13, 0.07, 0.035, 1), shader=unlit_shader)
Entity(parent=head, model="quad", position=(-0.13, 0.03, -0.3), scale=(0.09, 0.1), color=color.rgba(0.04, 0.04, 0.04, 1), shader=unlit_shader, double_sided=True)
Entity(parent=head, model="quad", position=(0.13, 0.03, -0.3), scale=(0.09, 0.1), color=color.rgba(0.04, 0.04, 0.04, 1), shader=unlit_shader, double_sided=True)
Entity(parent=head, model="quad", position=(0, -0.15, -0.3), scale=(0.15, 0.04), color=color.rgba(0.35, 0.08, 0.07, 1), shader=unlit_shader, double_sided=True)
Entity(parent=avatar, model="cube", position=(0, 0.83, 0), scale=(0.65, 0.85, 0.36), color=color.rgba(0.16, 0.38, 0.72, 1), shader=unlit_shader)
Entity(parent=avatar, model="cube", position=(-0.47, 0.85, 0), scale=(0.2, 0.78, 0.24), color=color.rgba(0.95, 0.71, 0.49, 1), shader=unlit_shader)
Entity(parent=avatar, model="cube", position=(0.47, 0.85, 0), scale=(0.2, 0.78, 0.24), color=color.rgba(0.95, 0.71, 0.49, 1), shader=unlit_shader)
Entity(parent=avatar, model="cube", position=(-0.2, 0.23, 0), scale=(0.22, 0.48, 0.28), color=color.rgba(0.13, 0.18, 0.28, 1), shader=unlit_shader)
Entity(parent=avatar, model="cube", position=(0.2, 0.23, 0), scale=(0.22, 0.48, 0.28), color=color.rgba(0.13, 0.18, 0.28, 1), shader=unlit_shader)
held_item = Entity(parent=avatar, model="cube", position=(0.66, 0.66, -0.28), scale=0.32, texture=BLOCK_ICONS["grass"], shader=unlit_shader, enabled=False)

# Third-person camera is an independent orbit pivot, so it can show every side.
third_camera_pivot = Entity(parent=scene, position=(0, 1.2, 0))

# Explicit crosshair remains centered in both camera modes.
crosshair_vertical = Entity(parent=camera.ui, model="quad", position=(0, 0), scale=(0.002, 0.018), color=color.white)
crosshair_horizontal = Entity(parent=camera.ui, model="quad", position=(0, 0), scale=(0.012, 0.002), color=color.white)

hover_outline = Entity(
    parent=scene,
    model="wireframe_cube",
    scale=1.035,
    color=color.rgba(1, 0.9, 0.25, 1),
    shader=unlit_shader,
    enabled=False,
)
placement_outline = Entity(
    parent=scene,
    model="wireframe_cube",
    scale=1.045,
    color=color.rgba(0.2, 0.85, 1, 0.82),
    shader=unlit_shader,
    enabled=False,
)

# Clean HUD panels keep world state readable without debug overlays.
controls_panel = Entity(parent=camera.ui, model="quad", position=(0, 0.455), scale=(0.9, 0.075), color=color.rgba(0.035, 0.055, 0.08, 0.86))
help_text = Text(
    "WASD move   Space swim up   Ctrl dive   LMB mine   RMB place   E inventory   V camera",
    parent=camera.ui,
    position=(0, 0.455),
    origin=(0, 0),
    scale=0.82,
)

info_panel = Entity(parent=camera.ui, model="quad", position=(0.72, 0.345), scale=(0.3, 0.18), color=color.rgba(0.035, 0.055, 0.08, 0.86))
camera_text = Text("Camera: First person  [V]", parent=camera.ui, position=(0.6, 0.39), origin=(-0.5, 0), scale=0.82)
coords_text = Text("", parent=camera.ui, position=(0.6, 0.335), origin=(-0.5, 0), scale=0.82)

status_panel = Entity(parent=camera.ui, model="quad", position=(-0.72, -0.34), scale=(0.32, 0.14), color=color.rgba(0.035, 0.055, 0.08, 0.86))
selection_text = Text("", parent=camera.ui, position=(-0.86, -0.31), origin=(-0.5, 0), scale=0.78)
survival_text = Text("", parent=camera.ui, position=(-0.86, -0.365), origin=(-0.5, 0), scale=0.78)
oxygen_bar_background = Entity(parent=camera.ui, model="quad", position=(-0.86, -0.405), origin=(-0.5, 0), scale=(0.22, 0.012), color=color.rgba(0.12, 0.16, 0.2, 1))
oxygen_bar_fill = Entity(parent=camera.ui, model="quad", position=(-0.86, -0.405), origin=(-0.5, 0), scale=(0.22, 0.012), color=color.azure)

hotbar_panel = Entity(parent=camera.ui, model="quad", position=(0, -0.43), scale=(0.76, 0.115), color=color.rgba(0.035, 0.055, 0.08, 0.9))

for index, block_type in enumerate(BLOCKS):
    x = (index - 3) * 0.095
    slot = Entity(
        parent=camera.ui,
        model="quad",
        texture=BLOCK_ICONS[block_type],
        position=(x, -0.43),
        scale=(0.08, 0.08),
        color=color.rgba(1, 1, 1, 0.9),
    )
    label = Text(parent=camera.ui, text="", position=(x + 0.028, -0.405), scale=0.48, origin=(0, 0))
    hotbar_slots.append(slot)
    hotbar_counts.append(label)

inventory_panel = Entity(
    parent=camera.ui,
    model="quad",
    scale=(0.64, 0.55),
    color=color.rgba(0.1, 0.12, 0.15, 0.92),
    enabled=False,
)
inventory_title = Text(parent=camera.ui, text="INVENTORY", position=(0, 0.2), origin=(0, 0), scale=1.5, enabled=False)
inventory_list = Text(parent=camera.ui, text="", position=(-0.25, 0.05), origin=(-0.5, 0.5), scale=0.92, enabled=False)
inventory_hint = Text(parent=camera.ui, text="Press E to return", position=(0, -0.2), origin=(0, 0), scale=0.9, enabled=False)
inventory_widgets = (inventory_title, inventory_list, inventory_hint)


def refresh_inventory_ui():
    for index, block_type in enumerate(BLOCKS):
        selected = block_type == selected_block
        hotbar_slots[index].color = color.rgba(1, 0.96, 0.59, 1) if selected else color.white
        hotbar_counts[index].text = str(inventory[block_type])
    selection_text.text = f"Selected: {selected_block.title()}  ({inventory[selected_block]})"
    inventory_list.text = "\n".join(
        f"{index}.  {block_type.title():<8} {inventory[block_type]:>2}"
        for index, block_type in enumerate(BLOCKS, start=1)
    )


def toggle_inventory():
    global inventory_open
    inventory_open = not inventory_open
    inventory_panel.enabled = inventory_open
    for widget in inventory_widgets:
        widget.enabled = inventory_open
    crosshair_vertical.enabled = not inventory_open
    crosshair_horizontal.enabled = not inventory_open
    player.cursor.enabled = False
    mouse.locked = not inventory_open


def toggle_camera_mode():
    global camera_mode, orbit_yaw, orbit_pitch, orbit_target_yaw, orbit_target_pitch
    camera_mode = "third" if camera_mode == "first" else "first"
    if camera_mode == "third":
        orbit_yaw = player.rotation_y
        orbit_pitch = -8
        orbit_target_yaw = orbit_yaw
        orbit_target_pitch = orbit_pitch
        third_camera_pivot.position = player.position + Vec3(0, 1.2, 0)
        third_camera_pivot.rotation_y = orbit_yaw
        third_camera_pivot.rotation_x = orbit_pitch
        camera.parent = third_camera_pivot
        camera.position = (0, 0, -6)
        avatar.enabled = True
        camera_text.text = "Camera: Third person  [V]"
    else:
        camera.parent = player.camera_pivot
        camera.position = (0, 0, 0)
        avatar.enabled = False
        camera_text.text = "Camera: First person  [V]"


def input(key):
    global selected_block, inventory_dirty
    if key == "escape":
        application.quit()
        return
    if key == "e":
        toggle_inventory()
        return
    if key == "v":
        toggle_camera_mode()
        return
    if key in {str(index) for index in range(1, len(BLOCKS) + 1)}:
        selected_block = BLOCKS[int(key) - 1]
        inventory_dirty = True
        return
    if inventory_open:
        return

    target, normal = raycast_block()
    if key == "left mouse down" and target:
        removed = world_blocks.get(target)
        if set_block(target):
            add_to_inventory(removed)
    elif key == "right mouse down" and target and inventory[selected_block] > 0:
        placement = tuple(target[axis] + normal[axis] for axis in range(3))
        if (
            0 <= placement[1] <= MAX_BUILD_HEIGHT
            and placement not in world_blocks
            and set_block(placement, selected_block)
        ):
            inventory[selected_block] -= 1
            inventory_dirty = True
            if selected_block == "water":
                queue_water(placement)


def update():
    global current_center_chunk, water_animation, inventory_dirty, orbit_yaw, orbit_pitch, orbit_target_yaw, orbit_target_pitch, oxygen, health
    player_chunk = chunk_key((floor(player.x), 0, floor(player.z)))
    if player_chunk != current_center_chunk:
        stream_chunks(player_chunk)
        current_center_chunk = player_chunk

    # Mesh collision remains the primary collision system; this prevents a rare
    # controller fall-through from taking the player below the generated world.
    player_x, player_z = floor(player.x), floor(player.z)
    ground_height = column_surface_height(player_x, player_z)
    in_water = player_is_in_water()
    if in_water:
        player.gravity = 0
        player.speed = 3.2
        if held_keys["space"]:
            player.y += time.dt * 2.5
        elif held_keys["left control"]:
            player.y -= time.dt * 1.5
        else:
            # Buoyancy gently returns the player toward the surface.
            float_target = water_surface_height() - 1.55
            player.y = lerp(player.y, float_target, min(1, time.dt * 1.8))
    else:
        player.gravity = 0.7
        player.speed = 5
    if player.y < ground_height:
        player.y = ground_height + 0.02
        player.air_time = 0

    # Oxygen drains only when the player's eyes are below the water surface.
    if player_head_in_water():
        oxygen = max(0, oxygen - time.dt)
        if oxygen <= 0:
            health = max(0, health - time.dt * 2.5)
    else:
        oxygen = min(MAX_OXYGEN, oxygen + time.dt * 2.5)

    if health <= 0:
        spawn_position = (0, terrain_height(0, -3) + 3, -3)
        player.position = spawn_position
        stream_chunks(chunk_key(spawn_position))
        current_center_chunk = chunk_key(spawn_position)
        oxygen = MAX_OXYGEN
        health = 20.0

    coords_text.text = f"XYZ  {player.x:6.1f}  {player.y:5.1f}  {player.z:6.1f}"
    oxygen_ratio = oxygen / MAX_OXYGEN
    oxygen_bar_fill.scale_x = 0.22 * oxygen_ratio
    oxygen_bar_fill.color = color.red if oxygen <= 2 else color.azure
    survival_text.text = f"Oxygen {oxygen:>4.1f}/{MAX_OXYGEN:.0f}   Health {health:>2.0f}/20"
    survival_text.color = color.white

    if camera_mode == "third":
        # Mouse orbit is independent from movement and eased to avoid camera jumps.
        orbit_target_yaw += mouse.velocity[0] * 40
        orbit_target_pitch = clamp(orbit_target_pitch - mouse.velocity[1] * 40, -38, 28)
        smoothing = min(1, time.dt * 14)
        orbit_yaw = lerp(orbit_yaw, orbit_target_yaw, smoothing)
        orbit_pitch = lerp(orbit_pitch, orbit_target_pitch, smoothing)
        third_camera_pivot.position = player.position + Vec3(0, 1.2, 0)
        third_camera_pivot.rotation_y = orbit_yaw
        third_camera_pivot.rotation_x = orbit_pitch
        # Keep the avatar's face stable while the camera circles it.
        avatar.rotation_y = -player.rotation_y
        held_item.enabled = inventory[selected_block] > 0
        held_item.texture = BLOCK_ICONS[selected_block]
    else:
        held_item.enabled = False

    target, normal = raycast_block()
    hover_outline.enabled = bool(target) and not inventory_open
    placement_outline.enabled = bool(target) and not inventory_open
    if target:
        hover_outline.position = Vec3(*target) + Vec3(0.5, 0.5, 0.5)
        placement = tuple(target[axis] + normal[axis] for axis in range(3))
        placement_outline.position = Vec3(*placement) + Vec3(0.5, 0.5, 0.5)
        valid_placement = (
            0 <= placement[1] <= MAX_BUILD_HEIGHT
            and placement not in world_blocks
            and inventory[selected_block] > 0
        )
        placement_outline.color = color.rgba(0.2, 0.85, 1, 0.82) if valid_placement else color.rgba(1, 0.25, 0.2, 0.82)

    advance_water()
    water_animation = (water_animation + time.dt * 0.055) % 1
    for entities in chunk_entities.values():
        for entity in entities:
            if getattr(entity, "is_water_mesh", False):
                entity.texture_offset = (water_animation, water_animation * 0.35)
    if inventory_dirty:
        refresh_inventory_ui()
        inventory_dirty = False


app.run()
