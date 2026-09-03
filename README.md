# lpc-pixel

Turn a Universal LPC JSON loadout into **64×64 east-facing sprite strips** that any engine can use.

`pixelkit` calls [`@lpc-toolkit/cli`](https://www.npmjs.com/package/@lpc-toolkit/cli) as a **subprocess**, slices east `idle` / `walk` / `run`, optionally remaps to a locked palette, and writes CREDITS plus a small manifest. Godot `.import` files are an optional adapter, not the core. Unity, GameMaker, and custom engines can consume the PNGs as-is.

Character identity lives in JSON, not in a prompt. Do not draw the body with AI.

This repository licenses **our adapter + Cursor skill** as MIT. It does **not** relicense Universal LPC art or the GPL toolkit.

---

## Install

You need **Node 22+** (for the LPC CLI) and **Python 3.10+** (for pixelkit).

```bash
git clone https://github.com/francsun/lpc-pixel.git
cd lpc-pixel
npm install -g @lpc-toolkit/cli
pip install -r requirements.txt
```

The first catalog search downloads an LPC asset cache. Do not commit that cache.

On Windows the command is still `lpc-toolkit` (global npm). Check:

```bash
lpc-toolkit --version
python pixelkit/pixelkit.py build -h
```

---

## Use the Cursor skill

Agent instructions: [`.cursor/skills/lpc-pixel/SKILL.md`](.cursor/skills/lpc-pixel/SKILL.md).

**Option A — keep this repo as the tool (recommended)**

Clone it next to your game, or vendor it inside the game repo. Copy the skill into the game project:

```text
your-game/.cursor/skills/lpc-pixel/SKILL.md
```

Then tell the agent: “use lpc-pixel to swap to short hair and rebuild.”

**Option B — copy only the skill**

Default command in the skill:

```bash
python pixelkit/pixelkit.py build <file.json> --out dist/<name>
```

If `pixelkit.py` lives somewhere else, change that line, or write a thin project wrapper that injects `--engine` / `--palette` / `--tiles`.

Hard locks:

- Never draw the character with `generate2dsprite` / `image_gen`
- Failures go back to JSON parts (`search` / `set`), never a new character prompt
- This tool does not own terrain

---

## Quick check

After clone, render the sample adventurer (short hair, teal cardigan, brown boots, no weapon):

```bash
python pixelkit/pixelkit.py build examples/adventurer.json --out dist/adventurer
```

Open:

| File | What it is |
|---|---|
| `dist/adventurer/adventurer-idle.png` | East idle strip, 64×64 cells |
| `dist/adventurer/adventurer-walk.png` | East walk |
| `dist/adventurer/adventurer-run.png` | East run |
| `dist/adventurer/adventurer-sheet.png` | Full LPC sheet |
| `dist/adventurer/adventurer-sheet.viewer.html` | Play animations in a browser |
| `dist/adventurer/adventurer-manifest.json` | Frame counts, facing, filenames |
| `dist/adventurer/CREDITS.txt` | Required attribution |

Do not export a west strip. Flip east at runtime (Godot `flip_h`, Unity `flipX`, and so on).

---

## Make a character from scratch

The selection JSON is the only identity file. Do not keep a second drifting `*.selection.json`.

```bash
# 1. Create a character (body-type: male / female / teen / … — see CLI help)
lpc-toolkit character create my-hero --body-type male --json

# 2. Save the selection into your project, e.g. characters/hero.json
#    Every later search / set points at this one file.

# 3. Search parts. Confirm catalog item lists run, then set.
lpc-toolkit character search --selection characters/hero.json --type hair --query short --limit 20 --json
lpc-toolkit catalog item <id> --json
lpc-toolkit character set --selection characters/hero.json --type hair --item <id> --recolor lpcr.brown

# 4. Set clothes / legs / shoes the same way. Jacket-type coats often have no run.
#    If run is missing, switch to a cardigan / clothes item. Do not AI-draw legs.

# 5. Slice and export
python pixelkit/pixelkit.py build characters/hero.json --out dist/hero
```

`build` runs `character render` in a subprocess → slices east only → optional nearest-color remap → writes CREDITS, manifest, and a contact sheet. Do not change pixelkit to Lanczos, bbox-fit, or shrink 64×64 cells to 32.

---

## Swap parts / rebuild only

JSON already exists, change hair only:

```bash
lpc-toolkit character search --selection characters/hero.json --type hair --query curly --limit 20 --json
lpc-toolkit character set --selection characters/hero.json --type hair --item <id> --recolor lpcr.brown
python pixelkit/pixelkit.py build characters/hero.json --out dist/hero
```

Same parts, just rebuild the PNGs:

```bash
python pixelkit/pixelkit.py build characters/hero.json --out dist/hero
```

Matching a reference image: list the readable facts (hat, hair, robe, boots, weapon), then `search` / `set` the closest LPC items. The result is still a paper-doll 3/4 character, **not** a likeness of the painting.

---

## pixelkit flags

```bash
python pixelkit/pixelkit.py build <selection.json> --out <dir> [options]
```

| Flag | Default | What it does |
|---|---|---|
| `--out` | (required) | Delivery directory |
| `--engine` | `generic` | `generic` writes PNGs only; `godot` also writes `.import` |
| `--palette` | none | JSON palette; omit to keep LPC source colors |
| `--tiles` | none | Tile directory; omit to skip overlay QA |
| `--tile-top` | `grass-top.png` | Ground-top tile filename |
| `--tile-fill` | `grass-fill.png` | Optional fill tile |
| `--tile-size` | `32` | Tile edge in pixels |
| `--prefix` | JSON `name` | Output filename prefix |
| `--credits-dir` | none | Extra copy of CREDITS |
| `--verify-dir` | same as `--out` | Contact sheet / QA JSON |
| `--godot-res-prefix` | derived from `--out` | e.g. `res://sprites/` |
| `--strict` | off | Do not pass `--allow-partial` to the CLI |
| `--no-sheet` | off | Skip copying the full LPC sheet |

Lock a 24-color palette and write Godot imports:

```bash
python pixelkit/pixelkit.py build examples/adventurer.json --out dist/adventurer --palette pixelkit/palettes/default-24.json --engine godot --godot-res-prefix res://sprites/
```

Overlay QA only when you have ground tiles:

```bash
python pixelkit/pixelkit.py build examples/adventurer.json --out dist/adventurer --tiles path/to/tiles --tile-top ground-top.png
```

---

## Using the PNGs in a game

`{prefix}-manifest.json` records cell size and frame counts so the engine does not have to guess:

```json
{
  "cell": 64,
  "east_only": true,
  "west": "flip_h",
  "animations": {
    "idle": { "file": "adventurer-idle.png", "frames": 2, "frame_width": 64, "frame_height": 64 },
    "walk": { "file": "adventurer-walk.png", "frames": 9, "frame_width": 64, "frame_height": 64 },
    "run":  { "file": "adventurer-run.png",  "frames": 8, "frame_width": 64, "frame_height": 64 }
  }
}
```

Recommended:

- Filter: nearest; mipmaps off
- Pivot: bottom-center; idle / walk / run share one feet line
- Standing height is about 50px (roughly 2 tiles if tiles are 32px)
- Put `CREDITS.txt` on the in-game credits screen

Godot 4 can pass `--engine godot`. Templates live in `pixelkit/engines/`. Other engines can ignore that flag.

---

## What this tool will not do

- Import `@lpc-toolkit` into Python or your game (the GPL core stays out of process)
- Lanczos / bilinear / bbox-fit / shrink 64×64 cells to 32
- **Draw** a character from a prompt or a painting
- Act as a terrain / TileMap tool

---

## License split

| Piece | License |
|---|---|
| This repo's Python, skill, and templates | MIT |
| `@lpc-toolkit/cli` | GPL-3.0-or-later (install it yourself; do not vendor) |
| Composed PNGs | Follow the LPC layers listed in CREDITS (often CC0 / OGA-BY / CC-BY / CC-BY-SA / GPL). ShareAlike derivatives stay ShareAlike. |

Every export **must** keep `CREDITS.txt` / `CREDITS.csv` beside the PNGs.

---

## Layout

```text
.cursor/skills/lpc-pixel/SKILL.md   Cursor / Codex agent instructions
pixelkit/pixelkit.py                the build command
pixelkit/palettes/default-24.json   optional example palette
pixelkit/engines/                   optional Godot templates
examples/adventurer.json            demo loadout (not a game's hero)
```

---

## Troubleshooting

| Symptom | What to do |
|---|---|
| `lpc-toolkit CLI not on PATH` | `npm install -g @lpc-toolkit/cli`, then open a new terminal |
| `asset_image_missing` / no run | `--allow-partial` is on by default. Lasting fix: pick clothes that include `run`. Do not draw legs. |
| Feet line drifts, height is wrong, frames missing | Change JSON parts and `build` again. Do not resample. |
| Palette lock fails (extra swatches) | Check `--palette`. Still go back to part swaps; do not add colors. |
| Reference image does not match | LPC is paper-doll, not portrait. Keep swapping parts. |

Open a GitHub Issue for bugs and improvements.
