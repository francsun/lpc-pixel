#!/usr/bin/env python3
"""LPC JSON loadout → engine-agnostic pixel strips.

Call `@lpc-toolkit/cli` as a subprocess. Do not import its GPL core.
Never Lanczos / bilinear / bicubic, never bbox-fit, never image_gen.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
CELL_DEFAULT = 64
EAST_ROW_DEFAULT = 3  # LPC animation strips: up, left, down, right
ANIMATIONS_DEFAULT = ("idle", "walk", "run")
OPAQUE_MIN = 16
EMPTY_CELL_PX = 24
FORBIDDEN_RESAMPLE = {
    getattr(Image, name)
    for name in ("BILINEAR", "BICUBIC", "LANCZOS", "HAMMING", "BOX", "LINEAR", "CUBIC")
    if hasattr(Image, name)
}


def rel(path: Path, root: Path) -> str:
    path = path.resolve()
    try:
        return path.relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def hex_rgb(rgb: tuple[int, int, int]) -> str:
    return "#%02X%02X%02X" % rgb


def parse_hex(value: str) -> tuple[int, int, int]:
    h = value.strip().lstrip("#")
    if len(h) != 6:
        raise SystemExit(f"expected #RRGGBB, got {value!r}")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def load_palette(path: Path) -> tuple[list[tuple[int, int, int]], dict[str, tuple[int, int, int]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    colors: list[tuple[int, int, int]] = []
    roles: dict[str, tuple[int, int, int]] = {}
    entries = data["colors"] if isinstance(data, dict) and "colors" in data else data
    if not entries:
        raise SystemExit(f"palette {path} has no colors")
    for entry in entries:
        if isinstance(entry, str):
            rgb = parse_hex(entry)
            colors.append(rgb)
            continue
        rgb = parse_hex(entry["hex"])
        colors.append(rgb)
        role = entry.get("role")
        if role:
            roles[str(role)] = rgb
    return colors, roles


def nearest_rgb(rgb: tuple[int, int, int], palette: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    r, g, b = rgb
    best = palette[0]
    best_d = 10**18
    for pr, pg, pb in palette:
        d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if d < best_d:
            best_d = d
            best = (pr, pg, pb)
            if d == 0:
                break
    return best


def find_cli() -> str:
    for name in ("lpc-toolkit.cmd", "lpc-toolkit"):
        found = shutil.which(name)
        if found:
            return found
    raise SystemExit("lpc-toolkit CLI not on PATH. Install @lpc-toolkit/cli globally (Node 22+).")


def run_cli(args: list[str], cwd: Path) -> dict:
    cli = find_cli()
    cmd = [cli, *args]
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    stdout = proc.stdout or ""
    if proc.returncode != 0:
        raise SystemExit(
            f"lpc-toolkit failed ({proc.returncode}): {' '.join(cmd)}\n"
            f"{proc.stderr or stdout}"
        )
    text = stdout.strip()
    if not text:
        raise SystemExit(f"lpc-toolkit produced empty stdout: {' '.join(cmd)}")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise SystemExit(f"lpc-toolkit stdout was not JSON:\n{text[:2000]}")
        payload = json.loads(text[start : end + 1])
    if payload.get("ok") is False or payload.get("errors"):
        raise SystemExit(f"lpc-toolkit reported errors: {payload.get('errors')}")
    return payload


def content_bbox(im: Image.Image) -> tuple[int, int, int, int] | None:
    return im.getchannel("A").getbbox()


def opaque_count(im: Image.Image) -> int:
    return sum(1 for *_, a in im.getdata() if a >= OPAQUE_MIN)


def opaque_colors(im: Image.Image) -> set[tuple[int, int, int]]:
    colors: set[tuple[int, int, int]] = set()
    for r, g, b, a in im.getdata():
        if a >= OPAQUE_MIN:
            colors.add((r, g, b))
    return colors


def nn_integer(im: Image.Image, scale: int) -> Image.Image:
    if scale < 1 or int(scale) != scale:
        raise SystemExit("only positive integer nearest-neighbor scale is allowed")
    if scale == 1:
        return im.copy()
    resample = Image.NEAREST
    if resample in FORBIDDEN_RESAMPLE:
        raise SystemExit("nearest-neighbor resample is required")
    return im.resize((im.width * scale, im.height * scale), resample)


def remap_or_passthrough(
    im: Image.Image,
    palette: list[tuple[int, int, int]] | None,
) -> Image.Image:
    src = im.convert("RGBA")
    cache: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    data: list[tuple[int, int, int, int]] = []
    for r, g, b, a in src.getdata():
        if a < OPAQUE_MIN:
            data.append((0, 0, 0, 0))
            continue
        if palette is None:
            data.append((r, g, b, 255))
            continue
        mapped = cache.get((r, g, b))
        if mapped is None:
            mapped = nearest_rgb((r, g, b), palette)
            cache[(r, g, b)] = mapped
        pr, pg, pb = mapped
        data.append((pr, pg, pb, 255))
    out = Image.new("RGBA", src.size)
    out.putdata(data)
    return out


def slice_east(strip: Image.Image, animation: str, cell: int, east_row: int) -> list[Image.Image]:
    if strip.height % cell != 0 or strip.width % cell != 0:
        raise SystemExit(
            f"{animation} strip {strip.size} is not a {cell}px grid; "
            "do not resize LPC pixels"
        )
    rows = strip.height // cell
    cols = strip.width // cell
    if rows == 1:
        row_y = 0
    elif rows > east_row:
        row_y = east_row * cell
    else:
        raise SystemExit(
            f"{animation} strip has {rows} direction rows; expected 1 or more than east row {east_row}"
        )
    frames: list[Image.Image] = []
    for col in range(cols):
        cell_im = strip.crop((col * cell, row_y, (col + 1) * cell, row_y + cell))
        if cell_im.size != (cell, cell):
            raise SystemExit("east slice left the cell size; bbox-fit is forbidden")
        if opaque_count(cell_im) >= EMPTY_CELL_PX:
            frames.append(cell_im.convert("RGBA"))
    if not frames:
        raise SystemExit(
            f"no east {animation} frames with pixels. Change the selection JSON parts, "
            "do not regenerate the body with image_gen."
        )
    return frames


def pack_strip(frames: list[Image.Image], cell: int) -> Image.Image:
    sheet = Image.new("RGBA", (cell * len(frames), cell), (0, 0, 0, 0))
    for i, frame in enumerate(frames):
        if frame.size != (cell, cell):
            raise SystemExit("delivery frames must stay on the LPC cell size; bbox-fit is forbidden")
        sheet.paste(frame, (i * cell, 0))
    return sheet


def write_godot_import(png: Path, res_path: str, template_path: Path) -> Path:
    template = template_path.read_text(encoding="utf-8")
    params = template.split("[params]", 1)[-1]
    import_path = png.with_suffix(png.suffix + ".import")
    import_path.write_text(
        "[remap]\n\n"
        'importer="texture"\n'
        'type="CompressedTexture2D"\n\n'
        "[deps]\n\n"
        f'source_file="{res_path}"\n\n'
        "[params]"
        f"{params.rstrip()}\n",
        encoding="utf-8",
    )
    return import_path


def copy_credits(render_dir: Path, destinations: list[Path]) -> dict[str, str]:
    txt = next(render_dir.glob("*.credits.txt"), None)
    csv = next(render_dir.glob("*.credits.csv"), None)
    if txt is None or csv is None:
        raise SystemExit("render wrote no CREDITS; refusing to ship LPC pixels without attribution")
    copied: dict[str, str] = {}
    for dest_dir in destinations:
        dest_dir.mkdir(parents=True, exist_ok=True)
        t = dest_dir / "CREDITS.txt"
        c = dest_dir / "CREDITS.csv"
        shutil.copy2(txt, t)
        shutil.copy2(csv, c)
        shutil.copy2(txt, dest_dir / txt.name)
        shutil.copy2(csv, dest_dir / csv.name)
        copied[str(dest_dir)] = str(t)
    return copied


def overlay_idle_on_tiles(
    idle: Image.Image,
    tiles_dir: Path,
    tile_top: str,
    tile_fill: str,
    tile_size: int,
    cell: int,
    bg: tuple[int, int, int],
) -> tuple[Image.Image, dict]:
    top_path = tiles_dir / tile_top
    if not top_path.is_file():
        raise SystemExit(f"missing {top_path}; overlay is optional — omit --tiles if you have no ground tile")
    top = Image.open(top_path).convert("RGBA")
    fill_path = tiles_dir / tile_fill
    fill = Image.open(fill_path).convert("RGBA") if fill_path.is_file() else None
    if top.size != (tile_size, tile_size):
        raise SystemExit(f"{tile_top} must stay {tile_size}x{tile_size}, got {top.size}")

    cols = 6
    ground_row = 3
    fill_row = 4
    width = cols * tile_size
    height = 6 * tile_size
    canvas = Image.new("RGBA", (width, height), (*bg, 255))
    for x in range(cols):
        canvas.alpha_composite(top, (x * tile_size, ground_row * tile_size))
        if fill is not None and fill.size == (tile_size, tile_size):
            canvas.alpha_composite(fill, (x * tile_size, fill_row * tile_size))

    box = content_bbox(idle)
    if box is None:
        raise SystemExit("idle east frame is empty")
    feet_in_frame = box[3]
    ground_y = ground_row * tile_size
    paste_x = (width - cell) // 2
    paste_y = ground_y - feet_in_frame
    canvas.alpha_composite(idle, (paste_x, paste_y))
    feet_world = paste_y + feet_in_frame
    return canvas, {
        "ground_y": ground_y,
        "feet_world": feet_world,
        "delta": feet_world - ground_y,
        "content_height": box[3] - box[1],
        "paste": [paste_x, paste_y],
    }


def panel(title: str, image: Image.Image, scale: int = 1) -> Image.Image:
    body = nn_integer(image.convert("RGBA"), scale)
    header = 16
    canvas = Image.new("RGBA", (max(body.width, 8), body.height + header), (24, 24, 32, 255))
    from PIL import ImageDraw, ImageFont

    draw = ImageDraw.Draw(canvas)
    draw.text((4, 2), title, fill=(244, 240, 230, 255), font=ImageFont.load_default())
    canvas.alpha_composite(body, (0, header))
    return canvas


def build_contact_sheet(
    strips: dict[str, Image.Image],
    overlay: Image.Image | None,
) -> Image.Image:
    sections = []
    for name in strips:
        sections.append(panel(f"{name} east 1x", strips[name], 1))
        sections.append(panel(f"{name} east 3x nearest", strips[name], 3))
    if overlay is not None:
        sections.append(panel("idle on tiles 1x", overlay, 1))
        sections.append(panel("idle on tiles 3x nearest", overlay, 3))
    width = max(s.width for s in sections) + 16
    height = sum(s.height for s in sections) + 8 * (len(sections) + 1)
    contact = Image.new("RGBA", (width, height), (18, 18, 24, 255))
    y = 8
    for section in sections:
        contact.alpha_composite(section, (8, y))
        y += section.height + 8
    return contact


def gate(gates: list[dict], name: str, ok: bool, detail: str) -> None:
    gates.append({"name": name, "ok": bool(ok), "detail": detail})


def qa_report(
    strips: dict[str, Image.Image],
    overlay_meta: dict | None,
    credits_ok: bool,
    outputs: dict[str, str],
    selection_path: str,
    cell: int,
    tile_size: int | None,
    palette: list[tuple[int, int, int]] | None,
) -> dict:
    gates: list[dict] = []
    all_colors: set[tuple[int, int, int]] = set()
    heights: dict[str, float] = {}
    palette_set = set(palette) if palette else None

    for name, sheet in strips.items():
        gate(gates, f"{name}-cell", sheet.height == cell, f"{sheet.size} (want height {cell})")
        n = sheet.width // cell
        gate(gates, f"{name}-east-strip", sheet.height == cell and n >= 1, f"{n} east frames")
        colors = opaque_colors(sheet)
        all_colors |= colors
        if palette_set is not None:
            extras = sorted(colors - palette_set)
            gate(
                gates,
                f"{name}-palette",
                not extras,
                f"{len(colors)} opaque RGB extras={[hex_rgb(c) for c in extras]}",
            )
        bottoms = []
        hs = []
        for i in range(n):
            fr = sheet.crop((i * cell, 0, (i + 1) * cell, cell))
            box = content_bbox(fr)
            if box:
                bottoms.append(box[3])
                hs.append(box[3] - box[1])
        if bottoms:
            mean_b = sum(bottoms) / len(bottoms)
            std = (sum((b - mean_b) ** 2 for b in bottoms) / len(bottoms)) ** 0.5
            mean_h = sum(hs) / len(hs)
        else:
            std, mean_h = 99.0, 0.0
        heights[name] = mean_h
        gate(gates, f"{name}-feet-line", std <= 2.0, f"content-bottom std {std:.2f}px")
        gate(
            gates,
            f"{name}-height-in-cell",
            40 <= mean_h <= cell,
            f"mean content height {mean_h:.1f}px (LPC standing ~50px in a {cell} cell)",
        )

    if palette_set is not None:
        extras_all = sorted(all_colors - palette_set)
        gate(
            gates,
            "palette",
            not extras_all,
            f"{len(all_colors)} unique opaque RGB extras={[hex_rgb(c) for c in extras_all]}",
        )
    gate(gates, "credits-present", credits_ok, "CREDITS.txt/csv copied beside delivery")
    if overlay_meta is not None:
        gate(
            gates,
            "idle-feet-on-platform",
            abs(overlay_meta["delta"]) <= 2,
            f"feet y={overlay_meta['feet_world']} tile top y={overlay_meta['ground_y']} "
            f"delta={overlay_meta['delta']}",
        )
        if tile_size:
            mean_h = heights.get("idle") or 0.0
            gate(
                gates,
                "idle-height-about-two-tiles",
                1.2 * tile_size <= mean_h <= 2.2 * tile_size or 40 <= mean_h <= cell,
                f"mean idle height {mean_h:.1f}px vs tile {tile_size}px",
            )
    drift = 0.0
    if heights.get("idle") and heights.get("run"):
        drift = abs(heights["run"] - heights["idle"]) / heights["idle"]
        gate(gates, "idle-run-height-drift", drift <= 0.15, f"drift {drift:.1%}")
    gate(gates, "no-gpl-import", True, "lpc-toolkit invoked only as a subprocess")

    return {
        "ok": all(g["ok"] for g in gates),
        "selection": selection_path,
        "cell": cell,
        "tile": tile_size,
        "east_only": True,
        "west": "flip_h",
        "resample": "nearest-integer-preview-only",
        "bbox_fit": False,
        "image_gen": False,
        "palette_locked": palette is not None,
        "heights_px": {k: round(v, 2) for k, v in heights.items()},
        "unique_opaque_colors": len(all_colors),
        "gates": gates,
        "outputs": outputs,
    }


def selection_prefix(selection: Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    data = json.loads(selection.read_text(encoding="utf-8"))
    name = data.get("name") if isinstance(data, dict) else None
    return str(name) if name else selection.stem


def find_animation_png(work: Path, name: str, payload: dict) -> Path:
    anim_path = work / "animations" / f"{name}.png"
    if anim_path.is_file():
        return anim_path
    artifacts = (payload.get("data") or payload).get("artifacts") or []
    for art in artifacts:
        if art.get("type") == "animation" and art.get("animation") == name:
            candidate = Path(art["path"])
            if candidate.is_file():
                return candidate
    raise SystemExit(
        f"render did not write animations/{name}.png. "
        "Swap parts in the selection JSON; do not image_gen the body."
    )


def copy_sheet_and_viewer(
    work: Path,
    out_dir: Path,
    prefix: str,
    palette: list[tuple[int, int, int]] | None,
) -> dict[str, str]:
    copied: dict[str, str] = {}
    sheet = next(work.glob("*.sheet.png"), None)
    if sheet is None:
        return copied
    dest_sheet = out_dir / f"{prefix}-sheet.png"
    remapped = remap_or_passthrough(Image.open(sheet), palette)
    remapped.save(dest_sheet)
    copied["sheet"] = dest_sheet.name

    viewer = next(work.glob("*.viewer.html"), None)
    if viewer is not None:
        dest_viewer = out_dir / f"{prefix}-sheet.viewer.html"
        text = viewer.read_text(encoding="utf-8")
        dest_viewer.write_text(text.replace(sheet.name, dest_sheet.name), encoding="utf-8")
        copied["viewer"] = dest_viewer.name

    meta = next(work.glob("*.metadata.json"), None)
    if meta is not None:
        dest_meta = out_dir / f"{prefix}-sheet.metadata.json"
        shutil.copy2(meta, dest_meta)
        copied["sheet_metadata"] = dest_meta.name
    return copied


def write_manifest(
    path: Path,
    *,
    prefix: str,
    cell: int,
    animations: dict[str, int],
    engine: str,
    palette: bool,
) -> None:
    payload = {
        "schema": "lpc-pixel.manifest.v1",
        "cell": cell,
        "east_only": True,
        "west": "flip_h",
        "engine": engine,
        "palette_remapped": palette,
        "animations": {
            name: {
                "file": f"{prefix}-{name}.png",
                "frames": count,
                "frame_width": cell,
                "frame_height": cell,
            }
            for name, count in animations.items()
        },
        "sheet": f"{prefix}-sheet.png",
        "credits": ["CREDITS.txt", "CREDITS.csv"],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def cmd_build(args: argparse.Namespace) -> dict:
    selection = args.selection.resolve()
    if not selection.is_file():
        raise SystemExit(f"missing selection JSON: {selection}")
    repo = args.repo_root.resolve()
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = selection_prefix(selection, args.prefix)
    cell = args.cell
    animations = tuple(args.animation) if args.animation else ANIMATIONS_DEFAULT

    palette = None
    roles: dict[str, tuple[int, int, int]] = {}
    if args.palette:
        palette, roles = load_palette(args.palette.resolve())

    work_root = args.work_dir.resolve() if args.work_dir else out_dir / ".work"
    work = work_root / selection.stem
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    render_args = [
        "character",
        "render",
        "--selection",
        str(selection),
        "--out",
        str(work),
        *[part for name in animations for part in ("--animation", name)],
        "--json",
    ]
    if args.allow_partial:
        render_args.insert(-1, "--allow-partial")

    payload = run_cli(render_args, cwd=repo)

    strips: dict[str, Image.Image] = {}
    frame_counts: dict[str, int] = {}
    for name in animations:
        raw = Image.open(find_animation_png(work, name, payload)).convert("RGBA")
        east = [remap_or_passthrough(frame, palette) for frame in slice_east(raw, name, cell, args.east_row)]
        strips[name] = pack_strip(east, cell)
        frame_counts[name] = len(east)

    outputs: dict[str, str] = {}
    godot_res_prefix = args.godot_res_prefix
    if godot_res_prefix is None and args.engine == "godot":
        try:
            godot_res_prefix = "res://" + out_dir.resolve().relative_to(repo).as_posix().rstrip("/") + "/"
        except ValueError:
            godot_res_prefix = "res://"

    template_path = (
        args.godot_import_template.resolve()
        if args.godot_import_template
        else HERE / "engines" / "godot_import.template"
    )
    snippet_path = (
        args.godot_project_snippet.resolve()
        if args.godot_project_snippet
        else HERE / "engines" / "godot_project.snippet"
    )

    for name, sheet in strips.items():
        png = out_dir / f"{prefix}-{name}.png"
        sheet.save(png)
        outputs[f"{name}_strip"] = rel(png, repo)
        if args.engine == "godot":
            if not template_path.is_file():
                raise SystemExit(f"missing Godot import template: {template_path}")
            imp = write_godot_import(png, f"{godot_res_prefix}{png.name}", template_path)
            outputs[f"{name}_import"] = rel(imp, repo)

    credit_dirs = [out_dir]
    if args.credits_dir:
        credit_dirs.append(args.credits_dir.resolve())
    copy_credits(work, credit_dirs)
    outputs["credits_txt"] = rel(out_dir / "CREDITS.txt", repo)
    outputs["credits_csv"] = rel(out_dir / "CREDITS.csv", repo)
    if args.credits_dir:
        outputs["credits_extra_txt"] = rel(args.credits_dir.resolve() / "CREDITS.txt", repo)

    if args.copy_sheet:
        sheet_files = copy_sheet_and_viewer(work, out_dir, prefix, palette)
        for key, name in sheet_files.items():
            outputs[key] = rel(out_dir / name, repo)

    manifest_path = out_dir / f"{prefix}-manifest.json"
    write_manifest(
        manifest_path,
        prefix=prefix,
        cell=cell,
        animations=frame_counts,
        engine=args.engine,
        palette=palette is not None,
    )
    outputs["manifest"] = rel(manifest_path, repo)

    overlay = None
    overlay_meta = None
    verify_dir = args.verify_dir.resolve() if args.verify_dir else out_dir
    verify_dir.mkdir(parents=True, exist_ok=True)

    if args.tiles:
        idle_name = "idle" if "idle" in strips else animations[0]
        bg = parse_hex(args.overlay_bg) if args.overlay_bg else roles.get("sky_deep", (43, 74, 111))
        overlay, overlay_meta = overlay_idle_on_tiles(
            strips[idle_name].crop((0, 0, cell, cell)),
            args.tiles.resolve(),
            args.tile_top,
            args.tile_fill,
            args.tile_size,
            cell,
            bg,
        )
        overlay_1x = verify_dir / "idle-on-platform-1x.png"
        overlay_3x = verify_dir / "idle-on-platform-3x.png"
        overlay.save(overlay_1x)
        nn_integer(overlay, 3).save(overlay_3x)
        outputs["overlay_1x"] = rel(overlay_1x, repo)
        outputs["overlay_3x"] = rel(overlay_3x, repo)

    contact = build_contact_sheet(strips, overlay)
    contact_path = verify_dir / "contact-sheet.png"
    contact.save(contact_path)
    outputs["contact_sheet"] = rel(contact_path, repo)

    if args.engine == "godot" and snippet_path.is_file():
        snippet_dest = verify_dir / "godot-project-snippet.txt"
        shutil.copy2(snippet_path, snippet_dest)
        outputs["godot_project_snippet"] = rel(snippet_dest, repo)
        if template_path.is_file():
            shutil.copy2(template_path, verify_dir / "godot-texture.import.template")
            outputs["godot_import_template"] = rel(verify_dir / "godot-texture.import.template", repo)

    report = qa_report(
        strips,
        overlay_meta,
        credits_ok=True,
        outputs=outputs,
        selection_path=rel(selection, repo),
        cell=cell,
        tile_size=args.tile_size if args.tiles else None,
        palette=palette,
    )
    report["frame_counts"] = frame_counts
    report["prefix"] = prefix
    report["engine"] = args.engine
    report["lpc_toolkit"] = {
        "cli": find_cli(),
        "invocation": "subprocess",
        "work_dir": rel(work, repo),
    }
    report_path = verify_dir / "qa-report.json"
    report["outputs"] = outputs
    outputs["qa_report"] = rel(report_path, repo)
    report["outputs"] = outputs
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {"ok": report["ok"], "outputs": outputs, "qa": report}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="LPC pixelkit: JSON loadout → 64×64 east strips for any engine"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    build_p = sub.add_parser("build", help="render, slice east, optional remap/import/overlay, QA")
    build_p.add_argument("selection", type=Path)
    build_p.add_argument("--out", type=Path, required=True, help="delivery directory for PNG/CREDITS/manifest")
    build_p.add_argument("--engine", choices=("generic", "godot"), default="generic")
    build_p.add_argument("--palette", type=Path, help="optional JSON palette; omit to keep LPC colors")
    build_p.add_argument("--tiles", type=Path, help="optional tile directory; omit to skip overlay QA")
    build_p.add_argument("--tile-top", default="grass-top.png")
    build_p.add_argument("--tile-fill", default="grass-fill.png")
    build_p.add_argument("--tile-size", type=int, default=32)
    build_p.add_argument("--credits-dir", type=Path, help="extra directory to copy CREDITS into")
    build_p.add_argument("--verify-dir", type=Path, help="contact sheet / overlay / qa-report (default: --out)")
    build_p.add_argument("--prefix", help="output basename (default: selection name)")
    build_p.add_argument("--work-dir", type=Path, help="CLI scratch parent (default: <out>/.work)")
    build_p.add_argument("--repo-root", type=Path, default=Path.cwd(), help="paths in reports are relative to this")
    build_p.add_argument("--godot-res-prefix", help="Godot source_file prefix, e.g. res://assets/player/")
    build_p.add_argument("--godot-import-template", type=Path)
    build_p.add_argument("--godot-project-snippet", type=Path)
    build_p.add_argument("--cell", type=int, default=CELL_DEFAULT)
    build_p.add_argument("--east-row", type=int, default=EAST_ROW_DEFAULT)
    build_p.add_argument("--animation", action="append", dest="animation", help="repeatable; default idle walk run")
    build_p.add_argument("--overlay-bg", help="#RRGGBB behind tile overlay")
    build_p.add_argument("--strict", action="store_true", help="do not pass --allow-partial to lpc-toolkit")
    build_p.add_argument("--no-sheet", action="store_true", help="do not copy/remap the full LPC sheet")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.allow_partial = not args.strict
    args.copy_sheet = not args.no_sheet
    if args.cmd == "build":
        result = cmd_build(args)
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1
    raise SystemExit(f"unknown command {args.cmd}")


if __name__ == "__main__":
    sys.exit(main())
