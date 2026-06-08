---
name: js-route-guard-audit
description: 前端登录逻辑、路由守卫和客户端权限绕过审计工具。用于审计 Vue Router、React Router、Angular Router、Nuxt/Next 中间件、ASP.NET 前端页面跳转、后台登录流、验证码/2FA、弱口令小字典结果、菜单权限和本地登录状态判断，发现仅依赖 localStorage、sessionStorage、Cookie、Vuex/Pinia/Redux 状态、meta.roles、hidden 菜单或前端按钮控制的后台功能访问风险，并与 API 未授权审计交叉验证真实后端影响。
---

# JS Route Guard Audit - 前端登录与路由守卫审计

审计前端是否把认证、角色、菜单和后台访问控制错误地放在客户端；重点识别可通过 Vue/React/Angular 路由或直接 URL/hash 进入后台功能的路径，并与后端 API 鉴权交叉验证。

## 关键判定

前端路由绕过本身通常只证明 UI 可见，不等于后端越权。只有满足以下任一条件才可判高危：

1. 进入后台页面后关联 API 无需认证或低权限可调用。
2. 前端泄露有效 Token/签名/租户头，可调用后台 API。
3. 纯前端应用本身处理敏感数据或离线权限决策。
4. ASP.NET 页面/接口后端也缺少服务端授权校验。

否则按 `ROUTE` 低/中风险输出，并明确需要 API 验证。

## 工作流程

### 1. 路由与守卫入口定位

优先读取 `/js-asset-mapper` 的路由清单，然后检查：

| 框架 | 重点文件/模式 |
|------|---------------|
| Vue | `router.beforeEach`、`addRoute(s)`、`meta.requiresAuth`、`meta.roles`、`permission.js`、Pinia/Vuex |
| React | `PrivateRoute`、`ProtectedRoute`、`RequireAuth`、`react-router` loader/action、Redux/Zustand |
| Angular | `canActivate`、`canLoad`、`AuthGuard`、`RoleGuard` |
| Nuxt/Next | middleware、route rules、client-only guards、`useAuth` |
| ASP.NET | JS 跳转、隐藏菜单、`.aspx` 前端判断、`__doPostBack` 参数 |

### 2. 登录状态来源追踪

追踪以下 source：

- `localStorage/sessionStorage/cookie` 中的 `token/isLogin/user/roles/permissions`。
- URL/hash/query 中的 `token`、`redirect`、`ticket`、`code`。
- Store 状态：Vuex/Pinia/Redux/NgRx。
- `window.__INITIAL_STATE__`、`window.__CONFIG__`。

记录每个 source 是否可由用户直接修改，以及是否被用于关键分支。

### 2.1 运行时登录流验证（后台系统）

当目标表现为后台/管理端登录系统时，按 `../js-shared/RUNTIME_LOGIN_FLOW.md` 进行短时运行时验证，并把结果写入本专项报告。重点是确认登录态来源、登录成功判定和登录后路由/API加载，不做无限制爆破。

必须识别：

| 项目 | 重点 |
|------|------|
| 登录表单字段 | `username/account/user/loginName/mobile/email`、`password/pwd/pass`、`captcha/code/verifyCode`、`tenant/org/dept`、`rememberMe` |
| 登录接口 | `/login`、`/auth/login`、`/api/login`、`/admin/login`、`/oauth/token`、`/sso/login` |
| 验证码/2FA | 图片验证码优先调用本地 `mmx vision describe` 自动识别（普通文本/算术均可）；识别成功则继续弱口令探测，失败则跳过。滑块/短信/扫码/MFA 跳过自动提交。 |
| 前端加密/签名 | RSA/JSEncrypt、CryptoJS、md5/sha256、timestamp、nonce、sign、captchaKey/uuid |
| 成功判定 | 不能只看 HTTP 200；需结合业务 `code/msg/success/data/token`、cookie/storage 变化、redirect、后台 DOM、menu/userInfo/router API |
| 弱口令结果 | 成功/失败/跳过原因；成功即停止；密码在报告中脱敏 |

若后台系统无验证码，默认弱口令小字典未成功，报告中写入“建议人工在授权范围内进行密码爆破/口令强度验证”，但不要把该提示直接判为已确认高危。

### 3. 守卫逻辑审计点

| 风险 | 检查点 |
|------|--------|
| 本地标志绕过 | `if (localStorage.getItem('isLogin')) next()` |
| Token 只判存在 | 不校验过期、签名、服务端会话，仅存在即放行 |
| 角色客户端可信 | `roles.includes('admin')` 来自 localStorage/可改 store |
| 白名单过宽 | `startsWith('/login')`、正则错误、大小写/编码/尾斜杠绕过 |
| 动态路由污染 | 后端菜单未校验即 `addRoute`，或本地缓存 routes 可修改 |
| 菜单隐藏替代鉴权 | 按钮/菜单隐藏但路由和 API 仍可访问 |
| redirect/open redirect | 登录后 redirect 参数未校验，可跳外域或后台路径 |
| 404/兜底路由 | wildcard/HashHistory 导致受保护组件被加载 |

### 4. 绕过验证步骤

生成浏览器控制台验证步骤和路由访问矩阵：

```javascript
localStorage.setItem('token', 'test')
localStorage.setItem('roles', '["admin"]')
location.href = '/#/admin/user'
```

同时输出关联 API 验证任务给 `/js-api-audit`：

```markdown
| 路由 | 组件 | 绕过方式 | 关联 API | 后端验证状态 |
|------|------|----------|----------|--------------|
| /admin/user | User.vue | 修改 localStorage.roles | GET /api/admin/users | 待 API 审计 |
```

若运行时弱口令成功登录，还需额外输出：

- 成功账号（密码脱敏或写弱口令类型）。
- 登录后写入的 token/cookie/storage 键名和值类型（默认脱敏）。
- 登录后首屏路由、菜单权限 API、动态路由 API 和新增 chunk。
- 这些认证上下文对应的 `/js-api-audit` 验证模式：`WeakCredentialAuth`。

## 输出要求

```
{output_path}/route_guard_audit/{project_name}_js_route_guard_audit_{timestamp}.md
```

报告章节：

1. 路由守卫总览。
2. 登录态与角色来源表。
3. 受保护路由矩阵。
4. 可绕过路径详情。
5. 运行时登录流、验证码/2FA、弱口令小字典结果。
6. 与 API 未授权交叉验证任务。
7. 修复建议。

## 自检

- [ ] 每个守卫入口都有文件和行号。
- [ ] 每条受保护路由都标注 `requiresAuth/roles/permission` 来源。
- [ ] 可控登录态来源已追踪到 localStorage/cookie/store/URL。
- [ ] 若存在后台登录页，已记录验证码/2FA、登录接口、登录成功判定、弱口令小字典执行/跳过原因。
- [ ] 没有把纯 UI 绕过直接判为高危；已关联 API 审计状态。
- [ ] 已输出可复现的控制台步骤或 URL 访问步骤。
