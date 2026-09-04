---
name: lpc-pixel
description: >-
  Compose engine-agnostic player sprites from Universal LPC via lpc-toolkit and
  pixelkit (64×64 east idle/walk/run strips, optional palette remap, CREDITS,
  optional engine adapters). Use when the user mentions LPC, pixelkit, lpc-pixel,
  spritesheet, paper-doll, character parts, hero.json, player character, or asks
  to build/re-render/swap character parts from a description or reference image.
  Never draw the character with generate2dsprite or image_gen.
---

# LPC Pixel

Character body is LPC paper-doll + `pixelkit`. Identity lives in a selection JSON, not a prompt. Delivery PNGs work in any engine; Godot `.import` is opt-in.

## Hard locks

- Never draw the character with generate2dsprite
- Failures go back to JSON parts
- This tool does not own terrain

Also locked:

- No `image_gen` / Cursor `GenerateImage` for the character body.
- Failures go back to selection-JSON part swaps (`lpc-toolkit character search` / `set`). Never a new character prompt. Never Lanczos / bbox-fit / engine scale hacks.
- Terrain is out of scope. If the host project has a tile tool, use that; do not ask LPC to paint ground.
- Call `@lpc-toolkit/cli` as a **subprocess**. Do not import its GPL core.
- East-only 64×64 delivery; west = runtime `flip_h`.
- Every export must keep CREDITS beside the PNGs.
- Prefer CC0 / OGA-BY parts. Record SA/GPL if used. Prefer items that actually have `run`.
- A reference image is identity **hints** (hood, hair, robe). Match catalog parts. Do not draw a likeness.

## Commands

Mutate one selection file. Do not let a second `*.selection.json` drift.

```text
lpc-toolkit character search --selection <file.json> --type hair --query short --limit 20 --json
lpc-toolkit character set --selection <file.json> --type hair --item <id> --recolor lpcr.brown
python pixelkit/pixelkit.py build <file.json> --out dist/<name>
```

Optional flags:

```text
--palette <palette.json>
--engine godot --godot-res-prefix res://sprites/
--tiles <tile-dir> --tile-top <file.png>
```

`build` renders via CLI, slices east idle/walk/run, optionally remaps, writes CREDITS + manifest + sheet. Stop after `build` unless the user asked for engine scene work. Do not rewrite `pixelkit` to resample or crop to bbox.

Jacket-type coats often lack `run`. If preview/build cannot produce a run cycle, pick clothes/cardigan (or another item whose `catalog item --json` lists `run`). Do not draw legs.

## Outputs to open

- `{out}/{prefix}-idle.png` / `{prefix}-walk.png` / `{prefix}-run.png`
- `{out}/{prefix}-sheet.png` and `{prefix}-sheet.viewer.html`
- `{out}/{prefix}-manifest.json`
- `{out}/CREDITS.txt`
- `{verify}/qa-report.json` (verify dir defaults to `--out`)

## Routing

| Need | Do |
|---|---|
| New / different look | `search` → `set` on JSON → `pixelkit build` |
| Same parts, new strips | `pixelkit build` only |
| QA fail (feet, height, palette, missing run) | change JSON parts; rebuild |
| Reference image | name visible parts; `search`/`set` closest LPC items; still paper-doll 3/4 |
| FX / slash / muzzle | a separate FX tool **after** the character exists; never the body |
| Tiles / rooms | not this skill |

## Examples

### Swap hair

```text
lpc-toolkit character search --selection examples/adventurer/adventurer.json --type hair --query short --limit 20 --json
lpc-toolkit catalog item <id> --json
lpc-toolkit character set --selection examples/adventurer/adventurer.json --type hair --item <id> --recolor lpcr.brown
python pixelkit/pixelkit.py build examples/adventurer/adventurer.json --out examples/adventurer
```

Inspect east idle 1×. If the cut is wrong, `set` another hair id. Do not generate2dsprite a new head.

### Re-render

```text
python pixelkit/pixelkit.py build examples/adventurer/adventurer.json --out examples/adventurer
```

Open the three strips, the sheet viewer, and CREDITS. No part search unless QA fails.

### Match a reference image

1. List silhouette facts from the image (hair length, hood, robe vs jacket, boots, weapon).
2. `character search` / `catalog item` until each slot has a part that includes `run` if the user needs a run cycle.
3. `character set` onto the selection JSON.
4. `pixelkit build`.
5. If it is not close enough, swap parts. Do not `image_gen` a new body.
