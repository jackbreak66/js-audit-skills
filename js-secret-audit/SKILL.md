---
name: js-secret-audit
description: 前端 JavaScript / source map / 构建产物敏感信息与高价值线索审计工具。用于识别硬编码账号口令、Token、JWT、AK/SK、OAuth client_secret、Basic Auth、内部接口、文档附件路径、后台 URL、环境配置、字符串表中的弱格式秘密、可拼接访问链接、webpack splitChunks/残留 chunk 中的默认密码、以及可交叉验证的登录参数，并将高可信秘密与中低可信但高价值线索一并输出到报告。
---

# JS Secret Audit - 强化版前端敏感信息泄露审计

你的目标不是只找“标准格式 secret”，而是要尽可能找出**前端可见的认证信息、凭证线索、账号口令、文档访问路径、后台接口、附件 URL、以及可用于后续验证的高价值字符串**。

---

## 一、审计目标

识别以下两大类内容，并全部输出到报告：

### A. 高可信敏感信息

包括但不限于：

- JWT / Bearer Token / refresh_token / sessionId
- 云厂商密钥、第三方 SDK Key、短信/地图/支付/Sentry/Firebase Key
- OAuth `client_secret` / `appSecret` / `tenantSecret`
- Basic Auth、数据库/Redis/FTP/SMTP 连接凭证
- 明文账号密码对
- 可直接访问的附件、文档、导出文件路径
- 私钥、公钥、证书、签名密钥、加密 key

### B. 中低可信但高价值线索

即使不能立即证明是有效 secret，也必须记录并输出：

- `username` / `password` / `newpassword` / `szUserName` / `szPassword` / `user` / `USER` 等字段值
- `token` / `key` / `secret` / `authorization` / `delimiter` / `attribute` 等弱格式值
- 32 位十六进制串、16 位十六进制串、base64 串、疑似 MD5 / SM3 / 摘要值
- 附件路径、文档路径、上传目录、导出路径、历史文件名
- 内部系统代号、租户标识、模块 key、角色 key、用户枚举值
- source map 中暴露的源码路径、注释、调试字段、接口备注
- chunk 字符串表中的敏感命名和值

**原则：宁可降级输出，不要静默丢弃。**

---

## 二、输入范围

必须优先读取并检查：

- `/js-asset-mapper` 输出的 `scripts/js_static_scan.json`
- `source_path` 下的源码、`dist/`、`static/`、`assets/`、`build/`
- 所有 `.js`、`.mjs`、`.cjs`、`.map`、`.json`、`.env*`、`config*.js`、`config*.json`
- `output_path/deobfuscated/` 下的还原文件
- `output_path/asset_mapper/webpack_chunk_inventory.json` 中枚举到的所有 JS/map 资产
- `output_path/runtime_assets/downloaded_chunks/` 与 `output_path/runtime_assets/downloaded_maps/`，包括当前浏览器未加载但服务器可访问的独立 chunk/旧 chunk
- 所有 source map 的 `sourcesContent`
- 所有 chunk 中的字符串表、配置对象、初始化对象
- `window.__INITIAL_STATE__`、`window.__CONFIG__`、`window.__NUXT__`、`__NEXT_DATA__`
- `process.env`、`import.meta.env`、本地化字典、表单 schema、默认值对象

---

## 三、检索策略

### 1. 不要只依赖单条 regex

你必须同时执行以下四类检索：

#### 1）变量名驱动检索

搜索高风险字段名及其附近上下文：

- `password`, `passwd`, `pwd`, `newpassword`, `oldpassword`
- `username`, `userName`, `user`, `loginName`, `account`, `admin`, `szUserName`, `szPassword`
- `token`, `accessToken`, `refreshToken`, `authorization`, `auth`, `secret`, `client_secret`, `appSecret`
- `ak`, `sk`, `appKey`, `apiKey`, `signKey`, `encryptKey`, `tenantSecret`
- `cookie`, `session`, `sessionId`, `Authorization`, `Bearer`
- `doc`, `file`, `path`, `url`, `upload`, `download`, `export`, `attach`, `attachment`

#### 2）格式驱动检索

搜索典型值格式：

- JWT
- Basic Auth
- 云厂商 Key
- `-----BEGIN ... PRIVATE KEY-----`
- 16/24/32/40/64 位十六进制串
- 长 base64 串
- 明文 URL 路径、附件路径、`.doc` / `.docx` / `.xls` / `.xlsx` / `.pdf` / `.zip`
- `http://`、`https://`、`/oms/`、`/upload/`、`/download/`、`/export/`

#### 3）结构驱动检索

重点识别以下结构，而不是只看单个字段：

- 同一对象内同时出现 `username` 与 `password`
- 同一文件内相邻位置出现账号字段和值、口令字段和值
- `login`, `auth`, `oauth`, `sso`, `sign`, `decrypt`, `encrypt` 附近出现 secret 字段
- `headers`, `Authorization`, `Bearer`, `token` 被用于请求头
- `axios/fetch/request` 配置对象中出现认证参数
- `Form` / `schema` / `defaultValue` 中出现默认账号密码
- chunk 字符串表中出现一组账号密码、token、路径、baseURL 的组合

#### 4）路径与 URL 驱动检索

遇到文档路径、附件路径、导出路径时：

- 记录原始路径
- 尝试结合 `baseURL`、站点根路径、接口前缀拼接为可访问 URL
- 若存在多个候选根路径，全部列出
- 将可拼接出的文档访问链接单独列入报告

例如发现：

- `/oms/20251022/20251022160523830.docx`

则需要结合：

- `https://example.com/oms/20251022/20251022160523830.docx`
- `https://example.com/app/oms/20251022/20251022160523830.docx`
- 以及实际代码中出现的下载前缀进行组合

---

## 四、最低执行要求

### 1. 必须抓取“弱格式秘密”

以下内容即使不符合标准密钥格式，也必须命中并出报告：

- `username:"admin"`
- `password:"123456"`
- `szUserName:"admin"`
- `szPassword:"yw123456"`
- `token:"delimiter"`
- `token:"attribute"`
- `user:"measure1Monitor"`
- `USER:"web_user"`

### 2. 必须识别“账号口令对”

当同一对象、相邻代码块、同一函数入参、同一请求体中出现账号字段和口令字段时，按 **SECRET-ACCOUNT-PAIR** 单独输出，不得只记录 password 不记录 username。

### 3. 必须识别“默认口令 / 重置口令”

像 `newpassword`, `initPassword`, `defaultPassword`, `resetPassword` 这类字段，哪怕值很短，也要单独记为 **SECRET-DEFAULT-PASSWORD**。

### 4. 必须保留“疑似摘要值”

下列值不要因为看起来像 hash 就直接丢弃：

- `00000000000000000000000000000000`
- `795881f43b1d7f48af2c825dc4852763`
- `e0c9ea79f9bace118c8200aa004ba90b`
- `e0859ff2f94f6810ab9108002b27b3d9`

它们至少应归类为：

- `SECRET-HASH-CANDIDATE`
- 并标注“疑似 MD5/摘要/固定口令哈希，需结合登录逻辑进一步验证”

### 5. 必须区分“普通 key”与“高价值 key”

像 `key:"Helvetica"`、`key:"dependencies"` 属于普通字符串，允许低优先级或忽略。

但以下情况必须保留：

- key 名本身带认证/权限/证书/租户/加密语义
- key 值是手机号、账号、模块主键、角色 key、业务唯一标识
- key 周边出现登录、证书、属性、权限、文档路径、下载接口

例如：

- `key:"18124891025"`
- `key:"certificate"`
- `key:"attributes"`
- `key:"pj-role-title-"`

这些都应进入“高价值线索”表，而不是直接过滤。

---

## 五、判定逻辑

对每个命中都做以下判断：

1. **字段语义**：变量名是否具备认证、授权、账号、密码、密钥、路径语义
2. **值形态**：是否像明文、摘要、token、路径、URL、base64、hex
3. **组合关系**：是否和账号/密码/token/baseURL/headers/下载路径一起出现
4. **运行时可达性**：是否存在于生产 bundle、source map、可公开下载文件
5. **调用证据**：是否被用于登录请求、请求头、SDK 初始化、签名、文档下载
6. **利用价值**：是否可直接用于登录、访问附件、调用后台接口、枚举资产

### 分级规则

#### Critical

- 有效生产凭证、生产云密钥、可直接访问后台的 token/Basic Auth
- 明确的管理员账号密码对
- 可直接拼接访问的敏感文档 URL 且文件名明显为业务文档

#### High

- 默认账号密码、测试账号但权限较高
- 可复用 token / 签名 key / OAuth secret
- source map 暴露后台路径与敏感配置
- 可访问附件路径、导出路径、文档 URL 线索清晰

#### Medium

- 弱格式 token、疑似摘要值、可疑账号、内部租户/角色 key、用户枚举值
- 文档路径、上传目录、下载接口，但未完成可达性验证

#### Low

- 孤立的敏感命名字段、无证据的普通 key、无法确认用途的字符串

**禁止因“无法确认有效性”而不输出 Medium/Low。**

---

## 六、重点漏检补救规则

### 规则 1：账号口令成对输出

看到以下任意组合，必须合并为同一条风险：

- `username + password`
- `user + password`
- `szUserName + szPassword`
- `account + pwd`
- `admin + 123456`

### 规则 2：token 弱值也要输出

像：

- `token:"delimiter"`
- `token:"attribute"`

虽然不像生产 token，但至少是认证逻辑、字段名、解析规则或保留字段线索，必须进入报告的“中低可信高价值线索”部分。

### 规则 3：文档路径转访问链接

发现：

- `/oms/20251022/20251022160523830.docx`

必须：

- 提取文件名
- 提取目录
- 结合站点域名、baseURL、下载前缀构造完整 URL
- 输出“原始路径”和“候选访问链接”两列

### 规则 4：字符串表不降噪过度

对 bundle/chunk 中的字符串表：

- 不要只因它们出现在压缩产物中就忽略
- 若命中账号、密码、token、路径、下载、certificate、attributes、role、user 等高价值词，必须保留

### 规则 5：摘要值单独成表

疑似 MD5/hex/base64 的值不要与普通字符串混在一起，单列为：

- `疑似摘要/固定口令哈希/签名参数候选`

### 规则 6：Webpack 未加载 chunk 不得忽略

对 Webpack/Vue CLI/Nuxt splitChunks 站点，必须按 `../js-shared/WEBPACK_CHUNK_COVERAGE.md` 检查所有可访问 chunk：

- 浏览器 Network 中出现的合并 chunk 要扫描。
- `webpack_chunk_inventory.json` 枚举出的独立 chunk、旧 chunk、source map 也要扫描。
- 当前路由未加载但可通过 URL 直接访问的 JS，也属于前端可见构建产物。
- 如果硬编码密码只存在于未加载独立 chunk 中，仍按敏感信息泄露输出；不要因为“当前浏览器不加载”降噪掉。

命中硬编码密码时，额外记录：

| 字段 | 说明 |
|------|------|
| chunk 来源 | runtime_loaded / runtime_referenced / server_present_unloaded / sourcemap_referenced / orphan/stale |
| 当前浏览器是否加载 | 是/否/不确定 |
| 是否可直接访问 | 是/否/未验证 |
| 关联 runtime/合并 chunk | 如 splitChunks 合并文件名 |
| 泄露 chunk URL | 可直接访问的 JS/map URL |

---

## 七、输出格式（强制）

报告必须同时输出以下四个表，不能只输出高危项：

### 1. 高可信敏感信息表

| ID | 类型 | 字段 | 位置 | 脱敏值 | 证据 | 风险 |
|----|------|------|------|--------|------|------|

### 2. 账号口令与默认凭证表

| ID | 账号字段 | 账号值 | 口令字段 | 口令值(脱敏) | 文件位置 | chunk来源 | 当前是否加载 | 是否可直接访问 | 上下文 | 风险 |
|----|----------|--------|----------|--------------|----------|----------|--------------|----------------|--------|------|

### 3. 中低可信高价值线索表

| ID | 类型 | 命中值 | 字段/语义 | 位置 | 为什么值得关注 | 建议后续动作 |
|----|------|--------|-----------|------|----------------|--------------|

这里必须覆盖：

- 弱格式 token
- 用户名枚举
- hash 候选
- role/key/tenant/certificate/attributes 等关键业务字段
- 文档路径、下载路径、上传路径

### 4. 文档与附件访问线索表

| ID | 原始路径 | 候选完整 URL | 来源文件 | 是否可拼接 | 风险 |
|----|----------|---------------|----------|------------|------|

---

## 八、漏洞详情撰写要求

对每条高危或中危信息，输出一段可直接进报告的漏洞描述，至少包含：

- 泄露位置
- 泄露内容类型
- 利用方式
- 潜在影响
- 验证建议
- 修复建议

### 账号密码类描述要求

必须明确写：

- 前端代码中存在硬编码测试/默认账号凭证
- 攻击者可据此尝试登录后台、接口或相关系统
- 若凭证在其他系统复用，风险进一步扩大

### 文档路径类描述要求

必须明确写：

- 前端暴露内部文档/附件路径
- 攻击者可据此构造访问链接并尝试越权下载
- 即使当前未验证可下载，也属于高价值信息暴露

### hash 候选类描述要求

必须明确写：

- 前端存在疑似固定口令哈希/签名摘要值
- 若与认证、初始化密码或签名逻辑相关，可能被用于撞库、重放或逻辑分析

---

## 九、与其他审计联动

发现以下内容时，必须传递给后续 agent：

### 传递给 `/js-api-audit`

- 可复用 token / Authorization 头
- 登录接口参数名
- 账号密码对
- baseURL / internal API / download API
- 文档 URL 候选

### 传递给 `/js-route-guard-audit`

- 后台路由、管理端入口、内部页面路径
- role / permission / tenant / module key

### 传递给 `/js-source-map-audit`

- source map 中的源码路径、注释、调试配置、历史环境变量

---

## 十、降噪规则

可以降噪，但不能误删高价值线索。

### 可降噪

- `example`, `sample`, `dummy`, `mock`, `placeholder`, `your_key_here`
- 与样式、字体、布局、渲染器明显相关的普通字符串

### 不能因以下原因而丢弃

- 值太短
- 不是标准 token 格式
- 看起来像普通用户名
- 出现在压缩 bundle 里
- 只是路径不是完整 URL
- 看起来像 hash 但暂未确认算法

---

## 十一、执行提示词

执行时请遵守以下要求：

1. 先全量提取所有疑似敏感值，再做分级，禁止先验过滤过重。
2. 对账号、密码、token、key、path、url 做“字段名 + 值 + 上下文”联合分析。
3. 对弱格式 token、账号、默认密码、文档路径、hash 候选必须保留到报告。
4. 对路径类命中必须尝试拼接成完整访问链接。
5. 对每条命中输出“为什么值得关注”，不要只给一个字符串列表。
6. 不要只输出高危项；中低危但高价值线索必须独立成表。
7. 若发现多个账号、多个密码、多个 user 枚举值，要按可读形式整理，不要散落在原始日志中。
8. 报告中敏感值可脱敏展示，但需要保留足够证据证明命中真实存在。
9. 对 Webpack 构建产物，不要只扫描 Network 已加载 chunk；必须纳入 `webpack_chunk_inventory`、可下载独立 chunk、旧 chunk 和 sourcemap。

---

## 十二、最小自检清单

- [ ] 已扫描源码、bundle、source map、还原文件、配置文件。
- [ ] Webpack/splitChunks 站点已扫描当前加载 chunk、runtime 引用 chunk、服务器可访问但当前未加载 chunk、source map。
- [ ] 已检查字符串表、默认值对象、请求头、登录参数、下载路径。
- [ ] 已识别并合并账号口令对。
- [ ] 已输出弱格式 token 与 hash 候选。
- [ ] 已输出文档/附件路径及候选访问 URL。
- [ ] 已输出高危表、中低可信线索表、文档访问线索表。
- [ ] 没有因为“不能确认有效性”而静默丢弃高价值线索。
