# 文档与AI接入

H02 交付的系统必须让人能安装、让程序能调用、让 AI 知道工具顺序。

## 必备中文文档

至少包含：

- 系统说明：解决什么问题、页面入口、服务边界。
- 环境准备：Python/Node/数据库/浏览器依赖，凭据从哪里以 env 进入进程。
- 启动停止：本地启动、停止、状态检查命令。
- API 文档：路径、方法、请求、响应、错误码、幂等规则。
- MCP 安装指南：服务启动和 AI 客户端注册分开说明。
- 工具决策表：每个工具用途、何时用、输入、返回、副作用、顺序和异常处理。
- 示例：HTML 调用示例、Python 调用示例、AI 可复制安装任务。
- 发布说明：是否可提交 GitHub、许可证状态、公开包是否只含合成数据。

## AI 接入指南必须讲清楚

- 服务安装与 AI 客户端注册是两回事。
- Codex 配置 MCP 时只需要 Streamable HTTP URL 或 stdio 命令，不需要数据库密码。
- 先 health，再 list，再 get version，再 submit。
- `request_id` 重试同号；内容变化换新号。
- 409 先重读，不盲目重试。
- 503 不声称成功。
- 提交完成、正常或异常结论时必须有证据。

## 示例要求

HTML 示例：

- 从 API 读取列表或详情。
- 演示提交时带客户端标记、证据和版本。
- 不内置真实密钥。

Python 示例：

- 默认只读检查 health、列表和 schema。
- 写入演示必须显式参数，例如 `--write-demo`。
- 写入演示只创建新演示数据，不修改历史记录。

AI 可复制任务说明：

- 包含进入目录、安装依赖、启动服务、health 检查、配置 MCP、验证 list_tools。
- 明确不要写入密钥，不要把演示写入历史真实对象。
- 明确需要写入时只创建新的演示对象。

## MCP 工具目录

工具目录建议提供机器可读 JSON，字段包括：

- server 名称、URL、transport、instructions
- tools 数组
- 每个工具的 name、kind、purpose、when_to_use、input、returns、side_effect、order、error_handling

工具目录必须来自实际 MCP 工具，不得编造伪工具。
