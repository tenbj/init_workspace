# AGENTS.md - Codex 工作区入口

本文件是 Codex 在本工作区的启动入口，只保留强制门、SSOT 顺序和标准读取路由。具体制度不在入口重复展开，统一回到 `.system/standards/`、`.agents/rules/` 和对应 Skill。

## SSOT 顺序

1. `.system/standards/workspace-spec.json` 是机器可读 SSOT，负责目录骨架、必备文件、Skill 注册表、历史命名和初始化口径。
2. `.system/standards/*.md` 是人类可读标准；其中 `Skills管理标准.md` 是 Skill 管理与跨 Skill 引用的 SSOT。
3. `.agents/rules/*.md`、`.agents/skills/*/SKILL.md`、`.claude/commands/*.md` 是执行层。执行层与标准冲突时，以标准为准，并记录需要回修的差异。
4. `output/` 中的方案、问答、研究文档只算过程记录，不覆盖标准。

## 强制门索引

- 会话开始或进入项目工作前：执行 `B01`，做只读框架体检。
- 输出任何知识性回答前：先读 `.agents/rules/direction-rules.md`，完成话题归属；没有对应子项目时执行 `B04`；实质性回答必须完整落到对应 `output/` 文档，对话框只给摘要。
- 开始新话题、新研究或新知识产出前：执行 `B04`，先建立或定位标准子项目。
- 修改任何 live 文件前：执行 `B02`，按目标类型完成备份；备份未完成不得修改。
- 结束回复前：执行 `B03`，按信息增量写入 `.memory`；系统规则变化写入 `.memory/系统记录/`。
- 修改 `.ps1` 前：读 `.agents/rules/version-control-rules.md` 和 `workspace-spec.json` 的 `bomCheck.files`，保持 UTF-8 with BOM。
- 新建、升级、删除 Skill，或处理跨 Skill 依赖、编号引用、命令包装：读 `Skills管理标准.md`。

## 标准读取时机

- 判断目录骨架、初始化、exe 行为、必备文件、历史区结构：读 `workspace-spec.json`，必要时读 `工作区骨架规格.md`。
- 判断文件/目录命名、版本号、历史备份命名、`.memory` 当前态和历史态：读 `工作区命名规范.md`。
- 执行具体动作时，再读对应 `.agents/rules/*.md` 或具体 `SKILL.md`。

## Skill 编号分流

- 当请求、文档或 Skill 指令出现 `A01`、`B04`、`C03` 这类稳定编号时，立即读取 `Skills管理标准.md` 的“跨 Skill 稳定编号引用规则”。
- Skill 内不复制路由细则，只保留稳定编号或业务意图；编号到完整 Skill 文件夹名的解析规则由 `Skills管理标准.md` 统一定义。
- 找不到唯一目标时停止执行并报告，不猜测旧名称。
