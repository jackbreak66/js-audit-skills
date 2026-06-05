# 客户端漏洞 Source/Sink 速查

## Sources

`location.href/search/hash`, `URLSearchParams`, `document.referrer`, `localStorage/sessionStorage`, `document.cookie`, `postMessage event.data`, `WebSocket message`, `API response`, `window.name`。

## DOM XSS Sinks

`innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `v-html`, `dangerouslySetInnerHTML`, `bypassSecurityTrustHtml`, template compiler。

## Code Execution Sinks

`eval`, `new Function`, string `setTimeout/setInterval`, dynamic script insertion, dynamic import with user-controlled path。

## Navigation Sinks

`location.href`, `location.assign`, `location.replace`, `window.open`, router push/replace with untrusted redirect。

## 降噪项

- CORS、点击劫持、缺失 `X-Frame-Options`/`frame-ancestors`、缺失/宽松 CSP 不是 JS source → sink 链路，默认不作为高价值客户端漏洞输出。
- 如确需记录，放入“低优先级加固项”；不得标记为高危或严重。
- 若它们与真实影响组合，按真实根因评级：例如 API 越权按 `API`，可利用 DOM XSS 按 `XSS`，有效凭证泄露按 `SECRET`。
