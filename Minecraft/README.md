# PythonCraft

An original Minecraft-style voxel sandbox written in Python with [Ursina](https://www.ursinaengine.org/).

## Run it

From this folder:

```powershell
python -m pip install -r requirements.txt
python main.py
```

## Controls

- `W`, `A`, `S`, `D` — move
- Mouse — look around
- `Space` — jump
- Left-click — break a block
- Right-click — place the selected block
- `1`–`7` — select grass, dirt, stone, oak, leaves, sand, or water
- `Esc` — quit

The current build streams chunks around the player, so the generated world continues as you travel instead of ending at a fixed map boundary. It includes a seven-slot inventory, original terrain textures, collision-based first-person movement, mining/placing, and a bounded water-flow simulation for water placed by the player. The artwork in `assets/textures/` is original project artwork generated for PythonCraft; it is not a Minecraft texture pack.
