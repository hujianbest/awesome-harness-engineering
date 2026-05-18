# Scenario Preset — `frontend-spa`

针对前端 SPA（React / Vue / Svelte / Angular / Solid / Preact）。聚焦 XSS、state 一致性、effect 副作用、依赖、性能、accessibility。

## When to Use

`audit-planner` 在 Step 0.5 推荐本 preset，当满足：

- `package.json` 命中前端框架（react / vue / svelte / angular / solid-js / preact）
- 顶层 `index.html` + 入口 `main.tsx/ts/jsx/js` 或 `App.vue/svelte`
- bundler 配置：`vite.config.*` / `webpack.config.*` / `next.config.*` / `nuxt.config.*` / `astro.config.*`

## Categories

| id | description | severity_default | examples |
|---|---|---|---|
| `xss` | `dangerouslySetInnerHTML` / `v-html` / `innerHTML` 直接拼 user input / URL scheme 未过滤 | critical | `<div dangerouslySetInnerHTML={{__html: userBio}}/>`；`<a href={userUrl}>` 未过滤 `javascript:` |
| `state-management` | state 直接 mutate / stale closure / 跨组件共享但未 lift up / Redux/Zustand store 直接修改 | high | React `state.items.push(x); setState(state)`；`useEffect` 依赖数组漏 dep；Vuex state 不走 mutation |
| `effect-correctness` | effect 缺 cleanup / 依赖错 / async effect 未取消 / setState 在 unmounted | high | `useEffect(() => { fetch... })` 无 abort；定时器未 clearTimeout；async 完成时组件已卸载 |
| `route-and-auth` | 路由 guard 缺失 / 客户端 only auth 信任 / token 存 localStorage 不刷新 | high | 后台页仅前端 `if (!user) redirect`；JWT 存 localStorage 永不过期；private route 漏 wrap |
| `dependency-vuln` | 已知漏洞 npm 包 / 未 pin / postinstall script 跑远端 / sub-dep CVE | high | `lodash<4.17.21`；`react-scripts` 旧版未升；postinstall curl \| bash |
| `bundle-and-build` | dev only code 进 production / process.env 漏给 client / source map 公开生产 source | medium | `if (process.env.NODE_ENV === 'production')` 拼错变量名；admin debug panel 进 prod bundle |
| `accessibility` | 缺 aria / 图无 alt / 表单 label 漏关联 / contrast 不足 / tabIndex 误用 / 仅鼠标交互 | medium | `<img>` 漏 alt；按钮用 `<div onClick>`；模态框打开时焦点未 trap |
| `performance` | 不必要的 re-render / 大列表无虚拟化 / bundle 未拆 / 图片未懒加载 | medium | List 渲染 10k 项不分页；`useMemo` 缺关键依赖；首屏 bundle > 500 KB |
| `forms-validation` | 表单仅前端校验信任 / 数字类型 input 当字符串 / file upload 未限类型大小 | medium | 价格字段无 min/max；email 仅前端 regex 校验；upload 接受任意 mime |
| `i18n` | 字符串 hardcode / locale 切换不持久 / RTL 不支持 / 日期 / 数字 format 写死 | low | `<button>提交</button>` 没走 i18n；`toLocaleDateString` 不传 locale |
| `network-api` | 未 timeout / 未 retry / 错误状态码 silently 当成功 / SSE / WebSocket reconnect 缺失 | medium | `fetch` 无 AbortController + timeout；500 当成功；WebSocket 断后未重连 |
| `error-handling` | error boundary 缺失 / catch + ignore / 错误未上报 / 用户无可见反馈 | medium | 整个 App 无 ErrorBoundary；promise rejection 未 .catch；fetch 失败 UI 永远 loading |
| `secret-leak` | API key 嵌入 client bundle / sourcemap 暴露后端 url / .env 全部下发到 client | high | `VITE_API_KEY=...` 实际是后端 secret；构建产物 sourcemap 公开 |
| `dead-code` | 注释代码 / 未路由组件 / feature flag 永真永假 | low | 注释 `// TODO old route`；switch 永不命中分支 |
| `contract-violation` | API client / OpenAPI 与后端 schema 漂移 / GraphQL 字段拼错 / prop type 与父传不符 | medium | 接口字段后端改 snake_case 前端仍 camelCase；GraphQL non-null 字段处理为 null |

## 二选一仲裁规则

| 二选一场景 | 优先取 |
|---|---|
| `xss` vs `state-management` | `xss` |
| `route-and-auth` vs `xss` | `route-and-auth` 若是鉴权绕过；`xss` 若是注入 |
| `effect-correctness` vs `state-management` | `effect-correctness` 若根因在 effect cleanup / dep；否则 `state-management` |
| `performance` vs `state-management`（额外 re-render） | `state-management` 若 root 是 mutation；`performance` 若是 memo 缺失 |
| `secret-leak` vs `dependency-vuln` | `secret-leak`（直接利用风险更高） |

## 不收 base 11 中的哪些 category

- 拆细 `security` → `xss` / `route-and-auth` / `secret-leak`
- 拆细 `concurrency` → `effect-correctness`（前端实际是 single-thread + effect 周期问题）
- 不收 `typing`：TS / Flow 类型问题由编译器把关，本 preset 不重复
- 不收 `i18n-or-encoding`：拆为 `i18n`（UI 文本）与 `serialization`（基本不出现）

## risk_focus 建议

- `xss`
- `route-and-auth`
- `dependency-vuln`
- `accessibility`

## 参考资料

- OWASP Top 10 — A03 Injection (XSS)
- WCAG 2.1 AA
- React Hooks rules + exhaustive-deps
- Web Almanac 2024 (performance baseline)
