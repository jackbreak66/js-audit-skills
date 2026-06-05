# 前端 JS 混淆与构建产物处理策略

## 处理优先级

1. 读取源码优先：`src/`、`pages/`、`views/`、`components/`、`router/`、`store/`、`api/`。
2. 若只有构建产物，优先找 source map：`//# sourceMappingURL=...`、`.map`、Webpack `sourcesContent`。
3. 对 Webpack/Vue CLI/Nuxt splitChunks 构建，先按 `WEBPACK_CHUNK_COVERAGE.md` 枚举 runtime 引用、合并 chunk、独立 chunk、旧 chunk、source map；不要只处理浏览器当前加载文件。
4. 无 source map 时做最小可读化：格式化、字符串提取、调用点定位、请求封装还原。
5. 遇到加密/运行时解密 bundle，定位解密函数、密钥、eval/new Function/importScripts 调用，把解密后的派生产物写入 `deobfuscated/`。
6. 不覆盖原文件；所有还原文件命名为 `{original}.pretty.js`、`{original}.decoded.js`、`{original}.sourcemap/`。

## 识别特征

| 类型 | 特征 | 处理 |
|------|------|------|
| Webpack/Vite bundle | `__webpack_require__`、`import.meta.env`、chunk 文件 | 找 manifest、source map、动态 import |
| Webpack splitChunks/残留 chunk | `__webpack_require__.u`、chunk id→name/hash 映射、`pages-a~pages-b` 合并 chunk、服务器上可访问的未加载独立 chunk | 运行 `webpack_chunk_inventory.py`，将 runtime_referenced/server_present_unloaded/orphan chunk 全部回流扫描 |
| JSFuck/obfuscator | 大量 `_0x`、`eval(function(p,a,c,k,e,d))`、字符串数组 | 先格式化，再静态提取字符串表和解码函数 |
| ASP.NET 前端 | `.aspx/.ascx/.cshtml`、`PageMethods`、`__doPostBack`、`Sys.Net.WebServiceProxy` | 提取 WebMethod/PageMethod、隐藏字段、ViewState 相关请求 |
| 加密配置 | `CryptoJS.AES.decrypt`、`atob`、`pako.inflate`、自定义 xor | 追踪密钥来源和解密输出 |
| sourcemap 泄露 | `.map`、`sourcesContent`、原始路径 | 用 source map 还原 API、注释、密钥、源码结构 |

## 必须记录

- 原始文件路径、大小、hash 或 chunk 名称。
- 还原方法和命令。
- source map 是否包含 `sourcesContent`。
- Webpack chunk 来源：runtime_loaded / runtime_referenced / server_present_unloaded / sourcemap_referenced / orphan/stale。
- 无法还原时保留字符串、URL、函数名和调用关系证据。
