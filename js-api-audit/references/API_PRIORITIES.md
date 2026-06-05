# API 未授权审计优先级（优化版）

## 一、默认可安全验证的读取类动作

优先验证：

`get`, `list`, `page`, `query`, `search`, `detail`, `info`, `tree`, `enum`, `dict`, `config`, `profile`, `preview`, `view`, `download`, `export`, `report`, `log`, `menu`, `user`, `role`, `dept`, `org`, `tenant`, `task`, `system`。

说明：

- `download` / `export` 需判断是否为读取型数据外泄，不等同于安全无风险。
- `config/system/log/report` 常常属于高价值未授权读取目标。

## 二、默认禁止自动请求的危险动作

以下动作只做静态分析，不做自动请求：

`delete`, `remove`, `del`, `clear`, `truncate`, `drop`, `disable`, `forbid`, `offline`, `shutdown`, `resetPassword`, `resetPwd`, `grant`, `assignRole`, `setRole`, `save`, `create`, `add`, `insert`, `update`, `edit`, `modify`, `bind`, `unbind`, `import`, `upload`, `approve`, `reject`, `publish`, `sync`, `execute`, `runTask`, `dispatch`, `push`, `send`, `restart`, `recover`, `restore`, `batchDelete`, `batchRemove`, `batchUpdate`。

## 三、重点敏感参数

`id`, `ids`, `userId`, `accountId`, `tenantId`, `orgId`, `deptId`, `roleId`, `permissionId`, `fileId`, `docId`, `path`, `filePath`, `url`, `downloadUrl`, `callback`, `redirect`, `returnUrl`, `status`, `isAdmin`, `type`, `key`, `code`, `dictType`, `menuId`, `taskId`。

## 四、重点敏感响应字段

`data`, `rows`, `list`, `records`, `result`, `total`, `url`, `path`, `fileUrl`, `downloadUrl`, `previewUrl`, `token`, `config`, `userInfo`, `tenantInfo`, `deptInfo`, `menuList`, `permissions`, `roles`, `logContent`。

## 五、验证顺序

1. **NoAuth**：去掉所有 Cookie、Authorization、X-Token、CSRF、tenant header。
2. **PostEmptyJsonProbe**：对 `POST` JSON 或 body 形态未知接口发送空 JSON `{}`，确认是否存在默认业务响应、默认列表或细粒度错误信息。
3. **LowPriv**：使用普通用户认证访问后台或高敏读取接口。
4. **ParamTamper**：修改 `id/userId/tenantId/orgId/roleId/fileId/path/url/status`。
5. **WideRead**：扩大 `pageSize/ids/fileIds/export scope`，观察数据面扩大。
6. **FileAccess**：对返回的 `path/url/fileUrl/downloadUrl` 拼接完整 URL 并验证是否可直接访问。

## 六、报告强制输出

以下结果必须单独写入报告：

- 无认证返回具体业务信息的接口。
- 低权限可访问后台读取接口。
- 返回文件路径、文档路径、下载地址的接口。
- 删除/修改/导入/上传等危险接口的静态台账。
- 多个环境的 `baseURL` 与隐藏后台域名。
