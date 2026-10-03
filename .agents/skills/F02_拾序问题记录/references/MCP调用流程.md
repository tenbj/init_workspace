# MCP调用流程

## 环境定位

若已连接拾序MCP，直接使用对应工具。否则使用已安装MCP SDK的Python执行本技能scripts/shixu_mcp.py；本工作区配套环境为.temp/shixu-venv/Scripts/python.exe，系统Python可能没有MCP包。先核对环境存在，不自动安装或修改Codex配置。

脚本从当前工作区output/*/03_代码程序/*/application/mcp_server.py定位唯一应用；多个候选或迁移后传--application明确目录。默认URL为http://127.0.0.1:8765，可传--url；现有服务只接受回环地址。MCP进程不自动启动API。

## 调用和请求落盘

从工作区根运行示例（替换实际路径）：

```powershell
& '.temp/shixu-venv/Scripts/python.exe' '.agents/skills/F02_拾序问题记录/scripts/shixu_mcp.py' --tool get_system_status
& '.temp/shixu-venv/Scripts/python.exe' '.agents/skills/F02_拾序问题记录/scripts/shixu_mcp.py' --tool list_issues
```

搜索参数文件为 {"q":"问题关键字"}，使用--input读取；get_issue为 {"issue_id":"真实ID"}。

写入前取得最新revision；按 B02 保护将写入的子项目工作文件，完整请求保存至对应子项目03_代码程序下独立任务目录。中间件为请求JSON，最终件为回读结果JSON，错误保留在任务记录；不直写output根目录。请求含新UUID request_id、读取到的expected_version、actor审计标签和AI定义的tag。创建请求结构：

```json
{"body":{"title":"用户的问题","description":"用户已提供的背景","tag":"AI定义的分类","priority":"中","actor":"Codex","request_id":"新UUID","expected_version":0}}
```

示例中的0仅为占位，必须替换为实际读取版本。请求中的背景也是占位，不要原样提交。使用assets/请求模板.json时须替换所有占位符。

```powershell
& '.temp/shixu-venv/Scripts/python.exe' '.agents/skills/F02_拾序问题记录/scripts/shixu_mcp.py' --tool create_issue --input '<任务目录>/request.json' --output '<任务目录>/result.json'
```

更新请求为 {"issue_id":"真实ID","body":{"tag":"新分类","request_id":"新UUID","expected_version":最新版本,"actor":"Codex"}}。仅传要修改字段。脚本支持health、list、get、create、update，不开放删除和状态流转。

## 回读、并发与失败

写工具必须读取持久化请求文件；脚本不生成或替换request_id，不悄悄改变expected_version。create/update返回成功后自动get_issue并核对显式字段，输出confirmed和问题详情。只读调用只返回读取数据。批量逐条调用，每次使用最新版本。

超时、断线或503时结果可能未知：保留完整原请求，以同一request_id重试；不要生成新编号盲目重建。成功后的回读失败提示“写入已返回成功但回读未确认”，按ID再读或重放原请求。409重读对象和版本、评估并发，再准备新请求；422修正输入后使用新编号。任何参数变化均属于新请求。回读字段不同可能有后续并发编辑，不能自动覆盖。

输出文件保存失败时也不得据此断言业务写入失败；先回读确认。request_id仅防止同一请求重试重复，不替代语义查重。
