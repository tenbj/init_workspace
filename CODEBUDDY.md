# CODEBUDDY.md · WorkBuddy桥接入口

本文件是本工作区的CodeBuddy / WorkBuddy兼容入口。先读取 [AGENTS.md](AGENTS.md)，按其中的SSOT顺序、标准读取路由和授权边界执行；本入口仅补充桥接路径与本地日志约定，不另设一套工作区制度。

## 技能调用

- 桥接入口位于 `.workbuddy/skills/<稳定Skill名称>/SKILL.md`，源逻辑位于 `.agents/skills/<稳定Skill名称>/SKILL.md`。桥接目录名、frontmatter的name和description应与当前源技能一致。
- 调用时先读桥接壳指向的源SKILL.md，再按源技能的步骤和边界执行。`scripts/`、`references/`、`assets/`等相对路径均以源技能目录为基准；命令工作目录和参数按源技能说明设置。
- 稳定编号路由按 [Skills管理标准.md](.system/standards/Skills管理标准.md) 执行，以 [workspace-spec.json](.system/standards/workspace-spec.json) 的 `skillsManagement.registeredSkills` 为准；目标缺失或不唯一时报告，不猜测旧名称。
- B01仅在用户显式调用或明确要求框架体检时执行，不因会话开始、批量修改或调用其他技能而自动运行。
- A00不建立桥接壳。只有人工本轮明确触发时，才读取并执行 [A00源技能](.agents/skills/A00_超管模式/SKILL.md)；普通任务授权不等价于启动超管模式，激活条件与有效期按AGENTS和A00执行。
- PowerShell读取项目文本显式使用 `Get-Content -LiteralPath <path> -Encoding UTF8 -Raw`；修改脚本时遵守工作区的BOM要求。

## 输出与记忆

按AGENTS及源技能完成话题归属、产出和任务进度管理。已有主题复用相应子项目，新主题按B04处理。

框架记忆由B03按内容路由：PROJECT写对应子项目对话记录，SYSTEM写系统记录，BOTH分别写入两类；知识提炼和地图按B03的触发条件维护。不得将所有技能执行记录统一写入子项目对话记录。

WorkBuddy会话中的本地运行摘要可追加到 `.workbuddy/memory/YYYY-MM-DD.md`，日期按Asia/Shanghai。该日志不替代框架记忆，也不是SSOT；只保留必要摘要，不记录凭据或敏感配置。`.workbuddy/memory/`已由根.gitignore忽略，本地文件继续保留；技能桥接目录不受这条规则影响。

超管模式生效时，按A00暂停项目自动落盘与记忆流程，不因本入口再次触发B系列强制门或本地日志写入。

## 权限与规则来源

入口文件（包括本文件）及 `.system/` 的写入边界统一执行 [AGENTS.md](AGENTS.md) 的“写入权限边界”。桥接调用不扩大源技能的权限，普通修改请求不作为A00触发条件；显式A类技能调用涉及的标准写入也只限该源技能声明的授权范围。

Git任务执行 [Git版本控制标准.md](.system/standards/Git版本控制标准.md) 和B11。提交、推送、合并、发布按用户实际授权分别处理，不能由桥接壳自动扩大操作范围。

## 当前桥接清单

2026-10-09核对：注册技能50个，排除A00后有效桥接49个。以下是当前索引；注册表或源技能变更后应重新核对，不以本表覆盖SSOT。

| 编号 | 桥接入口 |
|------|----------|
| A01 | [A01_创建技能](.workbuddy/skills/A01_创建技能/SKILL.md) |
| A02 | [A02_安装技能](.workbuddy/skills/A02_安装技能/SKILL.md) |
| A03 | [A03_系统更新](.workbuddy/skills/A03_系统更新/SKILL.md) |
| B01 | [B01_框架体检](.workbuddy/skills/B01_框架体检/SKILL.md) |
| B02 | [B02_版本控制备份](.workbuddy/skills/B02_版本控制备份/SKILL.md) |
| B03 | [B03_记忆管理](.workbuddy/skills/B03_记忆管理/SKILL.md) |
| B04 | [B04_子项目管理](.workbuddy/skills/B04_子项目管理/SKILL.md) |
| B05 | [B05_课题研究](.workbuddy/skills/B05_课题研究/SKILL.md) |
| B06 | [B06_项目规范化](.workbuddy/skills/B06_项目规范化/SKILL.md) |
| B07 | [B07_系统治理方案沉淀](.workbuddy/skills/B07_系统治理方案沉淀/SKILL.md) |
| B08 | [B08_任务进度管理](.workbuddy/skills/B08_任务进度管理/SKILL.md) |
| B09 | [B09_GitHub发布](.workbuddy/skills/B09_GitHub发布/SKILL.md) |
| B10 | [B10_课题分离](.workbuddy/skills/B10_课题分离/SKILL.md) |
| B11 | [B11_Git分支工作流](.workbuddy/skills/B11_Git分支工作流/SKILL.md) |
| C01 | [C01_同步代码仓库](.workbuddy/skills/C01_同步代码仓库/SKILL.md) |
| C02 | [C02_数仓生产库查询](.workbuddy/skills/C02_数仓生产库查询/SKILL.md) |
| C03 | [C03_Doris建表语句查询](.workbuddy/skills/C03_Doris建表语句查询/SKILL.md) |
| C04 | [C04_临时数据存储](.workbuddy/skills/C04_临时数据存储/SKILL.md) |
| C05 | [C05_1对1DWD单表SQL生成](.workbuddy/skills/C05_1对1DWD单表SQL生成/SKILL.md) |
| C06 | [C06_DWD字段信息Excel生成](.workbuddy/skills/C06_DWD字段信息Excel生成/SKILL.md) |
| C07 | [C07_ODS-DWD-一键生成](.workbuddy/skills/C07_ODS-DWD-一键生成/SKILL.md) |
| C08 | [C08_数据代理分析](.workbuddy/skills/C08_数据代理分析/SKILL.md) |
| C09 | [C09_data-assets依赖Excel生成](.workbuddy/skills/C09_data-assets依赖Excel生成/SKILL.md) |
| C10 | [C10_数仓交付文档生成](.workbuddy/skills/C10_数仓交付文档生成/SKILL.md) |
| C11 | [C11_ODS表粒度主键核验](.workbuddy/skills/C11_ODS表粒度主键核验/SKILL.md) |
| C12 | [C12_SQL主线识别](.workbuddy/skills/C12_SQL主线识别/SKILL.md) |
| C13 | [C13_模型使用说明生成](.workbuddy/skills/C13_模型使用说明生成/SKILL.md) |
| C14 | [C14_上下游数量一致性核验](.workbuddy/skills/C14_上下游数量一致性核验/SKILL.md) |
| C15 | [C15_数据平台质量指标配置](.workbuddy/skills/C15_数据平台质量指标配置/SKILL.md) |
| C16 | [C16_SQL业务溯源与诊断](.workbuddy/skills/C16_SQL业务溯源与诊断/SKILL.md) |
| C17 | [C17_数仓质量治理编排](.workbuddy/skills/C17_数仓质量治理编排/SKILL.md) |
| C18 | [C18_数据模型SQL开发](.workbuddy/skills/C18_数据模型SQL开发/SKILL.md) |
| D04 | [D04_架构图生成](.workbuddy/skills/D04_架构图生成/SKILL.md) |
| E01 | [E01_模型设计标准化](.workbuddy/skills/E01_模型设计标准化/SKILL.md) |
| E02 | [E02_模型评审编排](.workbuddy/skills/E02_模型评审编排/SKILL.md) |
| E03 | [E03_模型命名建议](.workbuddy/skills/E03_模型命名建议/SKILL.md) |
| E04 | [E04_模型设计运行归档](.workbuddy/skills/E04_模型设计运行归档/SKILL.md) |
| E05 | [E05_模型设计文档生成](.workbuddy/skills/E05_模型设计文档生成/SKILL.md) |
| F01 | [F01_钉钉文档下载](.workbuddy/skills/F01_钉钉文档下载/SKILL.md) |
| F02 | [F02_拾序问题记录](.workbuddy/skills/F02_拾序问题记录/SKILL.md) |
| F03 | [F03_报表使用说明生成](.workbuddy/skills/F03_报表使用说明生成/SKILL.md) |
| F04 | [F04_汇报表格制作](.workbuddy/skills/F04_汇报表格制作/SKILL.md) |
| G01 | [G01_HTML交互产物](.workbuddy/skills/G01_HTML交互产物/SKILL.md) |
| G02 | [G02_单画布ER图生成](.workbuddy/skills/G02_单画布ER图生成/SKILL.md) |
| G03 | [G03_HTML回答生成](.workbuddy/skills/G03_HTML回答生成/SKILL.md) |
| H01 | [H01_原型设计](.workbuddy/skills/H01_原型设计/SKILL.md) |
| H02 | [H02_原型系统交付](.workbuddy/skills/H02_原型系统交付/SKILL.md) |
| I01 | [I01_内网穿透](.workbuddy/skills/I01_内网穿透/SKILL.md) |
| I02 | [I02_系统部署升级](.workbuddy/skills/I02_系统部署升级/SKILL.md) |


## 验证范围

已核对桥接集合、源文件存在性、name/description一致性和本地memory忽略规则。WorkBuddy客户端的自动发现与索引刷新、依赖凭据的业务技能运行，不在这次本地文件验证范围内，不能据此宣称已通过运行时集成验收。
