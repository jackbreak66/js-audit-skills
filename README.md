# js-audit-skills

> 面向红队的 AI Agent 驱动前端 JavaScript 全链路安全审计 Skills

本项目是一套专为 AI Coding Agent（Claude Code / Kimi Code CLI 等）设计的**可组合安全审计 Skills**，用于对 Vue、React、Angular、Vite、Webpack、Nuxt、Next、ASP.NET 等前端项目执行**源码优先的白盒/灰盒安全审计**。

核心定位：**让 AI Agent 像前端红队一样工作**——从静态资产还原到动态接口验证，从硬编码敏感信息挖掘到登录态突破，形成完整的审计闭环。

---

## 🔥 核心能力矩阵

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        JS 全链路安全审计流水线                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  资产还原 → 敏感信息 → 路由守卫 → API 审计 → 客户端漏洞 → 交叉验证 → 报告输出   │
├─────────────────────────────────────────────────────────────────────────────┤
│  运行时登录流 + mmx 验证码识别 + 弱口令探测                                    │
│  Webpack splitChunks / 残留 chunk 全覆盖                                      │
│  SafeMutationProbe 低副作用动态验证                                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ 审计流水线架构（5 阶段）

```
阶段1: 资产还原与索引 (js-asset-mapper)
  └─ 框架识别 / 入口提取 / source map / Webpack chunk 枚举
  └─ 路由表 / API 端点 / 参数来源 / 认证头 / Burp 模板

阶段1.5: 运行时登录流与异步资产采集
  └─ 后台登录页识别 → 表单字段提取 → 验证码状态判定
  └─ mmx 多模态验证码识别 → 自动填入 → 弱口令小字典探测
  └─ 登录成功判定 → token/cookie/storage 变化采集
  └─ 登录触发的异步 JS/chunk/source map 回流静态审计
  └─ 访问不同后台路由触发的**懒加载 chunk**下载并回流静态分析

阶段2: 专项静态审计并行
  ├─ js-secret-audit: 硬编码密钥 / Token / 账号口令 / 文档路径 / 环境配置
  ├─ js-route-guard-audit: 登录逻辑 / 路由守卫绕过 / 菜单权限 / 客户端鉴权缺陷
  ├─ js-api-audit: 全量 API 台账 / 参数恢复 / 未授权验证 / 越权探测
  └─ js-client-vuln-audit: DOM XSS / postMessage / 开放跳转 / 原型污染 / 供应链

阶段3: 交叉分析
  ├─ 敏感 Token → 注入 API 验证条件
  ├─ 路由绕过 → 关联后台 API 鉴权状态
  ├─ source map 还原 → 补充 API 与敏感信息清单
  └─ P0/P1 高价值接口 → 生成验证队列

阶段4: 可复现验证（低副作用优先）
  ├─ NoAuth: 无登录态去认证请求（强制执行，不跳过）
  ├─ PostEmptyJsonProbe: POST JSON 接口空体 `{}` 探测
  ├─ LowPriv: 普通用户态请求后台接口
  ├─ ParamTamper: id / userId / tenantId / orgId / role 篡改
  └─ SafeMutationProbe: 写操作使用不存在 ID / canary / dryRun / validateOnly

阶段5: 汇总报告与质量校验
  └─ final_report.md + api_inventory_full.md/json/csv + 全量 HTTP 请求模板
```

---

## 🎯 关键技术特性

### 1. 硬编码敏感信息深度提取
- **变量名驱动 + 格式驱动 + 结构驱动 + 路径驱动** 四维检索策略
- 覆盖 JWT、Bearer Token、云厂商 AK/SK、OAuth secret、Basic Auth、明文账号口令对
- **中低可信高价值线索不丢弃**：弱格式 token、疑似 MD5/哈希值、文档附件路径、内部租户 key 等全部入报告
- **Webpack 残留 chunk 全覆盖**：当前浏览器未加载但服务器可访问的独立 chunk/旧 chunk 一并扫描

### 2. 全量 API 接口台账与动态验证
- **硬性产出全量 API 台账**：所有发现的前后端交互 API（fetch/axios/GraphQL/WebSocket/SignalR/ASP.NET PageMethods）必须进入 `api_inventory_full.md/json/csv`
- **零遗漏原则**：低危、未验证、参数不完整、重复调用变体均不得删除
- **调用链追踪**：页面/组件 → API 方法 → request wrapper → interceptor → auth/token/sign → baseURL → 最终 client
- **后端成功响应证据**：对返回 `success=true` / `code=0/200` / 数据列表 / 任务 ID / 文件 URL 的接口，必须在报告中具体展开字段证据

### 3. 危险接口低副作用探测（SafeMutationProbe）
- **不跳过、不忽略高副作用接口**：删除/清空/停用/重置/批量修改/导入/上传/执行类接口必须验证
- **低副作用探测优先**：
  - 使用不存在 ID / 非法 ID / 空数组 / canary 字段
  - 优先使用 `dryRun=true` / `validateOnly=true` / `preview=true` / `force=false`
  - 触发参数校验或权限校验即可判定鉴权状态
- **只有明确阻断原因才允许 `StaticOnly`**：无授权 Host / 用户禁止发包 / 验证码 MFA / 真实状态变更不可避免

### 4. 短小弱口令探测机制
- **高命中小字典**：`admin/123456`、`admin/admin`、`root/root` 等 18 组固定组合
- **成功即停止**：命中后立即终止，不扩大字典、不持续爆破
- **源码线索优先**：若 JS/注释/配置中发现默认账号密码线索，优先尝试线索组合
- **多维度成功判定**：结合业务 code/msg/token、cookie/storage 变化、页面跳转、后台 DOM、菜单 API 响应

### 5. mmx 多模态验证码识别 + 弱口令联动
- 登录页遇到**图片验证码**（文本/算术）时，自动调用本地 `mmx vision describe` 进行 OCR 识别
- 支持**算术验证码自动计算**：如 `5 x 5 = ?` → 提取答案 `25`
- 识别结果自动填入验证码字段，继续执行弱口令探测
- **验证码场景请求量控制**：弱口令尝试限制为最多前 5 个高优先级组合
- **失败智能回退**：`mmx` 不可用 / 调用失败 / 连续 2 次解析失败 → 自动跳过弱口令提交，记录原因

### 6. Webpack splitChunks / 残留 Chunk / 懒加载 Chunk 全覆盖
- 浏览器 Network 仅代表当前路径加载集合，**不代表服务器全部可访问 JS**
- **运行时通过 Chrome MCP 访问不同路由，捕获 Vue/React 路由懒加载触发的 chunk.js，下载并回流静态审计**
- 枚举 runtime 引用 chunk、source map 暴露 chunk、服务器可访问但未加载的独立 chunk/旧 chunk
- 所有可访问 JS/map 资产（含懒加载 chunk）进入敏感信息扫描和 API 提取范围

---

## 📦 项目结构

```
js-audit-skills/
├── js-audit-pipeline/         # 总控流水线：编排 5 阶段审计链路
│   └── SKILL.md
├── js-asset-mapper/           # 资产还原：框架/路由/API/参数/认证头映射
│   ├── SKILL.md
│   └── scripts/
│       ├── js_static_scan.py
│       └── webpack_chunk_inventory.py
├── js-secret-audit/           # 敏感信息泄露：硬编码密钥/账号/Token/文档路径
│   └── SKILL.md
├── js-route-guard-audit/      # 路由守卫绕过：登录逻辑/权限绕过/弱口令探测
│   └── SKILL.md
├── js-api-audit/              # API 未授权审计：全量台账/动态验证/越权探测
│   └── SKILL.md
├── js-client-vuln-audit/      # 客户端攻击面：DOM XSS/postMessage/原型污染/供应链
│   └── SKILL.md
└── js-shared/                 # 共享规范
    ├── DEOBFUSCATION_STRATEGY.md   # 反混淆策略
    ├── OUTPUT_STANDARD.md          # 输出标准
    ├── RUNTIME_LOGIN_FLOW.md       # 运行时登录流 + mmx 验证码识别
    ├── SEVERITY_RATING.md          # 严重度评级
    └── WEBPACK_CHUNK_COVERAGE.md   # Webpack chunk 覆盖规范
```

---

## 🔧 前置依赖

本项目的部分能力依赖以下外部 CLI 工具，需要用户自行安装配置：

### 1. Chrome DevTools MCP

**用途**：运行时登录流采集、异步 chunk/JS 下载、路由懒加载验证、定点浏览器补证。

- 仓库：https://github.com/ChromeDevTools/chrome-devtools-mcp
- 安装后需确保 AI Agent（Claude Code / Kimi Code CLI）已正确配置 MCP 集成
- 仅在授权测试 Host 上短时使用，不做长时间在线持续扫描

### 2. MiniMax CLI (`mmx`)

**用途**：多模态验证码自动识别，支持普通文本验证码与算术验证码。

- 仓库：https://github.com/MiniMax-AI/cli/
- 安装后需配置 `~/.mmx/config.json`（API URL + Key）
- 典型调用：
  ```bash
  mmx vision describe \
    --image "https://target.com/captcha?t=123456" \
    --prompt "这是一个验证码图片，识别验证码的具体内容。如果是算术题请直接给出计算结果。"
  ```
- **注意**：`mmx` 仅处理图片类验证码，滑块/短信/扫码/MFA 仍需跳过自动提交

> 以上工具均为可选增强能力。若未安装，审计流水线会自动降级：缺少 Chrome MCP 时仅执行静态分析；缺少 `mmx` 时遇到验证码直接跳过弱口令探测。

---

## 🚀 典型使用场景

### 场景 1：后台管理系统 JS 审计
```
输入: 前端 dist/ 目录 + 授权测试 Host
产出:
  ├─ 全量 API 台账（含未验证接口的手工发包模板）
  ├─ NoAuth 有效响应接口清单（含具体响应字段证据）
  ├─ 弱口令探测结果 + mmx 验证码识别记录
  ├─ 可绕过后台路由矩阵（附浏览器控制台验证步骤）
  └─ 硬编码 Token / 账号口令 / 文档访问路径
```

### 场景 2：Webpack 构建产物深度审计
```
输入: 生产环境可访问的 JS / source map / 入口 HTML
产出:
  ├─ Webpack chunk 完整清单（含残留/未加载 chunk）
  ├─ source map 还原后的原始源码路径、注释、调试配置
  ├─ 残留 chunk 中硬编码密码 / 默认凭证
  └─ 未被当前路由加载但可直接访问的敏感信息泄露点
```

### 场景 3：前端路由守卫 + API 交叉验证
```
输入: Vue/React/Angular 源码 + 低权限测试账号
产出:
  ├─ 前端路由绕过路径（localStorage/cookie 篡改即可进入）
  ├─ 绕过路由关联的后台 API 未授权/越权验证结果
  ├─ ParamTamper 候选清单（tenantId / orgId / roleId 篡改响应）
  └─ SafeMutationProbe 高副作用接口探测台账
```

---

## 📋 输出产物规范

审计完成后，标准输出目录结构如下：

```
{output_path}/
├── asset_mapper/
│   ├── webpack_chunk_inventory.md
│   └── api_inventory_seed.md
├── secret_audit/              # 敏感信息泄露报告
├── route_guard_audit/         # 路由守卫 + 弱口令探测报告
│   └── login_flow.md          # 运行时登录流记录
├── api_audit/
│   ├── api_inventory_full.md      # 全量 API 台账（硬性产物）
│   ├── api_inventory_full.json
│   ├── api_inventory_full.csv
│   ├── all_api_replay_templates.http   # 所有接口手工发包模板
│   ├── dynamic_validation_results.md   # 动态验证结果
│   └── backend_success_responses.md    # 后端业务成功响应证据
├── client_vuln_audit/         # 客户端漏洞报告
├── cross_analysis/            # 交叉分析产物
│   ├── high_risk_api.md
│   ├── high_risk_routes.md
│   └── evidence_index.md
├── runtime_assets/            # 运行时采集资产
│   ├── login_flow.md
│   ├── login_attempts.json    # 含 mmx 验证码识别记录
│   ├── runtime_js_urls.txt
│   ├── downloaded_chunks/
│   └── downloaded_maps/
├── deobfuscated/              # 反混淆/还原产物
└── final_report.md            # 最终汇总报告（必须含全量 API 台账）
```

---

## ⚠️ 安全声明

- 本项目所有动态请求验证能力**仅针对用户授权的沙箱/测试目标**
- 弱口令探测采用**高命中小字典 + 成功即停止**策略，不做无限制爆破
- 高副作用接口优先使用 **SafeMutationProbe**（不存在 ID / canary / dryRun）进行低副作用探测
- 未授权外部目标仅输出 HTTP 请求模板，**不主动发包**

---

## 📝 设计哲学

> **先求全量，再求精准；先落证据，再下结论。**

- 全量 API 台账优先于漏洞筛选
- source map / 残留 chunk 与浏览器已加载代码同等重要
- 低副作用探测优先于直接跳过
- 后端业务响应字段证据优先于状态码猜测
- CORS / 点击劫持 / 缺失安全头默认降噪，不进入高危列表

---

## ⚖️ 法律声明与免责条款

**本项目仅供网络安全行业从业者、安全研究人员及授权渗透测试人员在合法授权范围内使用。**

1. **合法使用**：使用本项目的任何功能前，您必须确保已获得目标系统的明确书面授权。禁止对未授权的目标进行任何形式的扫描、探测或攻击。

2. **研究目的**：本项目旨在辅助安全审计研究、漏洞发现与防御能力验证，不得以任何形式用于非法入侵、数据窃取、破坏系统或任何违反法律法规的活动。

3. **后果自负**：**下载、安装或使用本项目，即视为您已充分理解并同意自行承担因使用本项目而产生的一切法律后果、技术风险和安全责任，与项目作者及贡献者无关。**

4. **无担保声明**：本项目按"原样"提供，不提供任何明示或暗示的担保，包括但不限于适销性、特定用途适用性及非侵权性的担保。

5. **遵守法律**：使用者应当遵守《中华人民共和国网络安全法》及相关法律法规，以及所在国家/地区的所有适用法律。

---

*Made for Red Team AI Agents. Use Responsibly.*
