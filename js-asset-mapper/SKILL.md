---
name: js-asset-mapper
description: 前端 JavaScript 项目资产、路由、API 和参数映射工具。用于审计 Vue、React、Angular、Vite、Webpack、Nuxt、Next、ASP.NET WebForms/Razor 以及混淆或构建后的 JS bundle，从源码、构建产物或运行时登录流中提取框架类型、入口页面、source map、webpack runtime/splitChunks/残留 chunk、异步 chunk、前端路由、请求封装、全量 API 端点、请求方法、参数来源、认证头、WebSocket/GraphQL/SignalR 调用和 Burp 请求模板。适合在 JS 安全审计前做全量资产盘点，并为敏感信息、路由守卫、未授权 API 和 DOM 漏洞审计提供输入。
---

# JS Asset Mapper - 前端资产、路由与 API 映射

从前端源码或构建产物中完整提取资产、路由、API、参数和认证上下文。只做映射和证据收集，不直接下漏洞结论。

## 核心原则

- 运行时证据优先于源码注释；构建产物优先于死代码。
- 源码优先，source map 次之，bundle 字符串和调用关系兜底。
- 本工具偏白盒/灰盒资产还原；Chrome MCP/浏览器只用于定点确认实际加载的入口、chunk、登录流和请求，不作为长期实时监听审计器。
- 对 Webpack/Vue CLI/Nuxt splitChunks 站点，Browser Network 不是完整资产清单；必须额外枚举 runtime 引用、source map 暴露、服务器可访问但当前未加载的独立 chunk/旧 chunk。
- 不省略接口：无法解析参数时也要输出端点、调用位置和未知字段。
- 全量 API 清单优先于风险筛选：低危、未验证、参数不完整、重复调用变体也要进入资产台账，供后续人工发包。
- 对混淆代码，把派生产物写入 `output_path/deobfuscated/`，不覆盖原文件。
- 输出必须能支撑后续 `/js-secret-audit`、`/js-route-guard-audit`、`/js-api-audit`。

参考共享规范：`../js-shared/OUTPUT_STANDARD.md`、`../js-shared/DEOBFUSCATION_STRATEGY.md`。
Webpack chunk 覆盖规范：`../js-shared/WEBPACK_CHUNK_COVERAGE.md`。

## 输入

- `source_path`: 前端项目根目录、`dist/`、静态站点目录、ASP.NET 前端目录或单个 bundle 所在目录。
- `output_path`: 默认 `{source_path}_js_audit/asset_mapper/`。
- 可选：一次性导出的 HAR/Network 资源清单，用于补充实际加载的异步 chunk 和 API 请求。

## 工作流程

### 1. 项目类型识别

检查并记录：

| 类型 | 证据 |
|------|------|
| Vue | `package.json` 中 `vue`、`.vue`、`router/index.*`、`createRouter`、`new VueRouter` |
| React/Next | `react`、`react-router`、`routes`、`pages/`、`app/` |
| Angular | `angular.json`、`@angular/router`、`canActivate` |
| Vite/Webpack | `vite.config.*`、`webpack.config.*`、chunk/manifest |
| ASP.NET 前端 | `.aspx/.ascx/.cshtml/.master`、`PageMethods`、`__doPostBack`、`WebResource.axd` |
| 构建产物 | `dist/`、`assets/*.js`、`static/js/*.chunk.js`、source map |

### 2. 运行静态扫描脚本

优先执行内置脚本生成初始索引：

```bash
python3 skills/js-asset-mapper/scripts/js_static_scan.py "{source_path}" \
  --output "{output_path}/scripts/js_static_scan.json" \
  --markdown "{output_path}/asset_mapper/{project_name}_js_asset_map_{YYYYMMDD_HHMMSS}.md"
```

如项目很大，先排除 `node_modules`；只有在做供应链或依赖源码审计时才加 `--include-node-modules`。

### 3. source map 与混淆处理

按 `../js-shared/DEOBFUSCATION_STRATEGY.md` 执行：

1. 查找 `sourceMappingURL` 和 `.map` 文件。
2. 解析 `sourcesContent`，提取原始源码路径、注释、API、密钥。
3. 对无 sourcemap 的 bundle 做格式化和字符串提取。
4. 对 `eval`、`new Function`、`atob`、`CryptoJS.*.decrypt`、`pako.inflate`、自定义 `_0x` 解码函数，记录还原步骤和派生产物。

### 3.0 Webpack splitChunks / 残留 chunk 枚举

当识别到 Webpack/Vue CLI/Nuxt 构建产物、`__webpack_require__`、`jsonp`、`runtime.js`、`app.js`、`chunk-vendors`、`static/js/*.js` 时，必须执行本步骤，避免只扫描浏览器当前加载的合并 chunk。

运行内置脚本：

```bash
python3 js-asset-mapper/scripts/webpack_chunk_inventory.py "{source_path}" \
  --base-url "{site_origin}/" \
  --output "{output_path}/asset_mapper/webpack_chunk_inventory.json" \
  --markdown "{output_path}/asset_mapper/webpack_chunk_inventory.md"
```

输出要进入后续审计输入：

- 将 `webpack_chunk_inventory.json` 中所有 `.js/.map` 资产加入 `runtime_assets/runtime_js_urls.txt` 或下载队列。
- 下载或复制所有可访问 JS 到 `runtime_assets/downloaded_chunks/`。
- 下载或复制所有 `.map` 到 `runtime_assets/downloaded_maps/`。
- 重新运行静态扫描和 `/js-secret-audit`，确保未被浏览器当前加载的独立 chunk/旧 chunk 也被扫描。

报告中为每个 chunk 标注：

- `runtime_loaded`：浏览器当前路径实际加载。
- `runtime_referenced`：webpack runtime 映射可推出。
- `server_present_unloaded`：服务器可直接访问但当前 Network 未加载。
- `sourcemap_referenced`：source map 暴露。
- `orphan/stale`：旧构建残留或未引用独立 chunk。

不得因为某 chunk 未被当前浏览器路由加载就从敏感信息、API、路由审计输入中删除。

### 3.1 可选运行时资源补充

当源码/构建目录不完整、路由使用懒加载或线上入口与本地文件不一致时，可以短时使用浏览器/MCP：

1. 访问入口页和少量高价值路由，导出 Network/HAR 或记录 JS/CSS/source map URL。
2. 下载或保存异步 chunk，写入 `output_path/runtime_assets/` 或加入扫描输入。
3. 记录“哪个路由/交互加载了哪个 chunk/请求”，然后回到静态扫描和人工审计。

不要把浏览器持续监听作为主流程；CORS、点击劫持、安全头缺失不属于资产映射结论。

### 3.2 后台登录流触发的资产补充

当目标是后台/管理端登录系统时，按 `../js-shared/RUNTIME_LOGIN_FLOW.md` 做短时登录流采集，并把运行时发现的资产纳入本工具输入。重点不是登录是否成功本身，而是补齐登录前后才加载的 JS、配置和 API。

必须记录和落盘：

- 登录页初始加载的 JS/CSS/runtime config/source map。
- 点击登录按钮后新增的 JS/chunk，例如验证码、RSA/JSEncrypt、CryptoJS、签名、nonce/timestamp 相关代码。
- 登录请求 URL、method、参数名、认证/签名字段、响应成功判定字段。
- 登录成功后 dashboard/layout/menu/userInfo/permission/router API 触发的异步 chunk。
- 访问少量高价值后台路由后新增的懒加载 chunk 和 `.map`。
- 每个运行时资源的触发动作：入口访问、点击登录、登录成功跳转、访问某后台路由。

输出建议：

```
{output_path}/runtime_assets/
├── login_flow.md
├── login_attempts.json
├── runtime_js_urls.txt
├── downloaded_chunks/
├── downloaded_maps/
└── runtime_asset_index.md
```

完成后重新运行或补充静态索引，确保 `runtime_assets/downloaded_chunks/` 和 `runtime_assets/downloaded_maps/` 中的文件也进入路由、API、敏感信息和客户端漏洞审计范围。

### 4. 路由映射

必须提取：

- 路由路径、name、component、redirect、children、alias。
- `meta.requiresAuth`、`meta.roles`、`permission`、`hidden`、菜单权限字段。
- 动态路由：`addRoute`、`addRoutes`、后端菜单转换、懒加载 import。
- 跳转点：`router.push/replace`、`navigate`、`history.push`、`window.location`。

输出示例：

```markdown
### R-001 /admin/user
| 项目 | 值 |
|------|----|
| 组件 | `src/views/admin/User.vue` |
| meta | `requiresAuth: true, roles: ['admin']` |
| 注册方式 | 静态 routes + lazy import |
| 入口文件 | `src/router/index.ts:42` |
| 关联 API | `GET /api/admin/users`, `DELETE /api/admin/users/{id}` |
```

### 5. API 与参数映射

重点还原请求封装链：

```
view/component → api module → request wrapper → axios/fetch/ajax → baseURL/interceptor
```

必须输出字段：

| 字段 | 要求 |
|------|------|
| HTTP 方法 | 从 `axios.get/post`、`method` 字段、封装默认值推断 |
| URL | 组装 `baseURL + path + query`，保留环境变量来源 |
| 参数 | Path、Query、Body、FormData、Header、Cookie、GraphQL variables |
| 认证 | Authorization、X-Token、Cookie、CSRF、租户头、签名头 |
| 调用位置 | 页面/组件/API 文件行号 |
| Burp 模板 | 每个可请求接口必须生成 |

全量 API 资产输出要求：

- 输出 `asset_mapper/api_inventory_seed.md/json`，作为 `/js-api-audit` 的全量台账种子。
- 同一接口多处调用时，保留所有调用位置和参数变体。
- 动态拼接无法完全解析时，保留模板路径和变量来源，不要删除。
- GraphQL/WebSocket/SignalR/ASP.NET 特殊调用必须进入同一份 API 资产台账。

### 6. ASP.NET 前端特殊提取

- `PageMethods.MethodName(...)` → `POST /Page.aspx/MethodName`。
- `[WebMethod]` 前端调用线索、`Sys.Net.WebServiceProxy.invoke`。
- `__doPostBack(eventTarget,eventArgument)`、隐藏字段 `__VIEWSTATE`、`__EVENTVALIDATION`。
- `.asmx`、`.ashx`、`.svc`、SignalR hub URL。

## 输出文件

```
{output_path}/
├── asset_mapper/
│   ├── {project_name}_js_asset_map_{timestamp}.md
│   ├── webpack_chunk_inventory.md
│   ├── webpack_chunk_inventory.json
│   ├── api_inventory_seed.md
│   └── api_inventory_seed.json
├── scripts/
│   └── js_static_scan.json
├── runtime_assets/
│   ├── login_flow.md
│   ├── runtime_js_urls.txt
│   ├── downloaded_chunks/
│   └── downloaded_maps/
└── deobfuscated/
    └── ...
```

## 自检

- [ ] 已识别项目类型和构建方式。
- [ ] 已检查 source map 和混淆/运行时解密特征。
- [ ] 若为 Webpack/splitChunks 构建，已枚举 runtime 引用、source map 引用、服务器可访问但当前未加载的 chunk，并将它们回流敏感信息扫描。
- [ ] 若存在后台登录系统，已采集登录页、登录提交和登录后首屏触发的异步 JS/chunk/source map，并回流静态索引。
- [ ] 所有发现的前端路由均有路径、组件、鉴权 meta。
- [ ] 所有 API 均有方法、URL、参数、认证头、调用位置和 Burp 模板。
- [ ] 已输出全量 API 资产台账种子；未验证或参数未知接口没有被过滤。
- [ ] ASP.NET PageMethods/WebMethod/SignalR 调用已单独提取。
- [ ] 输出 JSON/MD 可被后续 JS 审计 skill 使用。
