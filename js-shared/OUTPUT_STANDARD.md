# 前端 JS 审计统一输出规范

## 硬约束

1. 报告必须写入用户指定的 `output_path`，不得散落到项目源码目录。
2. 每个漏洞必须有证据链：`文件位置/代码片段摘要 → 数据来源 → 触发路径/API → 影响 → 验证方式`。
3. 不能把“前端隐藏菜单/路由”单独判为高危；必须交叉验证后端 API 是否也缺鉴权。
4. 对混淆或构建产物，必须记录还原步骤、source map 状态、bundle 文件名和 hash/大小。
5. 所有 Burp/HTTP 模板必须包含方法、路径、Host、认证头是否需要、Content-Type、Body 示例。
6. 如果接口参数由前端代码拼接或序列化，必须输出参数来源和可控字段。
7. 所有 `【填写】` 占位符必须替换；无内容填 `无` 或 `N/A`。
8. CORS、点击劫持、缺失 `X-Frame-Options`/`frame-ancestors`、缺失/宽松 CSP、通用安全响应头缺失默认写入“低优先级加固项”，不得标记为高危或严重。
9. Chrome MCP/浏览器运行时证据必须服务于明确验证点；不要把持续监听到的响应头缺失或异步资源存在本身当作漏洞。
10. 对后台登录系统，运行时登录流和弱口令小字典结果必须写清验证码/2FA状态、执行/跳过原因、成功判定依据；密码和 token/cookie 默认脱敏。
11. 授权 Host 存在时，API 不能仅停留在静态提取：无有效登录态也必须执行 `NoAuth`；写操作/高副作用接口必须尝试低副作用探测或写明明确阻断原因。
12. 后端返回业务成功的动态响应必须具体上报：HTTP 状态、业务 `code/msg/success`、关键 `data` 字段、影响判断和证据文件；不能只写“有响应/请求成功/StaticOnly”。
13. 禁止使用“`StaticOnly` 表示因无有效登录态或接口含写操作，未进行动态请求验证，仅做静态提取登记”这类笼统注释；`StaticOnly` 只能用于有明确阻断原因的少数接口。
14. 全量 API 台账是硬性输出：所有发现的前后端交互 API 都必须列入报告或附录，包含方法、baseURL、路径、参数摘要、认证方式、调用位置和验证状态；不能只列高危、已验证或成功响应接口。
15. 未验证 API 也必须列出手工发包所需信息：参数占位、缺失字段、建议认证态和请求模板，避免人工测试遗漏。
16. Webpack/Vue CLI/Nuxt splitChunks 站点必须输出 chunk 覆盖说明：当前浏览器加载 chunk、runtime 引用 chunk、source map、服务器可访问但当前未加载的独立 chunk/旧 chunk；未加载但可访问 chunk 中的硬编码密码仍按泄露上报。

## 输出目录

```
{output_path}/
├── asset_mapper/          # 资产、路由、API 原始清单
├── secret_audit/          # 敏感信息泄露
├── route_guard_audit/     # 前端登录/路由守卫
├── api_audit/             # 全量 API 台账、未授权/越权动态验证、响应证据与请求模板
├── client_vuln_audit/     # DOM、postMessage、依赖等客户端攻击面
├── cross_analysis/        # 交叉分析和验证优先级
├── runtime_assets/        # 登录流、运行时 JS/chunk/source map/HAR/资源清单
├── deobfuscated/          # 格式化/反混淆/还原 source map 的派生产物
└── scripts/               # 运行时脚本、中间 JSON、扫描索引
```

## Webpack Chunk 覆盖块

当识别到 Webpack/Vue CLI/Nuxt 构建产物时，报告必须包含：

```markdown
## Webpack/splitChunks 资产覆盖

| chunk/文件 | 来源类型 | 当前浏览器是否加载 | 是否可直接访问 | 来源证据 | 是否进入敏感信息扫描 |
|------------|----------|------------------|----------------|----------|----------------------|
| static/js/pages-login-routers-bindMobile.565d1b67.js | server_present_unloaded | 否 | 是/未验证 | webpack_chunk_inventory / URL | 是 |
```

来源类型取值：

- `runtime_loaded`
- `runtime_referenced`
- `server_present_unloaded`
- `sourcemap_referenced`
- `orphan/stale`

如果硬编码密码、默认口令、测试账号只出现在 `server_present_unloaded` 或 `orphan/stale` chunk 中，仍必须进入“账号口令与默认凭证表”，并说明：当前浏览器路径未加载不等于不泄露，只要 JS 可直接访问即可被攻击者读取。

## 文件命名

```
{project_name}_{skill_type}_{YYYYMMDD_HHMMSS}.md
```

| skill_type | 对应 Skill |
|------------|------------|
| js_asset_map | js-asset-mapper |
| js_secret_audit | js-secret-audit |
| js_route_guard_audit | js-route-guard-audit |
| js_api_audit | js-api-audit |
| js_client_vuln_audit | js-client-vuln-audit |
| js_audit_pipeline | js-audit-pipeline |

## 通用漏洞详情块

```markdown
### [【漏洞编号】] 【漏洞标题】

| 项目 | 信息 |
|------|------|
| 严重等级 | 【🔴/🟠/🟡/🔵 + 等级 + CVSS】 |
| 可达性 (R) | 【0-3 + 理由】 |
| 影响范围 (I) | 【0-3 + 理由】 |
| 利用复杂度 (C) | 【0-3 + 理由】 |
| 可利用性 | 【✅已确认 / ⚠️待验证 / ❌不可利用 / 🔍环境依赖】 |
| 位置 | 【文件:行号 或 bundle:offset】 |
| 触发入口 | 【路由/API/事件/页面】 |
| 证据摘要 | 【关键代码与数据流摘要，不贴长篇代码】 |

#### 数据流
`source → transform → sink`

#### 验证方式
```http
【可复现请求或浏览器控制台步骤】
```

#### 修复建议
【最小修复建议】
```

## API 动态验证与后端成功响应块

授权 Host 存在时，最终报告必须包含本节。每个接口至少应有一条执行结果或明确阻断原因；无登录态不构成阻断理由，应执行 `NoAuth`。

## 完整 API 台账块

最终报告或 API 审计报告必须包含全量 API 台账；如果最终报告只做总览，也必须明确引用 `api_audit/api_inventory_full.md/json/csv`，并保证这些文件存在。台账不得只包含高危或已验证接口。

```markdown
## 完整 API 台账

| ID | 方法 | baseURL | 路径/模板路径 | 页面/组件/事件 | path参数 | query参数 | body/form参数 | header/cookie | 认证方式 | 参数来源 | 调用位置 | 验证状态 | 手工测试建议 |
|----|------|---------|---------------|---------------|----------|-----------|--------------|---------------|----------|----------|----------|----------|--------------|
| API-001 | GET | https://example.test | /api/user/list | UserList.vue mounted | 无 | pageNum,pageSize,keyword | 无 | Authorization | Bearer token | queryParams 默认值 | src/api/user.ts:12 | NoAuthTested | 去认证、低权、pageSize扩大 |
```

全量 API 台账文件建议：

```text
api_audit/api_inventory_full.md
api_audit/api_inventory_full.json
api_audit/api_inventory_full.csv
api_audit/all_api_replay_templates.http
```

未验证接口必须进入：

```markdown
## 未验证 API 手工测试清单

| ID | 方法 | URL | 参数占位 | 缺失信息 | 建议认证态 | 建议测试方式 |
|----|------|-----|----------|----------|------------|--------------|
```

```markdown
## API 动态验证结果

| ID | 模式 | 方法 | URL | 测试参数摘要 | HTTP状态 | 业务code/success | msg摘要 | data摘要 | 判定 |
|----|------|------|-----|--------------|----------|------------------|---------|----------|------|
| API-001 | NoAuth | GET | /api/user/list?pageNum=1&pageSize=10 | 去除认证头 | 200 | code=0 | success | total=23, records存在 | VerifiedNoAuth |

## 后端成功响应证据

| ID | 模式 | 成功判定字段 | 响应关键字段 | 影响判断 | 证据文件 |
|----|------|--------------|--------------|----------|----------|
| API-001 | NoAuth | HTTP 200 + code=0 | `total=23`, `records[0].username=...` | 无认证读取用户列表 | `api_audit/dynamic_validation_results.json` |
```

判定要求：

- `2xx + code=0/200/success=true/data非空`：视为后端业务成功，必须上报。
- `2xx + 未登录/无权限业务码`：记录为业务层鉴权，不得只写 HTTP 成功。
- `401/403/302`：记录状态、跳转位置或错误消息。
- `4xx/5xx` 若包含栈、SQL、路径、配置、签名错误细节，也要作为异常响应证据。
- 敏感值可脱敏，但字段名、数量、对象结构、成功判定字段必须保留。

高副作用接口报告块：

```markdown
## 高副作用接口低副作用探测

| ID | 方法 | URL | 动作 | 探测方式 | 响应摘要 | 是否业务成功 | 后续人工确认 |
|----|------|-----|------|----------|----------|--------------|--------------|
| API-020 | POST | /api/admin/user/update | update | id=999999999 + dryRun=true | code=0,msg=success | 是 | 确认是否真实写入 |
```

## 运行时登录流与弱口令测试块

当目标识别为后台/管理端登录系统时，最终报告必须包含本节；若未触发运行时登录流，写 `N/A` 并说明原因。

```markdown
## 运行时登录流与弱口令测试

| 项目 | 结果 |
|------|------|
| 是否识别为后台登录系统 | 是/否/不确定 |
| 登录页 | URL 或 N/A |
| 登录接口 | METHOD + URL 或 N/A |
| 是否存在验证码 | 无/有/不确定 |
| 验证码是否可识别 | 可识别/不可识别/N/A |
| 是否存在 2FA/短信/扫码/频控 | 是/否/不确定 |
| 是否执行弱口令小字典 | 是/否 |
| 尝试次数 | N |
| 是否成功登录 | 是/否 |
| 成功账号 | username 或 N/A；密码脱敏 |
| 登录后 token/cookie/storage | 已发现/未发现；值脱敏 |
| 登录触发异步 JS/source map | 已采集 N 个 |
| 后续审计影响 | 已纳入 API/路由/敏感信息/客户端漏洞审计 或 N/A |

### 弱口令测试结论

- 成功：记录为弱口令风险，并关联登录后可访问后台路由、菜单权限 API、关键业务 API。
- 失败且无验证码：不直接判漏洞；提示建议人工在授权范围内进行密码爆破/口令强度验证。
- 存在不可识别验证码/2FA/频控：说明自动化测试跳过，建议人工辅助验证。
```

弱口令成功的证据链必须包含：

```text
登录页 → 登录请求 → 成功响应/token/cookie/storage → 后台路由/DOM → 关键 API/chunk
```

弱口令失败且无验证码时的建议文本可使用：

```text
该站点表现为后台登录系统，未发现验证码/2FA/明显频控。默认弱口令小字典未成功。建议在授权范围内由人工进行密码爆破/口令强度验证，并结合账号锁定策略和测试窗口控制风险。
```

## 低优先级加固项块

CORS、点击劫持、CSP/XFO、mixed content、通用安全头缺失等低信噪比问题如需保留，统一放在报告末尾，不进入 P0/P1 或高危列表：

```markdown
## 低优先级加固项

| 编号 | 类型 | 证据 | 影响说明 | 建议 | 评级 |
|------|------|------|----------|------|------|
| CONFIG-001 | Clickjacking/XFO | `GET /` 响应头未见 XFO/frame-ancestors（需运行时确认） | 未证明敏感操作可被诱导完成 | 按页面敏感度配置 `frame-ancestors` | 🔵 L |
```
