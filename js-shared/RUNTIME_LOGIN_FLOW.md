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

- **有验证码：优先调用本地 `mmx` 视觉识别工具进行自动识别**，详见下文「验证码识别工具（mmx）」章节。识别成功则自动填入并继续弱口令探测；识别失败或 `mmx` 不可用时，跳过自动提交，记录原因。
- 有验证码但无法可靠识别（`mmx` 不可用、调用失败或输出不可解析）：跳过自动提交，记录原因。
- 无验证码：执行默认弱口令小字典；成功即停止，不扩大字典。
- 每次尝试只记录必要摘要：账号、密码类型/脱敏值、验证码识别来源（`mmx`/`manual`/无）、请求 URL、业务 code/msg、是否出现 token/cookie/storage/redirect。

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

## 验证码识别工具（mmx）

当登录页存在图片验证码（含普通文本验证码、算术验证码）时，允许调用本地 `mmx vision describe` 进行自动识别，以扩展弱口令探测的覆盖范围。

### mmx 调用前提

- 本地已安装 `mmx` CLI，且环境可访问 MiniMax API（`api.minimaxi.com`）。
- 验证码为**图片类**（`<img>`、`base64`、`canvas` 截图可获取），非滑块、短信、扫码、MFA。

### 验证码识别流程

```
1. 定位验证码元素与字段
   └─ 记录验证码字段名：captcha / code / verifyCode / captchaCode / imgCode / validateCode
   └─ 记录验证码图片获取方式：
      a. <img src="/captcha?t=xxx"> → 提取 src URL（注意去掉固定随机数，保留可刷新 URL 模板）
      b. base64 data URI → 保存为临时 PNG/JPEG
      c. canvas 绘制 → 截图保存

2. 对每个弱口令组合执行（有验证码时限制最多前 5 个高优先级组合）：
   a. 刷新验证码：重新请求验证码 URL（追加随机参数如 ?t=Date.now() 避免缓存），或刷新页面后重新提取。
   b. 将验证码图片下载/保存到临时路径：{output_path}/runtime_assets/captcha_temp/。
   c. 调用 mmx：
      mmx vision describe \
        --image "{captcha_image_path_or_url}" \
        --prompt "这是一个验证码图片，识别验证码的具体内容。如果是算术题请直接给出计算结果。"
   d. 解析 mmx 输出：
      • 算术验证码：匹配「答案是 **XX**」→ 提取 XX 作为验证码值。
      • 文本验证码：匹配「验证码内容是：**XX**」或「内容是：**XX**」→ 提取 XX；否则提取第一个 **XX** 加粗块。
      • 输出为空、无加粗块、包含"无法识别""看不清"等 → 视为识别失败。
   e. 将识别结果填入验证码字段，组装完整登录请求（username + password + captcha + 其他固定字段）。
   f. 发送登录请求，记录：HTTP 状态、业务 code/msg、是否提示"验证码错误"。
   g. 若后端返回"验证码错误/已过期/不匹配"：
      • 记录本次识别结果与失败原因。
      • 继续下一个弱口令组合（回到 2a 刷新验证码）。
   h. 若后端返回"用户名或密码错误"：
      • 说明验证码识别成功（已通过验证码校验关卡），继续下一个弱口令。
   i. 若出现账户锁定、剩余尝试次数、频控、IP 风控：立即停止。

3. 识别失败回退
   • mmx 调用失败（网络、API 错误、本地未安装）→ 跳过自动弱口令提交。
   • 连续 2 次解析不出有效验证码内容 → 跳过自动弱口令提交。
   • 记录跳过原因和 mmx 原始输出（脱敏后）。
```

### 验证码场景下的弱口令限制

有验证码时，为避免高频请求触发风控，弱口令小字典只取**前 5 个高优先级组合**：

```text
admin/123456
admin/admin
administrator/123456
root/root
test/test
```

若源码/注释中发现默认账号密码线索，可替换为线索组合，但总数仍不超过 5 次。

### mmx 输出解析规则（供 agent 使用）

```javascript
// 伪代码：从 mmx stdout 提取验证码值
function extractCaptchaFromMmx(stdout) {
  // 算术题：答案是 **25**
  const mathMatch = stdout.match(/答案是\s*\*\*(\S+)\*\*/);
  if (mathMatch) return mathMatch[1].trim();

  // 明确标注
  const explicitMatch = stdout.match(/验证码内容是：\*\*(\S+)\*\*/);
  if (explicitMatch) return explicitMatch[1].trim();

  // 通用加粗块 fallback
  const genericMatch = stdout.match(/\*\*([^*\s]+)\*\*/);
  if (genericMatch) return genericMatch[1].trim();

  return null; // 识别失败
}
```

### 记录要求

`login_attempts.json` 中每条验证码相关尝试必须包含：

```json
{
  "timestamp": "...",
  "username": "admin",
  "password_type": "common_weak",
  "captcha_source": "mmx",
  "captcha_recognized": "JS98",
  "captcha_raw_mmx_output": "图片中的验证码内容是：**JS98**",
  "response_code": "...",
  "response_msg": "...",
  "captcha_validation_passed": true,
  "login_success": false
}
```

## 停止条件

出现以下任一情况立即停止自动尝试：

- 登录成功。
- 验证码不可识别（`mmx` 不可用、调用失败、输出不可解析）。
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
