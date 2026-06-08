---
name: js-audit-pipeline
description: 前端 JavaScript 白盒/灰盒安全审计流水线。用于编排多个 JS 审计 skill，对 Vue、React、Angular、Vite、Webpack、Nuxt、Next、ASP.NET 前端源码、source map、混淆 bundle 和构建产物执行源码优先的审计：资产和路由 API 映射、webpack splitChunks/残留 chunk 枚举、全量前后端交互 API 台账、运行时登录流与异步 chunk 采集、后台弱口令小字典验证、硬编码敏感信息泄露、登录逻辑和路由守卫绕过、前后端 API 未授权及参数审计、DOM XSS、postMessage、开放跳转、原型污染、客户端存储和供应链风险，并输出可复现请求模板、全量 API 清单和交叉验证报告。
---

# JS 全链路安全审计流水线

参考 Java 审计流水线的“先资产映射，再专项审计，再交叉验证，再质量校验”思路，为前端 JS 项目建立红队视角审计链路。

## 定位与边界

- **默认定位是白盒/灰盒 JS 代码审计**：以源码、构建产物、source map、静态资源目录、可下载 chunk 为主要证据。
- **运行时浏览器/MCP 只做定点补证**：用于确认入口 HTML 实际加载哪些 chunk、某个路由懒加载了哪个异步 JS、某个请求是否真实发出；不要让 Claude Code 长时间“盯着浏览器”实时分析所有异步加载代码。
- **异步 chunk 的推荐处理方式**：通过入口 HTML、manifest、sourceMappingURL、Network/HAR 或一次性资源清单把 JS 文件落盘/索引，再回到静态分析链路；运行时观察结果只作为“当前生产加载证据”。
- **Webpack splitChunks/残留 chunk 必须额外覆盖**：浏览器 Network 只代表当前路径加载集合，不代表服务器全部可访问 JS。必须枚举 runtime 引用、source map、独立 chunk、旧 chunk；未被当前浏览器加载但可直接访问的 JS 也要进入敏感信息和 API 扫描。
- **不做泛化 Web 配置扫描器**：CORS、点击劫持、缺失 CSP/X-Frame-Options 等响应头问题默认进入“环境加固/待运行时验证”，不进入 P0/P1 高风险队列，除非已经转化为可复现的 API 越权、敏感数据泄露或账号影响。

## 输入

- `source_path`: 前端源码、构建产物、ASP.NET 前端目录或静态资源目录。
- `output_path`: 默认 `{source_path}_js_audit`。
- 可选：测试 Host、普通用户 Cookie/Token、低权限账号、是否允许对沙箱服务发起验证请求、是否允许对授权后台登录页做弱口令小字典测试、可选的一次性 HAR/Network 资源清单。

## 流程总览

```
阶段1: 资产还原与索引
  └─ js-asset-mapper: 框架/入口/source map/webpack chunk inventory/路由/API/参数/认证头

阶段1.5: 运行时登录流采集（仅授权测试 Host）
  ├─ 识别后台登录页、登录接口、验证码/2FA/频控
  ├─ Chrome MCP 短时模拟登录提交，采集登录请求与 storage/cookie 变化
  ├─ 无验证码时执行固定弱口令小字典；成功即停止
  ├─ 可识别验证码时允许一次性辅助提交；不可识别则跳过自动提交
  └─ 下载登录前、登录中、登录后触发的异步 JS/chunk/source map 并回流静态审计

阶段2: 专项静态审计并行
  ├─ js-secret-audit: 硬编码敏感信息、source map、环境配置泄露
  ├─ js-route-guard-audit: 登录逻辑、路由守卫、菜单权限绕过
  ├─ js-api-audit: API 清单、参数、未授权/越权验证模板
  └─ js-client-vuln-audit: DOM XSS、postMessage、开放跳转、原型污染等

阶段3: 交叉分析
  ├─ 将敏感 Token/baseURL 注入 API 验证条件
  ├─ 将路由守卫绕过关联到后台 API
  ├─ 将 source map/反混淆结果补充到 API 与敏感信息清单
  └─ 对 P0/P1 高价值后台功能生成验证队列

阶段4: 可复现验证
  ├─ NoAuth: 无登录态也必须执行去认证请求
  ├─ LowPriv: 普通用户请求后台接口
  ├─ ParamTamper: id/userId/tenantId/orgId/role/path/url 篡改
  ├─ SafeMutationProbe: 写操作使用非法/不存在 ID、canary、dryRun/validateOnly 做低副作用探测
  └─ Browser: 定点确认路由、懒加载 chunk、storage 绕过或具体请求

阶段5: 汇总报告与质量校验
  └─ 输出 final_report.md、api_inventory_full.md/json/csv、high_risk_api.md、all_api_replay_templates.http、evidence_index.md
```

## 阶段1：资产还原

执行 `/js-asset-mapper`，必须产出：

- 项目类型、构建方式、入口 HTML、主要 bundle/chunk。
- Webpack/Vue CLI/Nuxt 站点必须产出 `webpack_chunk_inventory.md/json`，覆盖 splitChunks 合并 chunk、runtime 引用 chunk、source map、服务器可访问但当前未加载的独立 chunk/旧 chunk。
- source map 状态和反混淆派生产物。
- 完整前端路由表和路由 meta。
- 完整 API 表、参数、认证头和 Burp 模板。

输出目录：`{output_path}/asset_mapper/`、`{output_path}/scripts/js_static_scan.json`、`{output_path}/deobfuscated/`。

## 阶段1.5：运行时登录流与异步资产采集

当目标表现为后台/管理端登录系统时，允许短时使用 Chrome MCP 采集登录流证据；详细执行准则见 `../js-shared/RUNTIME_LOGIN_FLOW.md`。本阶段目的不是做长时间在线扫描，而是把**登录触发的异步 JS 和认证上下文**变成后续静态审计原料。

### 触发条件

满足任一条件即可进入本阶段：

- URL、标题或页面文案包含 `login/admin/manage/system/console/dashboard/后台/管理系统` 等特征。
- 页面存在用户名/密码表单，或 JS 中出现 `login/auth/token/menu/permission/userInfo/router` 等调用链。
- 阶段1发现后台路由、菜单权限 API、登录接口或动态路由懒加载。

### 执行规则

1. 登录前记录入口 URL、表单字段、验证码/2FA/租户字段、初始 JS/CSS/config/source map URL。
2. 如果存在**图片验证码**，优先调用本地 `mmx vision describe` 自动识别（支持普通文本验证码和算术验证码）。识别成功则自动填入并继续弱口令小字典探测；识别失败或 `mmx` 不可用时，跳过自动弱口令提交，记录原因。
3. 如果验证码为滑块、短信、扫码、MFA，或出现账户锁定、频控提示，立即停止自动尝试。
4. 无验证码时执行小字典弱口令测试，默认组合见 `../js-shared/RUNTIME_LOGIN_FLOW.md`；成功即停止，不扩大爆破。
5. 成功登录后采集 token/cookie/localStorage/sessionStorage 变化、dashboard/menu/userInfo/permission/router API、登录后新增 chunk/source map。
6. 所有新发现 JS、source map、runtime config 写入 `{output_path}/runtime_assets/`，并重新纳入阶段1/阶段2的静态输入。

### 输出

```
{output_path}/runtime_assets/
├── login_flow.md
├── login_attempts.json          # 密码脱敏，记录成功/失败/跳过原因
├── runtime_js_urls.txt
├── downloaded_chunks/
├── downloaded_maps/
└── runtime_asset_index.md
```

若识别为后台登录系统、无验证码、默认弱口令未成功，最终报告必须提示：建议在授权范围内由人工进行密码爆破/口令强度验证，并结合账号锁定、频控和测试窗口控制风险。

## 阶段2：专项审计

### 2.1 敏感信息

执行 `/js-secret-audit`：

- 审计硬编码密钥、Token、账号、内部域名、环境配置。
- Webpack 站点必须扫描 `webpack_chunk_inventory` 和 `runtime_assets/downloaded_chunks` 中所有 JS/map；不得只扫描 Browser Network 已加载的合并 chunk。
- 将可用凭证、baseURL、签名参数输出到 `cross_analysis/secret_to_api_inputs.md`。

### 2.2 路由守卫

执行 `/js-route-guard-audit`：

- 审计 Vue/React/Angular/ASP.NET 登录与角色判断。
- 输出可绕过路由矩阵和关联 API，不能单独把 UI 绕过判高危。

### 2.3 API 未授权

执行 `/js-api-audit`：

- 全量 API 台账是硬性产物：所有发现的前后端交互 API 都必须进入 `api_audit/api_inventory_full.md/json/csv` 和最终报告的“完整 API 台账/附录”，不能只输出高危或已验证接口。
- 对未验证接口也要列出方法、final_baseURL、路径、参数摘要、认证方式、调用位置、验证状态和手工发包建议。
- 对每个接口还原参数并生成动态验证请求；授权 Host 存在时，默认执行请求并观察后端响应。
- 没有有效登录态时也必须执行 `NoAuth`，不能仅因“无登录态”标记 `StaticOnly`。
- 对所有 `POST` JSON 或 body 形态未知接口，至少额外执行一次空 JSON `{}` 请求，避免遗漏“空体也有业务响应”的接口。
- 对写操作/高副作用接口，使用非法/不存在 ID、canary、`dryRun/validateOnly/preview` 等低副作用参数探测鉴权、参数校验和业务成功响应。
- 后端返回业务成功的接口必须在报告中具体上报 HTTP 状态、业务 `code/msg/success/data` 和关键字段摘要。
- 优先后台管理、用户、角色、权限、租户、导入导出、文件、报表接口。

### 2.4 客户端漏洞

执行 `/js-client-vuln-audit`：

- 审计 DOM XSS、postMessage、开放跳转、原型污染、Service Worker、依赖与本地存储。
- CORS、点击劫持、缺失 CSP/XFO 仅作为低优先级环境加固项记录；不得标记为高危或严重。

## 阶段3：交叉分析规则

### P0/P1 优先级

| 优先级 | 条件 |
|--------|------|
| P0 | 无需认证可调用后台关键 API；有效高权限 Token/云密钥泄露；路由绕过 + 后端 API 无鉴权 |
| P1 | 低权限可调用管理 API；IDOR/tenantId/orgId 篡改；source map 暴露后台源码和关键接口 |
| P2 | 仅前端 UI 绕过、低敏配置泄露、待验证 DOM 风险 |
| P3 | 代码质量、示例配置、不可达 mock |

> 噪音控制：CORS、点击劫持、缺失安全响应头、缺失 CSP 本身不进入 P0/P1；如果必须记录，放入 P3/加固项。若发现它们只是帮助触发了真实 API 越权或敏感数据泄露，按真实根因（API/SECRET/XSS）评级，而不是按 CORS/Clickjacking 评级。

### 交叉输出

```
{output_path}/cross_analysis/
├── high_risk_routes.md          # P0/P1 路由和关联 API
├── high_risk_api.md             # P0/P1 API 验证队列
├── api_inventory_full.md        # 全量 API 台账索引或汇总
├── secret_to_api_inputs.md      # 凭证/密钥对 API 的影响
├── all_api_replay_templates.http # 所有接口的手工发包模板
├── replay_templates.http        # 高风险/已验证接口请求
└── evidence_index.md            # 文件、行号、bundle、source map、派生产物索引
```

## 阶段4：验证模板

对每个高风险 API 输出并尽量执行动态验证请求；请求执行结果要写入 `api_audit/dynamic_validation_results.*`，后端业务成功响应要写入 `api_audit/backend_success_responses.md`。

基础模板：

```http
### NoAuth - 去除所有认证头
GET /api/admin/users?pageNum=1&pageSize=10 HTTP/1.1
Host: {{host}}
Accept: application/json

### LowPriv - 普通用户态
GET /api/admin/users?pageNum=1&pageSize=10 HTTP/1.1
Host: {{host}}
Authorization: Bearer {{low_priv_token}}
Accept: application/json

### ParamTamper - 敏感参数篡改
POST /api/user/update HTTP/1.1
Host: {{host}}
Authorization: Bearer {{low_priv_token}}
Content-Type: application/json

{"userId":"1002","role":"admin","tenantId":"1"}

### PostEmptyJsonProbe - POST 空 JSON 探测
POST /api/user/page HTTP/1.1
Host: {{host}}
Content-Type: application/json
Accept: application/json

{}
```

高副作用接口不能直接省略，应优先做低副作用探测：

```http
### SafeMutationProbe - 不存在 ID / canary / dryRun
POST /api/admin/user/update HTTP/1.1
Host: {{host}}
Content-Type: application/json
Accept: application/json

{"id":999999999,"username":"audit_probe_{{timestamp}}","remark":"security_test_noop","dryRun":true,"validateOnly":true}
```

如果响应出现 `success=true`、`code=0/200`、返回对象、任务 ID、文件 URL、数据列表等，必须在报告中具体展开，不允许只写“StaticOnly”或“有响应”。

对前端路由绕过输出浏览器步骤：

```javascript
localStorage.setItem('token', 'test')
localStorage.setItem('roles', '["admin"]')
location.href = '/#/admin/user'
```

浏览器/MCP 使用规则：

1. 只围绕明确问题做短时验证，例如“访问 `/admin/user` 是否加载 `chunk-admin.js`”或“点击导出按钮是否请求 `/api/export`”。
2. 对后台登录系统，允许围绕登录页、登录提交、登录成功首屏和少量高价值路由做短时采集，重点获取登录触发的异步 JS/chunk/source map、认证上下文和菜单/权限 API。
3. 优先导出 Network/HAR、资源 URL、响应状态和关键请求，再把 JS/chunk 作为静态输入处理。
4. 对 Webpack splitChunks 站点，Network/HAR 只是 `runtime_loaded` 证据；还必须结合 `webpack_chunk_inventory` 检查当前未加载但可访问的独立 chunk/旧 chunk。
5. 不要求持续监控所有异步请求；不能因为浏览器里看到某响应头缺失就直接给高危结论。

## 阶段5：质量校验

最终报告必须回答：

1. 是否有生产可达的敏感信息泄露。
2. 是否存在可直接访问后台页面的前端路由绕过。
3. 路由绕过是否关联到后端未授权 API。
4. 是否列出**全量前后端交互 API 台账**：总数、来源、参数、调用位置、认证方式、验证状态；不能只列高危或已验证接口。
5. 未验证 API 是否仍有手工发包模板和参数占位建议，避免人工测试遗漏。
6. 未授权 API 是否有请求参数、请求模板和验证状态。
7. 授权 Host 存在时，接口是否已动态请求验证；无登录态是否仍完成 NoAuth；写操作是否做了低副作用探测。
8. 后端业务成功响应是否已具体上报字段证据，而不是仅给 StaticOnly/模板。
9. Webpack splitChunks/残留 chunk 是否已覆盖；未被当前浏览器加载但可直接访问的 chunk 是否已进入敏感信息扫描。
10. 混淆/source map/ASP.NET 特殊前端是否已覆盖。
11. 若存在后台登录系统，是否已记录验证码/2FA状态、弱口令小字典结果、登录成功判定依据、登录触发的异步 JS 是否回流审计。
12. 红队补充面：DOM XSS、postMessage、开放跳转、原型污染、客户端存储、供应链是否已覆盖。
13. CORS、点击劫持、缺失 CSP/XFO 等低信噪比项是否已降噪：未进入高危/严重列表，仅在加固项或验证备注中出现。

## 最终输出

`final_report.md` 必须包含“完整 API 台账”章节或附录，至少列出每个 API 的 `ID、方法、baseURL、路径、参数摘要、认证方式、调用位置、验证状态`。如果接口数量过大，也必须在最终报告中给出全量表的索引、总数、分组统计和 `api_audit/api_inventory_full.md/json/csv` 的明确路径；不能只给高风险 API 摘要。

```
{output_path}/
├── asset_mapper/
│   ├── webpack_chunk_inventory.md
│   └── webpack_chunk_inventory.json
├── secret_audit/
├── route_guard_audit/
├── api_audit/
│   ├── api_inventory_full.md
│   ├── api_inventory_full.json
│   ├── api_inventory_full.csv
│   ├── all_api_replay_templates.http
│   └── dynamic_validation_results.md
├── client_vuln_audit/
├── cross_analysis/
├── runtime_assets/
├── deobfuscated/
└── final_report.md
```

## 执行建议

- 如果允许并行 agent，阶段2四个专项可并行；否则按 asset → secret → route → api → client → cross 顺序执行。
- 对大 bundle 先用脚本生成索引，再定点阅读高价值文件。
- 所有动态请求只针对用户授权的沙箱目标；未授权外部目标只输出模板不发包。对授权目标，不要因为无有效登录态而跳过接口验证，至少执行 NoAuth 并记录后端响应。
