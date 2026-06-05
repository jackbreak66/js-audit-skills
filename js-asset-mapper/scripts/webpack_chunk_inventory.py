#!/usr/bin/env python3
"""Heuristic webpack chunk inventory helper.

Purpose: enumerate JS/CSS/map assets referenced by webpack runtime, source maps,
HTML, and bundle strings, including chunks that are present/referenced but not
necessarily loaded by the browser in one runtime path.

It is intentionally dependency-free and conservative: findings are candidates
for audit input, not proof that a chunk is executed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from urllib.parse import urljoin
from typing import Dict, Iterable, List, Tuple

TEXT_EXTS = {".html", ".htm", ".js", ".mjs", ".cjs", ".json", ".map", ".txt"}
IGNORE_DIRS = {"node_modules", ".git", ".cache", "coverage", "__pycache__"}
MAX_BYTES = 25 * 1024 * 1024

ASSET_RE = re.compile(r"(?P<path>(?:[A-Za-z0-9_./~@-]+/)?[A-Za-z0-9_.~@/-]+\.(?:js|css|map))(?:[?#][^'\"`\s<>)]*)?", re.I)
SRC_RE = re.compile(r"(?:src|href)\s*=\s*['\"](?P<url>[^'\"]+\.(?:js|css|map)(?:[?#][^'\"]*)?)['\"]", re.I)
SM_RE = re.compile(r"sourceMappingURL\s*=\s*(?P<map>[^\s*]+)", re.I)
PAIR_RE = re.compile(r"(?P<key>[A-Za-z_$][\w$-]*|\d+|['\"][^'\"]+['\"])\s*:\s*['\"](?P<val>[^'\"]{1,240})['\"]")
HEX_RE = re.compile(r"^[a-f0-9]{6,32}$", re.I)
JS_EXT_RE = re.compile(r"\.(?:js|css|map)(?:$|[?#])", re.I)


def iter_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix.lower() in TEXT_EXTS:
                try:
                    if p.stat().st_size <= MAX_BYTES:
                        yield p
                except OSError:
                    continue


def read_text(path: Path) -> str:
    data = path.read_bytes()
    for enc in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", errors="replace")


def line_no(text: str, off: int) -> int:
    return text.count("\n", 0, off) + 1


def clean_asset_path(p: str) -> str:
    p = p.strip().strip('"\'`')
    p = p.split("#", 1)[0].split("?", 1)[0]
    while p.startswith("./"):
        p = p[2:]
    return p


def add_asset(assets: Dict[str, dict], path: str, kind: str, file: str, line: int, evidence: str, base_url: str | None = None):
    path = clean_asset_path(path)
    if not path or path.startswith(("data:", "blob:")):
        return
    item = assets.setdefault(path, {"path": path, "kind": kind, "sources": [], "url": urljoin(base_url, path) if base_url else ""})
    if kind not in item["kind"]:
        item["kind"] += "," + kind
    src = {"file": file, "line": line, "evidence": evidence[:260]}
    if src not in item["sources"]:
        item["sources"].append(src)


def parse_object_maps(text: str) -> List[Tuple[int, int, Dict[str, str]]]:
    maps: List[Tuple[int, int, Dict[str, str]]] = []
    # Small balanced-object approximation. Webpack chunk maps are usually compact.
    for m in re.finditer(r"\{[^{}]{10,6000}\}", text):
        pairs = {}
        for pm in PAIR_RE.finditer(m.group(0)):
            key = pm.group("key").strip('"\'')
            val = pm.group("val")
            pairs[key] = val
        if len(pairs) >= 2:
            maps.append((m.start(), m.end(), pairs))
    return maps


def compose_from_runtime_maps(text: str, rel: str, assets: Dict[str, dict], base_url: str | None):
    maps = parse_object_maps(text)
    name_maps = []
    hash_maps = []
    direct_asset_maps = []
    for start, end, mp in maps:
        vals = list(mp.values())
        if any(JS_EXT_RE.search(v) for v in vals):
            direct_asset_maps.append((start, end, mp))
        elif sum(1 for v in vals if HEX_RE.match(v)) >= max(2, len(vals) // 2):
            hash_maps.append((start, end, mp))
        elif any(("pages-" in v or "chunk" in v.lower() or "~" in v or "/" in v or "routers" in v.lower()) for v in vals):
            name_maps.append((start, end, mp))

    for start, end, mp in direct_asset_maps:
        for _, val in mp.items():
            if JS_EXT_RE.search(val):
                add_asset(assets, val, "webpack_runtime_direct", rel, line_no(text, start), "chunk map direct asset", base_url)

    # Pair nearby name and hash maps by overlapping keys. Covers common webpack runtime filename functions:
    # ({id:"pages-x"}[id]||id)+"."+{id:"hash"}[id]+".js"
    for ns, ne, names in name_maps:
        for hs, he, hashes in hash_maps:
            if abs(hs - ne) > 4000 and abs(ns - he) > 4000:
                continue
            common = set(names) & set(hashes)
            if not common:
                continue
            ctx = text[max(0, min(ns, hs) - 300): min(len(text), max(ne, he) + 300)]
            ext = ".css" if ".css" in ctx and ".js" not in ctx else ".js"
            prefix = ""
            pm = re.search(r"['\"](?P<prefix>(?:static/)?(?:js|css|assets?)/)['\"]\s*\+", ctx)
            if pm:
                prefix = pm.group("prefix")
            for key in sorted(common):
                name = names[key]
                h = hashes[key]
                if JS_EXT_RE.search(name):
                    candidate = name
                else:
                    candidate = f"{prefix}{name}.{h}{ext}"
                add_asset(assets, candidate, "webpack_runtime_composed", rel, line_no(text, min(ns, hs)), f"chunk id {key}: {name} + {h}", base_url)


def scan_file(path: Path, root: Path, assets: Dict[str, dict], base_url: str | None):
    text = read_text(path)
    rel = str(path.relative_to(root))
    for rx, kind in ((SRC_RE, "html_src"), (ASSET_RE, "literal_asset"), (SM_RE, "source_map_ref")):
        for m in rx.finditer(text):
            val = m.groupdict().get("url") or m.groupdict().get("path") or m.groupdict().get("map")
            if val:
                add_asset(assets, val, kind, rel, line_no(text, m.start()), m.group(0), base_url)
    compose_from_runtime_maps(text, rel, assets, base_url)

    if path.suffix.lower() == ".map":
        try:
            data = json.loads(text)
            for src in data.get("sources", [])[:20000]:
                if isinstance(src, str):
                    add_asset(assets, src, "sourcemap_source", rel, 1, "sources[]", base_url)
        except Exception:
            pass


def write_markdown(assets: List[dict], out: Path):
    lines = ["# Webpack/前端构建产物 Chunk 资产清单", ""]
    lines.append(f"- 发现资产候选: {len(assets)}")
    lines.append("- 说明: 这些资产包含浏览器已加载、webpack runtime 引用、source map 暴露或 bundle 字符串中出现的候选；未被浏览器加载但可直接访问的旧 chunk/独立 chunk 也应进入敏感信息扫描。")
    lines.append("")
    lines.append("| 路径 | 类型 | URL | 来源数 | 首个来源 |")
    lines.append("|------|------|-----|--------|----------|")
    for a in assets:
        src = a["sources"][0] if a.get("sources") else {}
        first = f"`{src.get('file','')}`:{src.get('line','')} {src.get('evidence','')}".replace("|", "\\|")
        lines.append(f"| `{a['path']}` | {a['kind']} | {a.get('url','')} | {len(a.get('sources', []))} | {first} |")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract webpack/runtime/literal JS/CSS/map asset candidates")
    ap.add_argument("root", help="frontend build/source/runtime_assets directory")
    ap.add_argument("--base-url", help="optional site base URL for candidate URL construction")
    ap.add_argument("--output", "-o", help="write JSON path")
    ap.add_argument("--markdown", "-m", help="write Markdown path")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    assets: Dict[str, dict] = {}
    for p in iter_files(root):
        try:
            scan_file(p, root, assets, args.base_url)
        except Exception as e:
            add_asset(assets, f"ERROR:{p}", "error", str(p), 0, str(e), None)

    items = sorted(assets.values(), key=lambda x: x["path"])
    report = {"root": str(root), "base_url": args.base_url or "", "asset_count": len(items), "assets": items}
    if args.output:
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown:
        write_markdown(items, Path(args.markdown))
    if not args.output and not args.markdown:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"asset_count": len(items)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
