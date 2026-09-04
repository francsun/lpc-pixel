# lpc-pixel

An agent skill for [Cursor](https://cursor.com), [Codex](https://openai.com/codex/), and any other agent that loads `SKILL.md`. It turns a Universal LPC **JSON loadout** into 64×64 east-facing sprite strips. Characters are drawn from the open-source [Universal LPC Spritesheet Character Generator](https://github.com/liberatedpixelcup/Universal-LPC-Spritesheet-Character-Generator). Identity lives in the JSON, not in a prompt. The PNGs work in any engine; west facing is a runtime flip.

Thanks to [Liberated Pixel Cup](https://github.com/liberatedpixelcup) and the LPC contributors.

## Dependencies

| Tool | What it is for |
|---|---|
| Cursor, Codex, or another `SKILL.md` agent | Loads [`.cursor/skills/lpc-pixel/SKILL.md`](.cursor/skills/lpc-pixel/SKILL.md) |
| [Universal LPC Character Generator](https://github.com/liberatedpixelcup/Universal-LPC-Spritesheet-Character-Generator) | Open-source paper-doll art this skill renders |
| Node 22+ and [`@lpc-toolkit/cli`](https://www.npmjs.com/package/@lpc-toolkit/cli) | Composes the LPC sheet |
| Python 3.10+ and [Pillow](https://pypi.org/project/Pillow/) | `pixelkit` slices east idle / walk / run |

`pixelkit` calls the CLI as a **subprocess**. Do not import the GPL toolkit into Python or your game. Each export still needs `CREDITS.txt` for the LPC layers.

## Quick install

```bash
git clone https://github.com/francsun/lpc-pixel.git
cd lpc-pixel
npm install -g @lpc-toolkit/cli
pip install -r requirements.txt
```

Copy the skill into the agent folder your tool reads:

```text
your-game/.cursor/skills/lpc-pixel/SKILL.md   # Cursor
your-game/.codex/skills/lpc-pixel/SKILL.md    # Codex
```

The file is the same. Then ask the agent to build or swap character parts with lpc-pixel.

## Example

[`examples/adventurer/`](examples/adventurer/) is a finished character: short brown hair, teal cardigan, charcoal pants, brown boots.

![East idle](examples/adventurer/adventurer-idle.png)

| File | |
|---|---|
| `adventurer.json` | LPC parts |
| `adventurer-idle.png` | East idle (64×64 cells) |
| `adventurer-walk.png` | East walk |
| `adventurer-run.png` | East run |
| `adventurer-sheet.png` | Full sheet |
| `adventurer-sheet.viewer.html` | Play the animations in a browser |
| `CREDITS.txt` | Required attribution |

Rebuild it:

```bash
python pixelkit/pixelkit.py build examples/adventurer/adventurer.json --out examples/adventurer
```
