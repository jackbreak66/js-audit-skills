---
name: js-api-audit
description: 前端 JavaScript 前后端交互 API 安全审计工具。用于从 Vue、React、Angular、Vite、Webpack、Nuxt、Next、ASP.NET 前端源码、source map、构建产物、运行时登录流资产和混淆 bundle 中严格还原所有前后端交互 API，强制输出全量 API 台账、参数来源、调用位置和请求模板；追踪页面调用链、request wrapper、interceptor、baseURL、认证头、登录后 token/cookie/storage、签名逻辑、参数构造与响应使用点；对授权 Host 默认执行动态请求验证，构造测试参数并记录后端响应证据；以红队视角识别未授权访问、弱口令登录后的后台 API 暴露、低权限越权、参数可控后台功能、文件读取下载、隐藏后台接口和前端可见但后端失守的真实风险。
---

# JS API Audit - 前后端交互与未授权接口审计

目标不是“粗略列几个接口”，而是**尽可能完整恢复前端真实调用面**，并给出可复核、可验证、可写进报告的 API 台账。

---

## 核心目标

1. 严格提取所有前后端交互 API，不遗漏 wrapper、二次封装、字符串拼接、模板字面量、OpenAPI 生成客户端、GraphQL、WebSocket、SignalR、ASP.NET 特殊调用。
2. **全量 API 台账是硬性产物**：不论是否动态验证、不论风险高低、不论参数是否完整，每个发现的接口都必须进入 `api_inventory_full.*` 和报告“完整 API 台账”章节；不能只写高危、只写已验证、只写摘要。
3. 对每个接口还原：`方法 + baseURL + 路径 + 参数来源 + 认证上下文 + 调用位置 + 响应关键字段 + 安全测试建议`。
4. 请求参数逻辑必须尽量从代码中恢复，不能只写“参数未知”；确实未知时也要给出字段缺失原因、候选参数来源和手工发包占位建议。
5. 对授权 Host 上的接口，默认必须构造测试参数做动态请求验证；无有效登录态也要执行 `NoAuth` 请求，不能仅因“无登录态”标记 `StaticOnly`。
6. 对**无身份凭证也返回具体业务信息**或业务成功响应的接口，必须单独列入报告并给出响应证据。
7. 对**删除/清空/停用/重置/批量修改类接口**，优先做低副作用动态探测：无认证请求、缺失/非法/不存在 ID、`dryRun/validateOnly` 参数、测试 canary 参数；只有在无授权 Host、用户明确禁止发包、或无法构造低副作用探测时，才标为 `StaticOnly`。

---

## 工作边界与动态验证规则

### 动态验证硬要求

只要提供了授权测试 Host，就不能停留在静态台账：

- 每个接口至少生成并尽量执行一条动态验证请求。
- 没有有效登录态时，仍然执行 `NoAuth`：删除 Cookie、Authorization、X-Token、CSRF、租户头等认证字段，观察后端是否返回登录拦截、权限拒绝、参数错误、业务数据或成功响应。
- 有弱口令/普通用户/人工登录态时，继续执行 `WeakCredentialAuth` 或 `LowPriv`。
- 有可控参数时，构造 `ParamTamper` 请求，观察后端是否真正校验 `id/userId/tenantId/orgId/roleId/fileId/path/url/status/isAdmin`。
- 动态请求的响应必须入报告：HTTP 状态、业务 `code/msg/success/data`、关键字段摘要、是否后端成功、是否泄露业务数据。

### 测试参数构造规则

从代码恢复参数后，按以下优先级构造动态验证请求：

1. 使用前端默认值、表单初始值、分页参数、路由参数、TS 类型、mock 示例中的字段。
2. 查询类接口优先使用低影响参数：`pageNum=1&pageSize=10`、`keyword=test`、`status=`、`id=1`。
3. 详情/文件类接口若缺少 ID，尝试从列表接口响应、路由参数、前端示例、mock 数据中取一个候选 ID；没有 ID 时使用 `1/0/-1/999999999` 并记录为占位探测。
4. 写操作/高副作用接口使用 canary 和低副作用参数：`id=-1/0/999999999`、`name=audit_probe_{timestamp}`、`remark=security_test_noop`、`dryRun=true`、`validateOnly=true`、`preview=true`、`force=false`。
5. 文件上传、导入、执行任务类接口优先发送缺文件、空文件名、非法 ID 或 `dryRun/preview` 请求，观察是否先鉴权、是否返回业务成功、是否暴露路径/任务 ID；不要上传真实敏感文件。

### 高副作用接口动态探测规则

高副作用接口不能简单写 `StaticOnly`，应至少尝试以下低副作用验证之一：

- `NoAuth` 原样请求或缺少必要参数请求，用于判断是否先鉴权。
- 使用不存在 ID / 非法 ID / 空数组 / canary 字段，触发参数校验或权限校验。
- 如果接口支持 `dryRun`、`validateOnly`、`preview`、`checkOnly`、`force=false`，优先使用这些参数。
- 若后端对低副作用探测返回业务成功，例如 `success=true`、`code=0/200`、返回任务 ID、创建/更新后的对象、下载地址、文件路径，必须作为“后端成功响应”写入报告，并标记需要人工确认是否发生真实状态变更。

只有以下情况才允许 `StaticOnly`：

- 没有授权测试 Host 或用户明确要求不发包。
- 请求需要不可自动获得的验证码、MFA、一次性签名、真实文件或人工审批。
- 无法构造低副作用请求，且真实请求很可能修改生产数据。

`StaticOnly` 必须写明具体阻断原因和建议的人工验证步骤，不能使用“无有效登录态”作为唯一理由。

禁止在报告中使用类似“`StaticOnly` 表示因无有效登录态或接口含写操作，未进行动态请求验证，仅做静态提取登记”的笼统注释；这会掩盖应执行的 NoAuth 和低副作用探测。

---

## 输入

优先读取并交叉关联：

- `/js-asset-mapper` 输出的 API 清单、脚本关系、静态扫描 JSON。
- `/js-secret-audit` 输出的 Token、Basic Auth、租户头、签名参数、baseURL、文档路径、附件路径、账号口令线索。
- `/js-route-guard-audit` 输出的后台路由、权限码、菜单、按钮权限、隐藏页面、运行时登录流、弱口令小字典结果及关联 API。
- `source_path` 中源码、`dist/`、`.map`、`.env*`、`config*.js/json`、内嵌配置、生成客户端代码。
- `output_path/deobfuscated/` 中的还原 JS。
- `output_path/runtime_assets/` 中登录页、登录提交、登录成功首屏和高价值后台路由触发的 JS/chunk/source map/HAR/资源清单。

---

## 必须识别的 API 来源

| 类型 | 必须覆盖的模式 |
|------|----------------|
| fetch | `fetch(url, { method, headers, body })` |
| axios | `axios.get/post/request`、`axios.create` 实例、`service({ url, method })` |
| request wrapper | `request({...})`、`http.*`、`api.*`、`defHttp.*`、`useRequest`、自定义 SDK |
| jQuery | `$.ajax/get/post` |
| OpenAPI/生成客户端 | Swagger/OpenAPI/NSwag/Orval/RTK Query/自动生成 API 客户端 |
| GraphQL | `/graphql`、`gql`、`operationName`、`variables`、persisted query |
| WebSocket/SSE | `WebSocket`、`EventSource`、Socket.IO |
| SignalR | `HubConnectionBuilder`、`/hub`、`.invoke()`、`.send()` |
| ASP.NET | `PageMethods.*`、`WebMethod`、`.asmx`、`.svc`、`.ashx`、`Sys.Net.WebServiceProxy.invoke` |
| 文件与报表 | `download/export/import/upload/report/preview/file/doc/attachment` |
| SSR/预加载 | `window.__INITIAL_STATE__`、`window.__NUXT__`、`__NEXT_DATA__`、hydration data |
| 运行时配置 | `window.__CONFIG__`、`APP_CONFIG`、`process.env`、`import.meta.env` |

---

## 严格提取规则

### 1. 不能只看字面量 URL

必须同时提取以下构造方式：

- 直接字符串：`'/api/user/list'`
- 模板字面量：`` `/api/user/${id}` ``
- 字符串拼接：`base + '/user/' + id`
- 变量转发：`const url = API.user.detail`
- 常量表：`API_MAP`、`serviceMap`、`ENDPOINTS`
- 二次封装：`getUserList(params)` → `request(...)`
- 工具函数：`buildUrl('/user', query)`、`join(baseURL, path)`
- 代码生成客户端：`client.userControllerListUsers()`
- 动态模块导入和路由懒加载中的 API 方法
- source map 还原出的原始源码中的接口

### 1.1 全量台账优先级

API 提取阶段先追求“全量覆盖”，再做风险分级和动态验证；不要因为接口看起来低危、参数不完整、未验证、重复调用或属于写操作就从台账中删除。

全量台账规则：

- 同一 `method + final_baseURL + path` 可合并为一个 API ID，但必须保留所有调用位置、页面/组件、按钮/事件和参数变体。
- 同一路径不同 method 必须拆分，例如 `GET /user` 与 `POST /user` 分别编号。
- 同一路径但不同 baseURL、不同认证上下文、不同参数结构，应记录为不同变体或在同一 ID 下列出 `variants`。
- 动态拼接无法完全还原时，保留模板路径，例如 `/api/user/${id}`、`/api/${module}/list`，并注明变量来源。
- GraphQL、WebSocket、SignalR、PageMethods 也要进入台账，不要只放在备注中。
- 未验证接口状态可以是 `Extracted/ProbeReady/Pending/StaticOnly`，但接口本身必须列出。
- 报告中不得只列 P0/P1 或动态验证成功接口；低危、待验证、参数未知接口也必须进入“完整 API 台账”。

### 2. 必须串起完整调用链

每个接口必须尽量追踪：

```text
页面/组件/按钮/事件
→ api 方法
→ request wrapper
→ request interceptor
→ auth/token/sign 注入
→ baseURL/env/runtime config
→ 最终 HTTP client
→ 响应数据使用点
```

### 3. baseURL 必须明确

每个接口都要输出 `final_baseURL`，不能只给相对路径。

baseURL 的解析顺序：

1. 运行时配置：`window.__CONFIG__`、`window.appConfig`、内联 script。
2. 构建时环境：`.env.production`、`.env.*`、`import.meta.env`、`process.env`。
3. axios/request 实例默认值：`axios.create({ baseURL })`。
4. wrapper 中的覆盖值：`service({ baseURL, url })`。
5. 当前页面 origin + 相对路径。
6. 若存在多个环境，必须分别列出：`prod / test / gray / admin / intranet`。

若发现多个 baseURL，必须：

- 标明每个 baseURL 的来源文件和变量名。
- 标记哪个更可能是生产值。
- 输出接口与 baseURL 的绑定关系。

### 4. 方法(method)不能缺失

若代码未显式指定 method：

- `fetch` 默认 `GET`
- axios `axios(url)` 默认 `GET`
- wrapper 默认 method 需从封装函数定义推断
- GraphQL 默认通常为 `POST`
- SignalR / WebSocket 记为 `WS` / `SignalR`

不允许把 method 留空。

---

## 参数恢复规则

### 原则

请求参数必须尽量从代码中恢复，而不是简单写“参数未知”。

### 参数来源必须系统追踪

对每个接口，至少检查以下来源：

- 函数签名：`getList(params)`、`detail(id)`、`save(data)`
- 默认值：`params = { pageNum:1, pageSize:10 }`
- 表单模型：`form`, `ruleForm`, `searchForm`, `queryParams`, `model`, `filters`
- Vue/React 状态：`data()`, `state`, `useState`, `reactive`, `ref`, `computed`
- 路由参数：`route.params`, `route.query`, `useParams`, `useSearchParams`
- 本地存储：`localStorage/sessionStorage/cookie`
- TS 类型：`interface`, `type`, `enum`, DTO 名称
- 校验规则：`yup/zod/joi/async-validator`，可推断字段名、必填项、类型
- `FormData.append()`
- `qs.stringify()` / URLSearchParams
- spread 合并：`{ ...query, tenantId, deptId }`
- 条件拼接：`if (id) params.id = id`
- 请求拦截器追加：`tenantId`, `orgId`, `Authorization`, `csrf`, `nonce`, `timestamp`, `sign`
- source map、mock、注释、示例请求
- GraphQL variables 和 operation 定义

### 参数输出要求

每个接口至少输出：

- `path_params`
- `query_params`
- `body_json`
- `form_data`
- `headers`
- `cookies`
- `injected_params`
- `param_source`（字段来自哪里）

### 参数占位规则

仍然无法恢复时，才允许使用占位值；且必须注明：

- 哪些字段来自代码推断
- 哪些字段是安全占位
- 哪些字段缺失会影响验证

示例：

```json
{
  "userId": "1001",
  "tenantId": "1",
  "pageNum": 1,
  "pageSize": 10,
  "keyword": "test"
}
```

并说明：`userId/tenantId` 来自代码默认字段，`keyword` 为安全占位值。

---

## 认证与签名逻辑恢复

必须识别并记录：

- `Authorization` / `Bearer`
- `X-Token` / `token`
- Cookie 会话
- CSRF/anti-forgery token
- `tenantId` / `orgId` / `deptId`
- `sign` / `signature` / `nonce` / `timestamp`
- Basic Auth
- HMAC / md5 / sha1 / sha256 之类前端签名逻辑
- 地图、短信、第三方 SDK 的 appid/appkey/appsecret
- 自定义 header：`AUTHU_USERID`、`X-User-Id`、`X-Tenant` 等

需要说明这些值的来源：

- 常量写死
- localStorage/sessionStorage
- Cookie
- 用户登录响应
- 环境配置
- 从其他接口返回再注入

### 登录态运行时输入

如果 `runtime_assets/login_flow.md` 或 `/js-route-guard-audit` 表明弱口令/人工辅助登录成功，必须把登录后认证上下文纳入 API 验证输入，并明确区分验证模式：

| 模式 | 用途 |
|------|------|
| NoAuth | 删除 Cookie、Authorization、X-Token、CSRF、租户头等认证字段 |
| WeakCredentialAuth | 使用弱口令成功后获得的 token/cookie/storage/header，验证后台 API 可访问范围 |
| LowPriv | 使用用户提供的普通用户凭证或 token 验证越权 |
| ParamTamper | 在上述认证上下文下篡改 `id/userId/tenantId/orgId/roleId/fileId/path/url/status/isAdmin` |
| ManualAuthRequired | 因验证码、MFA、频控或无有效账号导致无法自动获得登录态 |

要求：

- 记录 token/cookie/header/storage 的键名、来源接口和注入位置；值默认脱敏。
- 将登录后首屏的 `menu/userInfo/permission/router/config` API 优先放入高价值读取接口。
- 将登录后新增 chunk/source map 重新纳入 API 提取范围。
- 弱口令成功不等于 API 越权；需要继续验证后台 API 是否可读、是否越权、是否仅是正常登录后访问。
- 弱口令失败且无验证码时，输出“建议人工授权爆破/口令强度验证”，但不要伪造有效登录态。

---

## 响应分析规则

### 必须提取响应使用点

不仅要找请求，还要找前端如何消费响应：

- `res.data`
- `res.rows`
- `res.list`
- `res.result`
- `res.records`
- `res.total`
- `res.code === 200/0`
- `success === true`
- 详情页字段绑定、表格列、下载链接、文档路径、图片路径

### 对无认证返回信息的接口必须单独上报

若去掉身份凭证后仍返回以下任一内容，必须写进报告：

- 具体业务数据
- 用户信息 / 租户信息 / 部门信息 / 配置信息
- 文件路径 / 文档路径 / 下载地址 / OSS URL / 预签名 URL
- 列表记录数、详情字段、枚举数据、组织架构、菜单权限、日志内容
- 明显成功的 code/message/data 结构

即使未确认可进一步利用，也必须列入：

- `NoAuth 有效响应接口清单`
- 响应摘要
- 证据字段
- 风险评级建议

### 状态码不能孤立判断

必须结合前端响应拦截器判断：

- `200` 但业务 `code != 0/200`
- `302` 跳登录但实际响应中有数据
- `401/403` 被 wrapper 吞掉后返回默认对象
- `500` 但错误回显敏感信息

---

## 动态请求验证矩阵

对每个候选接口，至少生成并尽量执行以下验证请求；执行后必须记录后端响应摘要：

| 测试 | 目的 |
|------|------|
| NoAuth | 去掉 Cookie / Authorization / CSRF，验证是否无需认证；无登录态时也必须执行 |
| WeakCredentialAuth | 使用弱口令登录后的认证上下文，枚举后台首屏和高价值安全读取 API 的真实可达范围 |
| LowPriv | 使用普通用户认证，验证是否可访问后台或高敏功能 |
| ParamTamper | 修改 `id/userId/tenantId/orgId/roleId/fileId/path/url/status/isAdmin` 等参数 |
| SafeMutationProbe | 对写操作使用不存在 ID、canary、dryRun/validateOnly/preview 等低副作用参数，观察鉴权、参数校验和业务成功响应 |

响应判定必须结合 HTTP 与业务字段：

- `2xx + code=0/200/success=true/data非空`：后端业务成功，必须上报。
- `2xx + code=401/403/未登录/无权限`：后端有业务层鉴权，记录为 AuthRequired/Forbidden。
- `4xx/5xx + 敏感错误回显/SQL/路径/栈信息`：记录异常响应证据。
- `401/403/302`：记录拦截位置和跳转目标，不要只写“失败”。

### 重要补充

还应考虑：

- 分页参数扩大：`pageSize=1000`
- 批量导出：`ids`, `fileIds`, `userIds`
- 文件路径与 URL 控制：`path`, `url`, `filePath`, `downloadUrl`
- 回调与跳转参数：`callback`, `redirect`, `returnUrl`
- GraphQL introspection / 任意 query / mutation 名称暴露
- 菜单权限码与隐藏按钮关联的后台接口
- 多租户 header 缺失或可篡改
- 仅前端做按钮级控制、后端未校验权限

---

## 红队视角的重点补充

### 1. 不要遗漏“列表接口”和“详情接口”

真实渗透里最容易出成果的是：

- `/list`、`/page`、`/detail`、`/info`、`/get*`
- 字典、枚举、树形组织、配置读取
- 日志、任务、菜单、角色、部门、用户、租户
- 导出前的预览接口、文件详情接口、附件元数据接口

这些接口通常**不是高危动作词**，但非常容易出现 NoAuth 或低权可读。

### 2. 文件与文档接口要特殊处理

若返回值中出现以下字段，必须重点关注：

- `url`, `path`, `filePath`, `fileUrl`, `docPath`, `ossKey`, `objectKey`, `downloadUrl`, `previewUrl`

处理要求：

- 尝试结合 `baseURL`、站点 origin、静态资源根路径拼接完整 URL。
- 若能形成可访问文档链接，必须写入报告。
- 若无需认证即可访问文件，单独列为“文件未授权访问”。
- 若文件路径来自接口返回，再追溯是哪个接口提供的。

### 3. 隐藏后台接口

从以下位置恢复隐藏 API：

- 路由 `meta.permissions`
- 菜单树、按钮权限码、操作列事件
- `v-if` / `hasPermi` / `checkRole` / `auth()`
- 导入/导出按钮绑定事件
- 仅管理员可见页面的 API 模块

### 4. 灰度/内网/后台 baseURL

红队很有价值的一类结果：

- `adminBaseUrl`
- `manageBaseUrl`
- `intranetApi`
- `testApi`, `grayApi`, `devApi`

即使当前页面未直接调用，也要进入报告“潜在高价值后台接口”。

### 5. 观察下载型未授权

即使接口不是 CRUD 风险，也可能造成数据外泄：

- 导出 Excel / CSV / PDF
- 下载合同、报告、图片、证件、附件
- 预览 Office / PDF / 图片
- OSS/CDN 回源文件

这些一旦 NoAuth 成功，必须单独标注为高优先级。

### 6. 注意方法覆盖绕过

若发现：

- `_method`
- `X-HTTP-Method-Override`
- `method=DELETE`

要记录为“潜在方法覆盖风险”，但默认不主动利用。

---

## API 优先级分层

### P0 - 高价值可读接口（优先安全验证）

- `list/page/detail/info/get/query/search/tree`
- `config/system/menu/user/role/dept/org/tenant/log/task/report`
- `download/export/preview/file/doc/attachment`
- `graphql` introspection 或公开 query
- 返回用户、租户、配置、组织、日志、文件信息的接口

### P1 - 需要低权验证的接口

- 角色、菜单、部门、租户、审批、报表、任务、系统配置读取
- 普通用户本不应访问的后台接口

### P2 - 高副作用接口（优先低副作用动态探测）

- 删除、清空、重置、导入、上传、修改、授权、执行任务、批量操作
- 不能直接忽略；至少做 NoAuth 或非法/不存在 ID/dryRun 探测，除非无授权 Host 或无法避免真实状态变更

---

## 报告输出要求

输出路径：

```text
{output_path}/api_audit/{project_name}_js_api_audit_{timestamp}.md
```

动态验证证据建议同步落盘：

```text
{output_path}/api_audit/
├── api_inventory_full.md
├── api_inventory_full.json
├── api_inventory_full.csv
├── all_api_replay_templates.http
├── dynamic_validation_results.json
├── dynamic_validation_results.md
├── backend_success_responses.md
└── replay_templates.http
```

报告必须包含以下部分：

### 1. 审计概述

- 扫描范围
- 资产来源
- 提取到的 API 总数
- 全量 API 台账文件路径：`api_inventory_full.md/json/csv`
- 已解析 baseURL 数量
- 已动态请求验证接口数量
- NoAuth/WeakCredentialAuth/LowPriv/ParamTamper/SafeMutationProbe 各自执行数量
- 因明确阻断原因保留 StaticOnly 的接口数量

### 2. baseURL 与环境解析

表格至少包含：

| 环境 | baseURL | 来源文件 | 来源变量 | 备注 |
|------|---------|----------|----------|------|

### 3. 请求封装与认证链

说明：

- request wrapper 名称
- interceptor 注入逻辑
- token/cookie/sign/tenant/header 来源
- 登录后 token/cookie/storage/header 是否来自弱口令登录流、人工登录、用户提供凭证或静态泄露；值必须脱敏
- 响应拦截器和错误处理方式

### 4. 完整 API 台账

这是本 skill 的硬性输出。每条接口都要进表，不允许只写高危项、已验证项或摘要；即使未动态验证，也必须保留方法、路径、参数线索、调用位置和手工测试建议。

| ID | 方法 | final_baseURL | 路径/模板路径 | 接口名称/调用函数 | 页面/组件/事件 | path参数 | query参数 | body/form参数 | header/cookie | 认证方式 | 参数来源 | 调用位置 | 响应关键字段 | 风险标签 | 验证状态 |
|----|------|---------------|---------------|-------------------|---------------|----------|-----------|--------------|---------------|----------|----------|----------|--------------|----------|----------|

字段要求：

- `参数来源` 必须写清来自函数签名、表单模型、路由参数、TS 类型、mock、默认值、interceptor 注入或未知原因。
- `调用位置` 尽量包含文件:行号；构建产物至少包含 bundle 文件名、函数名/关键字符串/offset。
- `风险标签` 可多选：`Admin`、`User`、`Role`、`Tenant`、`File`、`Export`、`Import`、`Upload`、`Config`、`Log`、`Task`、`WriteAction`、`NoAuthCandidate`、`LowPrivCandidate`、`Unknown`。
- `验证状态` 是动态验证状态，不影响是否进入台账。
- 如果接口数量很大，`api_audit/{project_name}_js_api_audit_*.md` 仍必须包含全量表；最终总报告也必须附带或嵌入全量台账，不能只给“见高危接口”。

状态取值：

- `Extracted`：已静态提取，尚未验证。
- `ProbeReady`：已构造测试参数和请求模板，等待执行。
- `NoAuthTested`：已执行无认证请求。
- `AuthRequired`：后端明确要求登录或权限。
- `Forbidden`：认证存在但权限不足。
- `VerifiedSuccess`：后端返回业务成功，必须在成功响应证据表中展开。
- `VerifiedNoAuth`：无认证返回业务成功或敏感数据。
- `VerifiedWeakCredential`：弱口令登录态下返回后台业务数据。
- `ParamTamperSuspected`：参数篡改有疑似越权响应。
- `SafeMutationProbeAttempted`：写操作已做低副作用探测。
- `StaticOnly`：仅限无授权 Host、用户禁止发包、验证码/MFA/真实文件/真实状态变更不可避免等明确阻断原因。
- `Pending`：暂未执行；必须说明下一步请求。

### 5. 参数恢复明细

对高优先级接口和参数复杂接口，单独展示；全量参数摘要仍必须在“完整 API 台账”里出现：

- path/query/body/form/header/cookie
- 字段来源
- 默认值/占位值
- 是否可控

### 5.1 未验证接口手工测试清单

对 Claude Code 未能动态验证的接口，必须额外列出给人工发包使用的清单：

| ID | 方法 | URL | 参数占位 | 缺失信息 | 建议认证态 | 建议测试方式 |
|----|------|-----|----------|----------|------------|--------------|

这部分用于避免后续手工测试遗漏；不能因为未验证就省略接口。

### 6. NoAuth 有效响应接口清单

必须单独成节：

| ID | 方法 | URL | 无认证响应特征 | 证据字段 | 影响判断 | 风险 |
|----|------|-----|----------------|----------|----------|------|

### 6.1 动态请求验证结果总表

每个已执行请求都要记录，不能只给模板：

| ID | 模式 | 方法 | URL | 测试参数摘要 | HTTP状态 | 业务code/success | msg摘要 | data摘要 | 判定 |
|----|------|------|-----|--------------|----------|------------------|---------|----------|------|

### 6.2 后端成功响应证据

凡是后端返回业务成功，必须单独展开：

| ID | 模式 | 请求摘要 | 成功判定字段 | 响应关键字段 | 影响 | 证据文件 |
|----|------|----------|--------------|--------------|------|----------|

响应关键字段要具体，例如 `total=23`、`records[0].username=...`、`data.token存在`、`taskId=...`、`fileUrl=...`；敏感值脱敏，但不能只写“有响应”。

### 7. LowPriv / ParamTamper 候选清单

| ID | 类型 | 目标参数 | 预期影响 | 验证建议 |
|----|------|----------|----------|----------|

### 7.1 WeakCredentialAuth 后台 API 可达范围

若弱口令或人工辅助登录成功，必须单独列出：

| ID | 方法 | URL | 触发页面/路由 | 认证上下文来源 | 响应特征 | 后续风险判断 |
|----|------|-----|---------------|----------------|----------|--------------|

重点覆盖登录后自动请求的 `userInfo/menu/permission/router/config`，以及少量高价值后台读取接口。若没有成功登录或因验证码/MFA跳过，写 `N/A` 并说明原因。

### 8. 高副作用接口探测台账

| ID | 方法 | URL | 高副作用动作 | 低副作用探测方式 | HTTP/业务响应 | 是否业务成功 | 后续人工确认 |
|----|------|-----|--------------|------------------|---------------|--------------|--------------|

### 9. Burp/HTTP 请求模板

对所有已提取接口生成模板；对已执行接口同步给出实际请求摘要和响应证据文件：

- NoAuth
- WeakCredentialAuth（如有登录态）
- LowPriv
- ParamTamper
- SafeMutationProbe（写操作/高副作用接口）

模板必须带：

- 完整 `final_baseURL`
- 明确的 path/query/body
- 明确可删去或替换的认证头
- 全量接口都要至少有一个手工发包模板；不能只给高危接口模板。

### 10. 漏洞详情 / 待验证清单

区分：

- 已确认未授权
- 已确认低权越权
- 弱口令登录后的后台 API 可达范围
- 后端业务成功响应但影响待人工确认
- 响应异常但有敏感回显
- 待验证

---

## 输出风格要求

- 不漏接口，先求全，再分级。
- 全量 API 台账优先于漏洞筛选；报告必须能支持人工继续发包测试。
- 所有结论都给出来源文件、函数名或调用链依据。
- 对每条 NoAuth 命中给出“为什么这不是纯静态猜测”。
- 对每条后端业务成功响应给出具体字段证据，不能只写“请求成功”。
- 对无法确认的接口明确写不确定性，不要伪造成功。
- 对高副作用接口优先给出低副作用探测请求；若业务成功，要明确提醒人工确认是否发生真实状态变更。

---

## 最小请求模板示例

### 安全读取类接口

```http
GET {{final_baseURL}}/api/system/config/list?pageNum=1&pageSize=10 HTTP/1.1
Host: {{host}}
User-Agent: Mozilla/5.0
Accept: application/json, text/plain, */*
Authorization: Bearer {{token_or_empty}}
X-Token: {{x_token_or_empty}}
```

### 查询型 POST 接口

```http
POST {{final_baseURL}}/api/user/page HTTP/1.1
Host: {{host}}
Content-Type: application/json
Accept: application/json, text/plain, */*
Authorization: Bearer {{token_or_empty}}

{"pageNum":1,"pageSize":10,"tenantId":"1","keyword":"test"}
```

### 文件/文档访问

```http
GET {{final_baseURL}}/oms/20251022/20251022160523830.docx HTTP/1.1
Host: {{host}}
User-Agent: Mozilla/5.0
Accept: */*
```

---

## 自检

- [ ] 已扫描源码、构建产物、source map、派生还原文件。
- [ ] 已追踪页面 → API → wrapper → interceptor → baseURL → client 的调用链。
- [ ] 每个接口都有 method、final_baseURL、路径、参数摘要、认证上下文、调用位置。
- [ ] 已输出 `api_inventory_full.md/json/csv`，且包含所有已发现接口、参数摘要、调用位置、验证状态和手工测试建议。
- [ ] 最终报告或 API 审计报告没有只列高危/已验证接口；未验证接口也进入完整 API 台账。
- [ ] 授权 Host 存在时，每个接口至少构造并尽量执行一条动态验证请求；无登录态也已执行 NoAuth。
- [ ] 写操作/高副作用接口已尝试 NoAuth、非法/不存在 ID、canary 或 dryRun/validateOnly 等低副作用探测；未执行时有明确阻断原因。
- [ ] 若存在运行时登录流，已把登录后 token/cookie/storage/header 和新增 chunk/source map 纳入 API 提取与验证模式。
- [ ] 参数已从函数签名、表单、状态、路由、TS 类型、FormData、序列化逻辑中尽量恢复。
- [ ] 已单独列出 NoAuth 有效响应接口，并给出具体响应证据字段。
- [ ] 已单独列出所有后端业务成功响应，包含 HTTP 状态、业务 code/msg、关键 data 字段和影响判断。
- [ ] 已将删除/修改/导入/上传/执行类接口放入高副作用探测台账，而不是默认 StaticOnly。
- [ ] 已单独处理 GraphQL、WebSocket、SignalR、ASP.NET 特殊接口。
- [ ] 已对文件/文档/附件 URL 做 baseURL 拼接和未授权访问分析。
- [ ] 报告区分“已确认”“待验证”“静态高价值线索”。
