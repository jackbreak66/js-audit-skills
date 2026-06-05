# 运行时登录流与弱口令小字典规范

用于 JS 审计流水线在授权测试 Host 上短时使用 Chrome MCP/浏览器采集后台登录系统的真实运行时资产。目标是补齐登录前后才加载的 JS/chunk/source map、认证上下文和高价值后台 API；不是做长时间在线扫描或无限制爆破。

## 触发条件

满足任一条件即可执行：

- URL、标题、页面文案包含 `login/admin/manage/system/console/dashboard/后台/管理系统`。
- 页面存在用户名/密码表单。
- 代码或 Network 中出现 `login/auth/token/menu/permission/userInfo/router`。
- 静态资产中存在后台路由、菜单权限 API、动态路由懒加载或登录接口。

## 浏览器采集步骤

### 1. 登录前

记录：

- 当前 URL、title、入口 HTML。
- 表单字段名：账号、密码、验证码、租户/组织、rememberMe。
- 验证码/2FA/短信/扫码/MFA/频控迹象。
- 初始 JS/CSS/runtime config/source map URL。
- 登录按钮点击事件和登录接口候选。

### 2. 登录提交

- 有验证码且无法可靠识别：跳过自动提交，记录原因。
- 有验证码且可识别：允许一次性辅助填写；失败或出现频控/MFA时停止。
- 无验证码：执行默认弱口令小字典；成功即停止，不扩大字典。
- 每次尝试只记录必要摘要：账号、密码类型/脱敏值、请求 URL、业务 code/msg、是否出现 token/cookie/storage/redirect。

### 3. 登录成功后

采集：

- `localStorage/sessionStorage/cookie` 新增或变化的键名和值类型，值默认脱敏。
- `Authorization`、`X-Token`、CSRF、tenant/org/dept 等认证/上下文字段来源。
- dashboard/layout/menu/userInfo/permission/router/config API。
- 登录后首屏和少量高价值后台路由触发的异步 JS/chunk/source map。
- route → chunk → API 的对应关系。

## 默认弱口令小字典

控制在小规模、高命中、低扰动范围内；成功即停止。

```text
admin/123456
admin/admin
admin/admin123
admin/admin@123
admin/12345678
admin/password
admin/888888
admin/123qwe
admin/qwe123456
administrator/123456
root/root
root/123456
test/test
test/123456
user/user
user/123456
guest/guest
demo/demo
system/system
sysadmin/sysadmin
```

若源码、JS、注释、配置、接口响应中发现默认账号/密码线索，优先尝试线索组合；不要自动扩展为大字典。

## 登录成功判定

不能只看 HTTP 状态码。需要结合至少两个证据：

- 响应业务字段表示成功：`code=0/200`、`success=true`、`token`、`data.accessToken` 等。
- Cookie、localStorage、sessionStorage 出现认证值。
- 跳转到 dashboard/admin/console 页面。
- 后台 DOM、菜单、用户名、角色信息出现。
- 自动请求 `userInfo/menu/permission/router/config` 并返回有效数据。

## 停止条件

出现以下任一情况立即停止自动尝试：

- 登录成功。
- 验证码不可识别。
- 短信、扫码、MFA、人机验证、滑块等需要人工交互。
- 账户锁定、剩余尝试次数、频控、IP 风控提示。
- 用户未授权对该 Host 做运行时登录尝试。

## 输出文件

写入 `{output_path}/runtime_assets/`：

```text
login_flow.md
login_attempts.json          # 密码和 token/cookie 脱敏
runtime_js_urls.txt
downloaded_chunks/
downloaded_maps/
runtime_asset_index.md
```

`login_flow.md` 至少包含：

- 后台系统识别依据。
- 登录页、登录接口、表单字段、验证码/2FA/频控状态。
- 弱口令小字典执行/跳过原因、成功判定依据。
- 登录后认证上下文键名和值类型。
- 登录触发异步 JS/source map 数量和路径。
- 回流到静态审计的目录和后续影响。

## 报告判定

- 弱口令成功 + 可访问后台路由/API：按弱口令风险报告，并继续评估后台 API 暴露范围。
- 弱口令失败 + 无验证码：不直接判漏洞；建议人工在授权范围内做密码爆破/口令强度验证。
- 验证码/MFA/频控导致跳过：记录为自动化限制，建议人工辅助验证。
- 登录触发的 JS/chunk/source map 必须回流资产映射、敏感信息、路由守卫、API 和客户端漏洞审计。
