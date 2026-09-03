# lpc-pixel

把 Universal LPC 的 JSON 选件，做成 **任意引擎都能用** 的 64×64 东向像素条带。

`pixelkit` 只通过子进程调用 [`@lpc-toolkit/cli`](https://www.npmjs.com/package/@lpc-toolkit/cli)，切东向 `idle` / `walk` / `run`，可选锁色板，写出 CREDITS 和一份小 manifest。Godot `.import` 是可选适配器，不是核心。Unity、GameMaker、自研引擎直接吃 PNG 即可。

角色身份在 JSON 里，不在 prompt 里。不要用 AI 画身体。

This repo licenses **our adapter + Cursor skill** as MIT. It does **not** relicense Universal LPC art or the GPL toolkit.

---

## 安装

需要 **Node 22+**（给 LPC CLI）和 **Python 3.10+**（给 pixelkit）。

```bash
git clone https://github.com/francsun/lpc-pixel.git
cd lpc-pixel
npm install -g @lpc-toolkit/cli
pip install -r requirements.txt
```

第一次搜目录时，CLI 会下载 LPC 资源缓存。不要把缓存提交进仓库。

Windows 上命令是 `lpc-toolkit`（npm 全局）。确认：

```bash
lpc-toolkit --version
python pixelkit/pixelkit.py build -h
```

---

## 在 Cursor 里用这个 Skill

仓库里的代理说明在 [`.cursor/skills/lpc-pixel/SKILL.md`](.cursor/skills/lpc-pixel/SKILL.md)。

**方式 A：整个仓库当工具用（推荐）**

把本仓库放到你的游戏项目旁边，或加进游戏仓。对话里提到 LPC、pixelkit、角色选件、spritesheet 时，把 skill 文件加到游戏项目：

```text
你的游戏/.cursor/skills/lpc-pixel/SKILL.md   ← 复制本仓库这一份
```

然后对代理说：「用 lpc-pixel 给角色换短发并重渲」。

**方式 B：只拷 skill，命令仍指向本仓库的 `pixelkit.py`**

Skill 里的命令默认是：

```bash
python pixelkit/pixelkit.py build <file.json> --out dist/<name>
```

如果你把 `pixelkit.py` 放在别的路径，改 skill 里的这一行，或在游戏仓写一个薄包装（注入 `--engine` / `--palette` / `--tiles`）。

写死三条：

- 角色禁止 `generate2dsprite` / `image_gen`
- 失败回 JSON 选件（`search` / `set`），不要新写角色 prompt
- 本工具不管地形

---

## 最快验证

克隆后直接渲示例角色（短发、teal 开衫、棕靴，无武器）：

```bash
python pixelkit/pixelkit.py build examples/adventurer.json --out dist/adventurer
```

打开：

| 文件 | 内容 |
|---|---|
| `dist/adventurer/adventurer-idle.png` | 东向 idle 条，每格 64×64 |
| `dist/adventurer/adventurer-walk.png` | 东向 walk |
| `dist/adventurer/adventurer-run.png` | 东向 run |
| `dist/adventurer/adventurer-sheet.png` | 完整 LPC 表 |
| `dist/adventurer/adventurer-sheet.viewer.html` | 浏览器里播动画 |
| `dist/adventurer/adventurer-manifest.json` | 帧数、朝向、文件名 |
| `dist/adventurer/CREDITS.txt` | 必须保留的署名 |

西向不要导出。运行时把东向图 **水平翻转**（Godot `flip_h`，Unity `flipX`，等等）。

---

## 从零做一个角色

选件 JSON 是唯一身份文件。不要再维护第二份会漂的 `*.selection.json`。

```bash
# 1. 建角色（body-type: male / female / teen / … 以 CLI 为准）
lpc-toolkit character create my-hero --body-type male --json

# 2. 把选件存进你的项目，例如 characters/hero.json
#    之后所有 search / set 都指向这一份

# 3. 搜零件（先确认 catalog item 带 run，再 set）
lpc-toolkit character search --selection characters/hero.json --type hair --query short --limit 20 --json
lpc-toolkit catalog item <id> --json
lpc-toolkit character set --selection characters/hero.json --type hair --item <id> --recolor lpcr.brown

# 4. 同样方式 set 衣服 / 裤子 / 鞋子。外套类 jacket 经常没有 run。
#    没有 run 就换 cardigan / clothes，不要用 AI 补腿。

# 5. 切片导出
python pixelkit/pixelkit.py build characters/hero.json --out dist/hero
```

`build` 会：子进程 `character render` → 只切东向 → 可选色板最近色 remap → 写 CREDITS + manifest + 接触表。不要改 pixelkit 去做 Lanczos、bbox-fit，或把 64 格缩成 32。

---

## 换零件 / 只重渲

已经有 JSON、只换发型：

```bash
lpc-toolkit character search --selection characters/hero.json --type hair --query curly --limit 20 --json
lpc-toolkit character set --selection characters/hero.json --type hair --item <id> --recolor lpcr.brown
python pixelkit/pixelkit.py build characters/hero.json --out dist/hero
```

零件没变、只想再出一遍图：

```bash
python pixelkit/pixelkit.py build characters/hero.json --out dist/hero
```

对照参考图：把图里能看清的特征写成选件（帽子、发型、袍子、靴子、武器），`search` / `set` 最接近的 LPC 件。输出仍是纸娃娃 3/4 视角，**不是**那张图的肖像。

---

## pixelkit 参数

```bash
python pixelkit/pixelkit.py build <selection.json> --out <dir> [选项]
```

| 参数 | 默认 | 作用 |
|---|---|---|
| `--out` | （必填） | 交付目录 |
| `--engine` | `generic` | `generic` 只出 PNG；`godot` 另写 `.import` |
| `--palette` | 无 | JSON 色板；省略则保留 LPC 原色 |
| `--tiles` | 无 | 砖目录；省略则不做叠砖 QA |
| `--tile-top` | `grass-top.png` | 站立面砖文件名 |
| `--tile-fill` | `grass-fill.png` | 可选填充砖 |
| `--tile-size` | `32` | 砖边长 |
| `--prefix` | JSON 的 `name` | 输出文件名前缀 |
| `--credits-dir` | 无 | 额外拷一份 CREDITS |
| `--verify-dir` | 与 `--out` 相同 | 接触表 / QA JSON |
| `--godot-res-prefix` | 按 `--out` 推 | 例如 `res://sprites/` |
| `--strict` | 关 | 不传 CLI 的 `--allow-partial` |
| `--no-sheet` | 关 | 不拷完整 LPC 表 |

锁 24 色 + Godot 导入示例：

```bash
python pixelkit/pixelkit.py build examples/adventurer.json --out dist/adventurer --palette pixelkit/palettes/default-24.json --engine godot --godot-res-prefix res://sprites/
```

有地砖时才叠图验收：

```bash
python pixelkit/pixelkit.py build examples/adventurer.json --out dist/adventurer --tiles path/to/tiles --tile-top ground-top.png
```

---

## 游戏里怎么用这些 PNG

`{prefix}-manifest.json` 已经写明格大小和帧数，引擎不用猜：

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

建议：

- 过滤：nearest；关 mipmaps
- 轴点：脚底中心；idle / walk / run 共用一条脚线
- 人高大约 50px（在 32px 砖上约 2 格）
- 把 `CREDITS.txt` 放进游戏致谢画面

Godot 4 可加 `--engine godot`。模板在 `pixelkit/engines/`。其它引擎忽略该选项即可。

---

## 这个工具不会做的事

- 把 `@lpc-toolkit` import 进 Python 或游戏（GPL 核心必须留在子进程外）
- Lanczos / 双线性 / bbox-fit / 把 64×64 缩成 32
- 按 prompt 或原画 **画** 一个角色
- 当地形 / TileMap 工具用

---

## 许可怎么分

| 东西 | 许可 |
|---|---|
| 本仓库的 Python、skill、模板 | MIT |
| `@lpc-toolkit/cli` | GPL-3.0-or-later（自己装，不要 vendor） |
| 合成出来的 PNG | 跟 CREDITS 里的 LPC 图层走（常见 CC0 / OGA-BY / CC-BY / CC-BY-SA / GPL）。SA 衍生仍是 SA |

每次导出都必须把 `CREDITS.txt` / `CREDITS.csv` 留在 PNG 旁边。

---

## 目录

```text
.cursor/skills/lpc-pixel/SKILL.md   Cursor / Codex 代理说明
pixelkit/pixelkit.py                一条 build 命令
pixelkit/palettes/default-24.json   可选示例色板
pixelkit/engines/                   可选 Godot 模板
examples/adventurer.json            演示选件（不是某个游戏的主角）
```

---

## 故障

| 现象 | 做什么 |
|---|---|
| `lpc-toolkit CLI not on PATH` | `npm install -g @lpc-toolkit/cli`，新开一个终端 |
| `asset_image_missing` / 缺 run | 默认已 `--allow-partial`。长期方案：换带 `run` 的衣服，不要画腿 |
| 脚线漂、身高不对、缺帧 | 改 JSON 选件再 `build`，不要重采样 |
| 想锁项目色板但超出 swatch | 检查 `--palette`；失败仍回选件，不要加色 |
| 参考图对不上 | LPC 是纸娃娃，不是肖像。继续换零件 |

问题与改进请开 GitHub Issue。
