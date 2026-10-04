# MCP调用流程

## 环境定位

若已连接拾序MCP，直接使用对应工具。否则使用已安装MCP SDK的Python执行本技能scripts/shixu_mcp.py；本工作区配套环境为.temp/shixu-venv/Scripts/python.exe，系统Python可能没有MCP包。先核对环境存在，日常录入不自动安装；用户明确要求首次接入时按独立技能入口执行目标客户端配置。

默认使用Streamable HTTP传输，首选HTTPS基地址 `https://shixu.eliasliu.cc`，MCP端点为 `/mcp`。可通过 `SHIXU_MCP_BASE_URL` 或显式 `--url` 覆盖，`--config`中的地址优先，保留HTTP兼容；不自动修改已有私有配置。网页账号菜单 → AI接入 → 手动配置下载私有JSON，调用时提供 `--config <私有配置>`；也可使用 `--url <服务基地址>` 和私有环境变量 `SHIXU_MCP_TOKEN`。支持HTTP和HTTPS；HTTP会输出明文传输提示，服务端须启用SHIXU_ALLOW_HTTP_AUTH=true。配置地址保留实际协议和端口，不自动降级HTTPS或跟随重定向。新设备不需要应用源码，不自动启动服务。

仅显式 `--transport stdio` 时定位output下唯一mcp_server.py，多候选需传--application；stdio同样需要私有令牌。旧全局密钥不接受。支持OAuth的客户端可在HTTPS入口网页登录授权；公网HTTP使用账号PAT。

以下示例命令须补--config或事先设置环境令牌。请求/结果按目标工作台分别保存，不得换账号重放待确认请求。401重新授权；403检查只读范围，不能切账号绕过。

## 调用和请求落盘

从工作区根运行示例（替换实际路径）：

```powershell
& '.temp/shixu-venv/Scripts/python.exe' '.agents/skills/F02_拾序问题记录/scripts/shixu_mcp.py' --tool get_system_status
& '.temp/shixu-venv/Scripts/python.exe' '.agents/skills/F02_拾序问题记录/scripts/shixu_mcp.py' --tool list_identities
& '.temp/shixu-venv/Scripts/python.exe' '.agents/skills/F02_拾序问题记录/scripts/shixu_mcp.py' --tool list_issues
```

搜索参数文件为 {"q":"问题关键字"}，使用--input读取；get_issue为 {"issue_id":"真实ID"}。

按[创建身份与模型规则](创建身份与模型规则.md)确定人员、AI身份和实际模型。没有所需身份时，使用assets/身份请求模板.json准备独立create_identity请求；人员模板应改为kind=person、via=manual、模型空字符串。脚本自动list_identities回读，确认后取真实ID。不要自动更新已有档案。

每次写入前从list_identities或list_issues等读取最新revision；身份创建也会增加当前账号revision。按 B02 保护将写入的子项目工作文件，完整请求保存至对应子项目03_代码程序下独立任务目录。中间件为请求JSON，最终件为回读结果JSON，错误保留在任务记录；不直写output根目录。请求含新UUID request_id、读取到的expected_version、actor审计标签和AI定义的tag。以下仅为已确认Elias委托Codex且明确使用该模型时的示例：

```json
{"body":{"title":"用户的问题","description":"用户已提供的背景","tag":"AI定义的分类","priority":"中","actor":"Codex","creation":{"identityId":"<实际AI身份ID>","initiatedByPersonId":"<实际人员ID>","modelInfo":{"name":"GPT-6.1 Sol","provider":"OpenAI"}},"request_id":"新UUID","expected_version":0}}
```

示例中的0仅为占位，必须替换为实际读取版本。背景、UUID、身份ID也须替换。未知人员省略initiatedByPersonId；未知模型必须显式传modelInfo={}，不能省略或传null而继承档案默认值。assets/请求模板.json默认为未知人员与模型，必须按已确认上下文填入真实信息；不是将所有新记录都设为未知。

```powershell
& '.temp/shixu-venv/Scripts/python.exe' '.agents/skills/F02_拾序问题记录/scripts/shixu_mcp.py' --tool create_issue --input '<任务目录>/request.json' --output '<任务目录>/result.json'
```

更新请求为 {"issue_id":"真实ID","body":{"tag":"新分类","request_id":"新UUID","expected_version":最新版本,"actor":"Codex"}}。仅传要修改的业务字段，不传creation。脚本允许get_connection_context、get_system_status、list_identities、create_identity、list_issues、get_issue、create_issue、update_issue八个工具，不开放身份修改、删除和状态流转。

## 回读、并发与失败

写工具必须读取持久化请求文件；脚本不生成或替换request_id，不悄悄改变expected_version。问题create/update返回成功后自动get_issue，对照写入响应核对编号、标题、描述、分类、优先级、状态与六项创建快照；create还核对请求中的身份ID、发起人ID与模型。create_identity后按返回ID查list_identities核对档案。仅全部一致才输出confirmed=true。只读调用只返回读取数据。已连接的MCP直接调用也要执行同样的落盘和回读步骤。批量逐条调用，每次使用最新版本。

新create_issue缺少creation或显式modelInfo时脚本拒绝执行。仅升级前已发送且结果待确认的无creation原请求，允许加--legacy-retry按原文重放，不补字段、不换UUID或版本。不是旧请求则不能用该开关绕过来源记录。

超时、断线或503时结果可能未知：保留完整原请求，以同一request_id重试；不要生成新编号盲目重建。成功后的回读失败提示“写入已返回成功但回读未确认”，按ID再读或重放原请求。409重读对象和版本、评估并发，再准备新请求；422修正输入后使用新编号。任何参数变化均属于新请求。回读字段不同可能有后续并发编辑，不能自动覆盖。

输出文件保存失败时也不得据此断言业务写入失败；先回读确认。request_id仅防止同一请求重试重复，不替代语义查重。
