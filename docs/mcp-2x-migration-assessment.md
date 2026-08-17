# mcp 2.x 迁移评估（issue #4）

日期：2026-08-17。评估对象：`mcp>=1.0.0,<2.0`（commit 7cd1282 的临时钉版）是否应迁移到 2026-07-28 发布的 mcp 2.0.0。

**结论：暂不迁移（no-go now）。** 1.x 仍在维护（安全修复 + 关键 bugfix），本项目只用 stdio + tools，迁移无收益；但迁移本身不大（见下），可在 1.x 停止安全更新或需要 2026-07-28 协议特性时再做。

## 1. 本项目用到的 1.x 低级 Server API 盘点

全部集中在 `src/mi_fitness_mcp/server.py`（750 行），无 notification handler、无 resources/prompts：

| 位置 | 用法 | v2 状态 |
| --- | --- | --- |
| `server.py:11` | `from mcp.server import Server` | 保留，导入路径不变 |
| `server.py:12` | `from mcp.server.stdio import stdio_server` | 保留，签名不变 |
| `server.py:13` | `from mcp.types import TextContent, Tool` | 保留（`mcp.types` 是 `mcp_types` 的永久别名）；`Tool(inputSchema=...)` 构造参数仍兼容 |
| `server.py:48` | `@app.list_tools()` 装饰器 | **已删除** → 构造函数 `Server(name, on_list_tools=fn)`，签名为 `(ctx, PaginatedRequestParams \| None) -> ListToolsResult`，须自行包 `ListToolsResult(tools=[...])` |
| `server.py:287` | `@app.call_tool()` 装饰器 | **已删除** → `on_call_tool=fn`，签名为 `(ctx, CallToolRequestParams) -> CallToolResult`，须自行构造 `CallToolResult(content=[...])`；注意 `params.arguments` 可能为 `None`（v1 默认 `{}`） |
| `server.py:739` | `app.run(streams, app.create_initialization_options())` | 保留，v1 的 `main()` 可原样搬过去 |

另外两处行为变化对本项目无影响或已有防护：

- v2 低级 handler 抛异常不再转成 `isError: true` 结果，而是 JSON-RPC 错误。本项目 `call_tool` 已自带 try/except 并把错误序列化为 JSON 文本返回（`server.py:323-325`），行为不变。
- v2 删除了低级 `call_tool` 的 jsonschema 入参自动校验。本项目 handler 自己做参数校验，无依赖。

## 2. 替代 API 与官方推荐路径

来源：[官方迁移指南](https://py.sdk.modelcontextprotocol.io/migration/) 与 [v2.0.0 release notes](https://github.com/modelcontextprotocol/python-sdk/releases)。

- 低级 `Server` 在 v2 是重建而非删除：装饰器换成构造函数 `on_*` 关键字参数，返回值不再自动包装。**FastMCP 更名为 `MCPServer`（`mcp.server.mcpserver`），`@mcp.tool()` 装饰器 API 不变，是官方明确推荐的路径**（指南原文："If you want these conveniences, use MCPServer"）。
- 两条迁移路线：
  - **路线 A（保低级 Server）**：只改注册方式和两个 handler 的签名/返回包装，`server.py` 内 15 个 `_handle_*` 业务函数原样保留。估 diff：server.py ±80 行 + pyproject 钉版 1 行。
  - **路线 B（重写为 MCPServer）**：15 个工具拆成 15 个 `@mcp.tool()` 函数，返回 dict 由框架自动包装。结构更清晰但 diff 大（server.py 重写约 300+ 行），且 `sync_data` 的后台任务、`sync_tasks` 状态字典等自定义逻辑要重新挂接。
- 依赖面：v2 用 httpx2 替换了 httpx，但本项目自己声明并直接使用 `httpx>=0.27.0`（`adapters/mi_fitness_cloud.py:15`），两者可共存，无影响。

## 3. 回归风险

- 离线测试套件中只有 `tests/test_workout_series.py` 触到 server 层：它以 `asyncio.run(server.list_tools())` / `server.call_tool(name, args)` 直接调用被装饰的模块级函数（5 处调用）。路线 A 下这些函数签名变为 `(ctx, params)`，该测试文件需同步改 ~20 行；其余 8 个测试文件（respx mock httpx、CLI、export、sync）不经过 MCP 协议层，预期零改动。
- 无 in-memory MCP client 测试覆盖协议线格式，迁移后建议手动用 `mcp dev` 或真实客户端冒烟一次 stdio 握手 + tools/list + tools/call。

## 4. 1.x 维护承诺

[v2.0.0 release notes](https://github.com/modelcontextprotocol/python-sdk/releases) 明确：**"v1.x is in maintenance mode"**，`v1.x` 分支持续接收关键 bug 修复和安全补丁，文档保留在 `/v1/` 路径下，官方建议未迁移者保持 `<2` 上界（示例 `mcp>=1.28,<2`）。2.0.0 发布后仍出了 v1.29.0（含 v1.x 专项 backport），维护承诺在兑现中。未公布 1.x EOL 日期。

## 5. 建议

- **现在：不动。** 保持 `mcp>=1.0.0,<2.0`（可按官方建议顺手收紧为 `mcp>=1.28,<2`，非必须）。本项目是本地 stdio 工具型 server，v2 的新特性（stateless 2026-07-28 协议、resolver DI、扩展 API）都用不上。
- **触发迁移的条件**（任一）：上游宣布 1.x EOL / 停止安全更新；需要 2026-07-28 协议特性；或某次顺手的大版本窗口。
- **真迁时走路线 A**（保低级 Server、改 `on_*` 注册）：diff ~100 行、一个测试文件小改，风险可控。路线 B 只有在打算重做 server 结构时才值得。
