# 前端路由守卫绕过模式

- 修改 `localStorage/sessionStorage/cookie` 中的 `token/isLogin/roles/permissions`。
- 直接访问 Hash 路由：`/#/admin/...`。
- 修改动态路由缓存或菜单缓存后刷新。
- 利用白名单匹配错误：大小写、编码、尾斜杠、分号、双斜杠、`startsWith` 前缀。
- 登录 `redirect` 参数跳转后台路径或外域。
- 前端按钮隐藏但 API 未鉴权。

高危必须关联后端 API 未授权或有效凭证泄露。
