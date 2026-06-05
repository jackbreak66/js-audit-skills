#!/usr/bin/env python3
"""Static frontend JS/Vue/ASP.NET inventory helper.

Scans source or built frontend assets for likely API calls, routes, secrets,
storage/auth patterns, source maps, and client-side sinks. It is intentionally
regex/light-AST based so it works on mixed source and minified bundles.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

TEXT_EXTS = {
    ".js", ".jsx", ".ts", ".tsx", ".vue", ".mjs", ".cjs",
    ".html", ".htm", ".aspx", ".ascx", ".cshtml", ".master",
    ".json", ".map", ".env", ".config", ".xml", ".txt",
}
DEFAULT_IGNORES = {
    "node_modules", ".git", "dist/.vite", ".next/cache", ".nuxt", "coverage",
    "vendor", "vendors", "__pycache__", ".cache",
}
MAX_FILE_BYTES = 5 * 1024 * 1024

PATTERNS = {
    "api_call": [
        re.compile(r"\b(fetch)\s*\(\s*([`'\"])(?P<url>[^`'\"]{1,500})\2", re.I),
        re.compile(r"\baxios\s*\.\s*(get|post|put|delete|patch|request)\s*\(\s*([`'\"])(?P<url>[^`'\"]{1,500})\2", re.I),
        re.compile(r"\b\$\.ajax\s*\(\s*\{[^}]{0,800}?\burl\s*:\s*([`'\"])(?P<url>[^`'\"]{1,500})\1", re.I | re.S),
        re.compile(r"\b(url|baseURL|endpoint|apiUrl|requestUrl)\s*[:=]\s*([`'\"])(?P<url>(?:https?://|/)[^`'\"]{1,500})\2", re.I),
        re.compile(r"\b(PageMethods|Sys\.Net\.WebServiceProxy\.invoke)\b[^\n;]{0,500}", re.I),
        re.compile(r"\b(hubConnection|signalR|WebSocket|EventSource)\s*\([^\n;]{0,500}", re.I),
        re.compile(r"\b(gql|graphql)\b[^`'\"]{0,80}([`'\"])(?P<url>[^`'\"]{0,200})\2", re.I),
    ],
    "route": [
        re.compile(r"\bpath\s*:\s*([`'\"])(?P<path>/[^`'\"]{0,300})\1"),
        re.compile(r"\bname\s*:\s*([`'\"])(?P<name>[A-Za-z0-9_.:-]{1,120})\1"),
        re.compile(r"\bcomponent\s*:\s*(?:\(\)\s*=>\s*)?import\s*\(\s*([`'\"])(?P<component>[^`'\"]+)\1\s*\)"),
        re.compile(r"\brouter\.(?:push|replace)\s*\(\s*([`'\"])(?P<path>/[^`'\"]{0,300})\1"),
    ],
    "secret": [
        re.compile(r"(?P<kind>AKIA)[0-9A-Z]{16}"),
        re.compile(r"(?P<kind>aws_secret_access_key|secretAccessKey)\s*[:=]\s*['\"](?P<value>[A-Za-z0-9/+=]{32,})['\"]", re.I),
        re.compile(r"(?P<kind>private_key|BEGIN PRIVATE KEY)[\s\S]{0,80}-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        re.compile(r"(?P<kind>jwt)\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
        re.compile(r"(?P<kind>token|access_token|refresh_token|api[_-]?key|secret|client_secret|app[_-]?key|app[_-]?secret|password|passwd|pwd)\s*[:=]\s*['\"](?P<value>[^'\"]{8,})['\"]", re.I),
        re.compile(r"(?P<kind>firebase)AIza[0-9A-Za-z_-]{35}"),
        re.compile(r"(?P<kind>sentry_dsn)https://[0-9a-f]{16,32}@[\w.-]+/\d+", re.I),
        re.compile(r"(?P<kind>wechat|alipay|oauth)\b(appid|app_id|client_id)\s*[:=]\s*['\"](?P<value>[A-Za-z0-9_-]{8,})['\"]", re.I),
    ],
    "auth_storage": [
        re.compile(r"\b(localStorage|sessionStorage)\.(?:getItem|setItem|removeItem)\s*\([^\n;]{0,300}", re.I),
        re.compile(r"\bdocument\.cookie\b[^\n;]{0,300}", re.I),
        re.compile(r"\bAuthorization\s*[:=]\s*([`'\"])?Bearer\b[^\n,;}]{0,200}", re.I),
        re.compile(r"\b(beforeEach|beforeResolve|canActivate|AuthGuard|permission|roles?|requiresAuth|isLogin|isAuthenticated)\b[^\n;]{0,500}", re.I),
    ],
    "sink": [
        re.compile(r"\b(innerHTML|outerHTML|insertAdjacentHTML|document\.write|v-html|dangerouslySetInnerHTML)\b[^\n;]{0,300}", re.I),
        re.compile(r"\b(eval|Function|setTimeout|setInterval)\s*\([^\n;]{0,300}", re.I),
        re.compile(r"\b(postMessage|addEventListener\s*\(\s*['\"]message['\"])\b[^\n;]{0,500}", re.I),
        re.compile(r"\b(location\.(?:href|replace|assign)|window\.open)\s*\([^\n;]{0,300}", re.I),
        re.compile(r"\b(Object\.assign|\$\.extend|lodash\.merge|merge\s*\()\b[^\n;]{0,300}", re.I),
    ],
    "sourcemap": [
        re.compile(r"sourceMappingURL=(?P<map>[^\s*]+)"),
        re.compile(r"\"sourcesContent\"\s*:\s*\["),
    ],
}

METHOD_HINT = re.compile(r"\b(method|type)\s*:\s*['\"](?P<method>GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)['\"]", re.I)


def iter_files(root: Path, include_node_modules: bool) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        if not include_node_modules:
            dirnames[:] = [d for d in dirnames if d not in DEFAULT_IGNORES]
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix.lower() in TEXT_EXTS or name.startswith(".env"):
                try:
                    if p.stat().st_size <= MAX_FILE_BYTES:
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


def line_no(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def snippet(s: str, n: int = 240) -> str:
    return re.sub(r"\s+", " ", s.strip())[:n]


def redact_secret(value: str) -> str:
    value = value.strip()
    if len(value) <= 10:
        return "***"
    return value[:4] + "***" + value[-4:]


def scan_file(path: Path, root: Path) -> Dict[str, List[dict]]:
    text = read_text(path)
    rel = str(path.relative_to(root))
    results: Dict[str, List[dict]] = {k: [] for k in PATTERNS}
    for category, regexes in PATTERNS.items():
        for rx in regexes:
            for m in rx.finditer(text):
                item = {"file": rel, "line": line_no(text, m.start()), "match": snippet(m.group(0))}
                gd = {k: v for k, v in m.groupdict().items() if v}
                if category == "secret" and "value" in gd:
                    gd["redacted"] = redact_secret(gd.pop("value"))
                if category == "api_call":
                    win = text[max(0, m.start() - 300): min(len(text), m.end() + 500)]
                    mh = METHOD_HINT.search(win)
                    item["method_hint"] = mh.group("method").upper() if mh else "UNKNOWN"
                item.update(gd)
                results[category].append(item)
    return results


def detect_framework(root: Path, files: List[Path]) -> List[str]:
    names = {p.name.lower() for p in files}
    rels = {str(p.relative_to(root)).lower() for p in files}
    found = []
    package = root / "package.json"
    if package.exists():
        try:
            pkg = json.loads(read_text(package))
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            for fw, keys in {
                "Vue": ["vue", "@vue/cli-service", "vite"],
                "React": ["react", "react-router", "next"],
                "Angular": ["@angular/core"],
                "Nuxt": ["nuxt", "nuxt3"],
                "Webpack": ["webpack"],
                "Vite": ["vite"],
                "Axios": ["axios"],
            }.items():
                if any(k in deps for k in keys):
                    found.append(fw)
        except Exception:
            pass
    if any(p.endswith(".vue") for p in rels):
        found.append("Vue SFC")
    if any(p.endswith((".aspx", ".ascx", ".cshtml", ".master")) for p in rels):
        found.append("ASP.NET frontend")
    if "angular.json" in names:
        found.append("Angular")
    if "vite.config.js" in names or "vite.config.ts" in names:
        found.append("Vite")
    if "webpack.config.js" in names:
        found.append("Webpack")
    return sorted(set(found)) or ["Unknown/Mixed frontend"]


def summarize(results: Dict[str, List[dict]]) -> Dict[str, int]:
    return {k: len(v) for k, v in results.items()}


def write_markdown(report: dict, out: Path) -> None:
    lines = []
    lines.append(f"# JS 静态资产扫描报告\n")
    lines.append(f"- 扫描路径: `{report['root']}`")
    lines.append(f"- 文件数: {report['file_count']}")
    lines.append(f"- 框架识别: {', '.join(report['frameworks'])}\n")
    lines.append("## 统计\n")
    lines.append("| 类别 | 数量 |")
    lines.append("|------|------|")
    for k, v in report["summary"].items():
        lines.append(f"| {k} | {v} |")
    for category, items in report["findings"].items():
        lines.append(f"\n## {category}\n")
        if not items:
            lines.append("无")
            continue
        lines.append("| 文件 | 行 | 摘要 |")
        lines.append("|------|----|------|")
        for it in items[:500]:
            extra = it.get("url") or it.get("path") or it.get("name") or it.get("kind") or it.get("map") or ""
            summary = snippet((extra + " " + it.get("match", "")).strip(), 180).replace("|", "\\|")
            lines.append(f"| `{it['file']}` | {it['line']} | {summary} |")
        if len(items) > 500:
            lines.append(f"\n仅展示前 500 条，完整结果见 JSON。")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Scan frontend JS assets for routes, APIs, secrets and client-side risks")
    ap.add_argument("root", help="frontend source/build directory")
    ap.add_argument("--output", "-o", help="write JSON report path")
    ap.add_argument("--markdown", "-m", help="write Markdown summary path")
    ap.add_argument("--include-node-modules", action="store_true", help="include node_modules/vendor-like dirs")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    files = list(iter_files(root, args.include_node_modules))
    findings: Dict[str, List[dict]] = {k: [] for k in PATTERNS}
    file_hashes = []
    for p in files:
        try:
            data = p.read_bytes()
            file_hashes.append({"file": str(p.relative_to(root)), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
            r = scan_file(p, root)
            for k, items in r.items():
                findings[k].extend(items)
        except Exception as e:
            findings.setdefault("errors", []).append({"file": str(p), "error": str(e)})

    report = {
        "root": str(root),
        "file_count": len(files),
        "frameworks": detect_framework(root, files),
        "summary": summarize(findings),
        "findings": findings,
        "files": file_hashes,
    }
    if args.output:
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown:
        write_markdown(report, Path(args.markdown))
    if not args.output and not args.markdown:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"summary": report["summary"], "frameworks": report["frameworks"], "file_count": len(files)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
