# Webpack splitChunks / 残留 Chunk 覆盖规范

用于解决 webpack 打包站点中“浏览器只加载合并 chunk，但服务器仍暴露未加载的独立 chunk/旧 chunk，敏感信息只存在于未加载文件里”的漏报问题。

## 典型现象

- 浏览器 Network 只看到 `pages-a~pages-b~pages-c.<hash>.js` 合并 chunk。
- 服务器上仍可直接访问 `pages-a.<hash>.js` 独立 chunk 或旧构建残留。
- 硬编码密码、默认口令、测试账号、初始化参数可能只存在于独立 chunk，不存在于当前运行时加载的合并 chunk。
- 这些文件即使不被当前路由加载，只要可被 URL 直接访问，就属于前端可见信息泄露面。

## 处理原则

1. 不要把 Browser Network 当作完整 JS 资产清单；它只能证明“当前路径加载了什么”。
2. 对 webpack/Vue CLI/Nuxt 构建产物，必须区分：
   - `runtime_loaded`：浏览器当前路径实际加载。
   - `runtime_referenced`：webpack runtime 映射表可推出。
   - `server_present_unloaded`：服务器可访问但当前浏览器未加载。
   - `sourcemap_referenced`：source map 暴露。
   - `orphan/stale`：旧构建残留或未引用独立 chunk。
3. 敏感信息审计必须扫描所有可下载/可访问 JS，而不仅是 Network 中已加载 JS。
4. 在报告中同时给出“是否被浏览器当前加载”和“是否可直接访问”；未加载但可访问的 chunk 仍可作为漏洞证据。

## 必做枚举路径

### 1. 从入口 HTML 和 runtime chunk 提取

检查：

- `<script src=...>` / `<link href=...>`。
- `manifest.js`、`runtime.js`、`app.js`、`index.js`。
- webpack chunk filename 函数，例如：
  - `__webpack_require__.u`
  - `n.u = e => ...`
  - `jsonpScriptSrc`
  - `miniCssF`
- chunk id 到 chunk name/hash 的映射对象，例如：
  - `{123:"pages-login-routers-bindMobile"}`
  - `{123:"565d1b67"}`

### 2. 从 bundle 字符串中提取

全量搜索：

- `static/js/*.js`
- `js/*.js`
- `assets/*.js`
- `pages-*.js`
- `chunk-*.js`
- `*.js.map`
- `sourceMappingURL=`

### 3. 从 source map 提取

检查：

- `.js.map` 是否可访问。
- `sources` / `sourcesContent` 中的原始模块路径。
- `webpack://`、`src/pages`、`src/views`、`pages/login/routers` 等源码路径。

### 4. 从路由和 chunk 命名模式补齐

从路由表、动态 import、菜单路由中提取页面名，构造候选 chunk 名称：

- `pages-login-routers-{route}.{hash}.js`
- `views-{module}-{page}.{hash}.js`
- `chunk-{name}.{hash}.js`
- `static/js/{name}.{hash}.js`

只有已知 hash 或 runtime 映射中出现 hash 时才构造确定 URL；未知 hash 的候选应标为 `guess_only`，不能当作已确认资产。

## 推荐脚本

优先运行：

```bash
python3 js-asset-mapper/scripts/webpack_chunk_inventory.py "{source_path_or_runtime_assets}" \
  --base-url "{site_origin}/" \
  --output "{output_path}/asset_mapper/webpack_chunk_inventory.json" \
  --markdown "{output_path}/asset_mapper/webpack_chunk_inventory.md"
```

然后：

1. 将 `webpack_chunk_inventory.json` 中的 JS/map URL 写入 `runtime_assets/runtime_js_urls.txt` 或下载队列。
2. 对可下载 JS 全部落盘到 `runtime_assets/downloaded_chunks/`。
3. 对 `.map` 落盘到 `runtime_assets/downloaded_maps/`。
4. 将这些目录重新输入 `js_static_scan.py` 和 `/js-secret-audit`。

## 报告要求

发现敏感信息时必须记录：

| 字段 | 说明 |
|------|------|
| chunk 文件 | 命中的 JS/map 文件 |
| chunk 来源 | runtime_loaded / runtime_referenced / server_present_unloaded / sourcemap_referenced / orphan/stale |
| 当前浏览器是否加载 | 是/否/不确定 |
| 是否可直接访问 | 是/否/未验证 |
| 证据 | URL、文件 hash、行号、字符串上下文 |
| 风险说明 | 即使当前未加载，只要可访问仍是信息泄露 |

## 漏报防线

- 不要只扫描合并 chunk。
- 不要只扫描 Network 已加载文件。
- 不要因为独立 chunk “当前未被路由引用”就忽略其中的硬编码密码。
- 不要把 splitChunks 合并 chunk 中搜不到某个密码，误判为不存在泄露。
- 对旧构建残留、独立页面 chunk、source map 暴露源码中的默认密码，按“可公开下载构建产物泄露”处理。
