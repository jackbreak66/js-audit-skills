# 强化版前端敏感信息模式

## 1. 高风险字段名

### 认证与凭证
- `token`
- `accessToken`
- `refreshToken`
- `authorization`
- `Authorization`
- `auth`
- `secret`
- `client_secret`
- `appSecret`
- `tenantSecret`
- `signKey`
- `encryptKey`
- `apiKey`
- `appKey`
- `ak`
- `sk`
- `cookie`
- `session`
- `sessionId`

### 账号与口令
- `username`
- `userName`
- `user`
- `USER`
- `loginName`
- `account`
- `admin`
- `password`
- `passwd`
- `pwd`
- `newpassword`
- `oldpassword`
- `initPassword`
- `defaultPassword`
- `resetPassword`
- `szUserName`
- `szPassword`

### 路径与附件
- `path`
- `url`
- `file`
- `doc`
- `upload`
- `download`
- `export`
- `attachment`
- `attach`
- `baseURL`

### 权限与业务关键字段
- `role`
- `permission`
- `tenant`
- `module`
- `certificate`
- `certificates`
- `attributes`
- `issuer`
- `jwks`

---

## 2. 高可信格式

- AWS Access Key: `AKIA[0-9A-Z]{16}`
- JWT: `eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9._-]+\.[A-Za-z0-9._-]+`
- Firebase API Key: `AIza[0-9A-Za-z_-]{35}`
- Private Key: `-----BEGIN [A-Z ]*PRIVATE KEY-----`
- Basic Auth: `Authorization\s*[:=]\s*["']?Basic\s+[A-Za-z0-9+/=]+`
- Bearer Token: `Authorization\s*[:=]\s*["']?Bearer\s+[A-Za-z0-9._-]+`
- Sentry DSN: `https://[^\s"'@]+@[^\s"']+/\d+`

---

## 3. 弱格式但必须保留

### 明文账号口令值
- `admin`
- `Aa123456@`
- `smallwei`
- `123456`
- `yw123456`
- `measure1Monitor`
- `measure2Monitor`
- `measure3Monitor`
- `measure4Monitor`
- `measure5Monitor`
- `measure6Monitor`
- `measure7Monitor`
- `measure8Monitor`
- `measure9Monitor`
- `measure10Monitor`
- `web_user`

### 弱 token / 控制字段
- `delimiter`
- `attribute`
- `showEnumMembers`

### 疑似摘要 / 固定值
- `^[a-fA-F0-9]{16}$`
- `^[a-fA-F0-9]{32}$`
- `^[a-fA-F0-9]{40}$`
- `^[a-fA-F0-9]{64}$`
- `^[A-Za-z0-9+/]{20,}={0,2}$`

---

## 4. 文档与附件路径模式

- `/oms/\d{8}/[^\s"']+\.(doc|docx|xls|xlsx|pdf|zip)`
- `/(upload|uploads|download|downloads|export|exports|attach|attachment)/[^\s"']+`
- `https?://[^\s"']+\.(doc|docx|xls|xlsx|pdf|zip)`

---

## 5. 配对规则

以下字段若在同一对象、同一请求体、相邻 20 行内同时出现，应优先提升为账号口令对：

- `username` + `password`
- `user` + `password`
- `account` + `pwd`
- `szUserName` + `szPassword`
- `loginName` + `newpassword`

---

## 6. 降噪规则

### 可降噪词
- `example`
- `sample`
- `dummy`
- `mock`
- `placeholder`
- `your_key_here`

### 不可直接降噪的场景
- 命中出现在生产 bundle 或 source map
- 命中出现在 webpack runtime 引用、server_present_unloaded、orphan/stale 独立 chunk 或旧 chunk 中
- 命中出现在请求头、登录参数、下载接口、初始化配置附近
- 命中与账号、密码、token、路径组合出现
- 命中可被拼接成完整 URL 或调用链

## 7. Webpack chunk 覆盖

对 Webpack splitChunks 站点，以下位置出现的账号/密码/token 不得忽略：

- 浏览器 Network 加载的合并 chunk。
- `webpack_chunk_inventory.json` 枚举出的 runtime 引用 chunk。
- 服务器可访问但当前浏览器未加载的独立 chunk/旧 chunk。
- `.js.map` 的 `sourcesContent`。

如果 `password:"Aa123456@"` 只存在于 `pages-login-routers-bindMobile.<hash>.js` 这类未加载独立 chunk，仍按默认口令/硬编码密码线索输出。
