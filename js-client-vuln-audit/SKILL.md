---
name: js-client-vuln-audit
description: 前端 JavaScript 客户端攻击面审计工具。用于审计 Vue、React、Angular、ASP.NET 前端中的 DOM XSS、模板注入、开放跳转、postMessage 信任边界、WebSocket 消息处理、原型污染、客户端加密误用、JWT 和本地存储风险、Service Worker 缓存、source map 暴露、npm 依赖风险和前端供应链问题，作为敏感信息、路由守卫、API 未授权之外的红队补充审计；CORS/点击劫持/缺失安全响应头默认仅作为加固噪音项处理。
---

# JS Client Vulnerability Audit - 客户端攻击面审计

覆盖前端 JS 项目中除敏感信息、路由守卫和 API 未授权以外的高价值客户端风险。重点找“可由 URL、postMessage、存储、API 响应或用户输入控制并到达危险 sink”的链路。

## 适用边界

- 本 skill **主要适合白盒/灰盒 JS 代码审计**：从源码、bundle、source map、构建产物、一次性抓取的 runtime chunk 中追 source → sink 链路。
- Chrome MCP/浏览器自动化只用于定点补证，例如确认某路由懒加载的 JS 文件、某按钮触发的 XHR、某 payload 是否到达 DOM；不建议作为“实时持续监听所有异步 JS 并现场审计”的主流程。
- 如果只能通过浏览器看到异步加载代码，先导出资源 URL/HAR 或下载 chunk，再纳入静态审计；不要把短暂运行时观察替代完整证据链。
- CORS、点击劫持、缺失 `X-Frame-Options`/`frame-ancestors`/CSP **默认不作为漏洞主线**，只在“低优先级加固项/待验证项”中记录，且不得标为高危或严重。

## 审计类别

| 类别 | Source | Sink/风险点 |
|------|--------|-------------|
| DOM XSS | `location/search/hash`、API 响应、postMessage、storage | `innerHTML`、`v-html`、`dangerouslySetInnerHTML`、`document.write`、模板编译 |
| JS 执行 | URL/storage/API | `eval`、`new Function`、字符串 `setTimeout`、动态 import |
| 开放跳转 | query `redirect/returnUrl/next` | `location.href/replace/assign`、`window.open` |
| postMessage | `message` event | 缺少 origin/source 校验、信任 `event.data` |
| 原型污染 | query/JSON/API 响应 | `Object.assign`、`merge`、`$.extend(true)` 写入 `__proto__/constructor` |
| 客户端加密 | 硬编码 key、可逆加密 | `CryptoJS`、自定义 XOR、前端签名 |
| 存储风险 | Token/JWT/PII | localStorage/sessionStorage/cookie 缺陷、长生命周期 |
| Service Worker | cache/fetch handler | 缓存敏感响应、离线包污染、scope 过宽 |
| 依赖供应链 | `package-lock`、bundle | 已知前端依赖漏洞、恶意依赖、source map 泄露 |

### 明确降噪/默认不报漏洞

| 项目 | 处理方式 |
|------|----------|
| CORS 响应头 | JS 静态审计中通常无法准确认定；除非有可复现跨域读取敏感数据链路，否则不报漏洞。即使记录也不得高于中危，优先归类为后端 API 验证项。 |
| 点击劫持 / 缺失 XFO / 缺失 `frame-ancestors` | 默认加固项，不进漏洞详情；如有明确受害者交互 + 敏感状态改变 PoC，最高中危。 |
| 缺失/宽松 CSP | 默认加固项；只有与可利用 XSS 链路组合时，按 XSS 本身评级，不按 CSP 缺失评级。 |
| Mixed content、通用安全头缺失 | 默认低危/信息项，不进入高危列表。 |

## 工作流程

### 1. 建立 source 到 sink 清单

优先使用 `/js-asset-mapper` 的扫描 JSON，然后人工补充：

```bash
rg -n "(innerHTML|outerHTML|insertAdjacentHTML|v-html|dangerouslySetInnerHTML|document\.write|eval\(|new Function|postMessage|addEventListener\(['\"]message|location\.(href|assign|replace)|window\.open|Object\.assign|merge\(|__proto__)" "{source_path}"
```

### 2. DOM XSS 数据流追踪

对每个 sink 追踪：

1. 输入是否来自 URL、hash、query、storage、postMessage、API 响应或用户表单。
2. 中间是否经过 sanitizer：DOMPurify、escapeHTML、Vue/React 自动转义。
3. 是否使用绕过 API：`v-html`、`bypassSecurityTrustHtml`、`dangerouslySetInnerHTML`。
4. 输出最小 payload 和触发路由。

### 3. postMessage 审计

必须检查：

- `event.origin` 是否严格等于可信域，不接受 `*`、`indexOf`、`endsWith` 宽松判断。
- 是否校验 `event.source`。
- `event.data` 是否可触发路由跳转、DOM 写入、Token 读取、API 请求。
- `postMessage(..., '*')` 是否发送敏感数据。

### 4. 开放跳转与 OAuth 回调

检查 `redirect`、`returnUrl`、`next`、`callback` 参数是否：

- 允许外域、协议相对 URL、编码绕过、反斜杠绕过。
- 与 OAuth/SSO code/token 流组合导致 Token 泄露。
- 登录路由守卫中未校验目标路径。

### 5. 原型污染

重点确认是否存在：

```javascript
merge(target, JSON.parse(location.hash.slice(1)))
Object.assign(config, userControlledObject)
$.extend(true, {}, queryObject)
```

若污染对象影响鉴权、路由、请求头、模板配置或 sanitizer 配置，提升评级。

### 6. 前端供应链与配置

- 检查 `package.json`、lockfile 中的前端高危依赖，并记录是否打进生产 bundle。
- 检查生产是否暴露 `.map`、`.env`、`manifest`、调试面板。
- HTML/meta/server hint 只用于解释客户端风险，不主动把 CORS、点击劫持、CSP/XFO 缺失列为高危漏洞；若无法看到响应头，标注“需运行时验证/加固项”。

### 7. 可选浏览器/MCP 定点补证

仅在静态证据不足时使用：

1. 打开目标路由，记录实际加载的 JS/CSS/source map/chunk URL。
2. 对特定交互记录 XHR/fetch/WebSocket 请求、请求体和响应状态。
3. 将 runtime 发现的 chunk 下载或导出为 HAR，再回到 source/sink 或 API 还原流程。
4. 不做无限滚动式监听；不因单独发现 CORS、点击劫持或安全头缺失给高危/严重评级。

## 输出要求

```
{output_path}/client_vuln_audit/{project_name}_js_client_vuln_audit_{timestamp}.md
```

报告章节：

1. 客户端攻击面概述。
2. Source/Sink 矩阵。
3. 漏洞详情：按 `../js-shared/OUTPUT_STANDARD.md` 通用块。
4. 可复现 PoC：URL、控制台步骤或 HTML postMessage PoC。
5. 需要动态验证的依赖和运行时行为。
6. 低优先级加固项：CORS、点击劫持、CSP/XFO 等仅列摘要，不进入高危/严重漏洞列表。

## 自检

- [ ] 每个 XSS/跳转/postMessage 问题都有 source → sink 链路。
- [ ] 已区分框架自动转义和显式危险 API。
- [ ] postMessage 已检查 origin/source/data 三项。
- [ ] 原型污染已说明污染对象是否影响安全决策。
- [ ] 供应链和 source map 风险已标注是否进入生产构建。
- [ ] CORS、点击劫持、缺失 CSP/XFO 未被标为高危或严重；无明确利用链时仅作为加固项。
- [ ] 如使用 Chrome MCP/浏览器，只用于定点补证，并已把 runtime chunk/HAR 转化为可复查静态证据。
