<!-- memory-version: 1.3.0 -->
# 知识提炼 · Skills管理体系

> 从 Skills 管理体系研究中提炼的长期规则与设计结论，持续更新。

---

## 2026-05-09 · 斜杠调用与版本号

**核心观点**：
- Skill 的 YAML `name` 应采用 `{域代码}{编号}_{技能名}_v{MAJOR}.{MINOR}.{PATCH}`。
- 这样既保留 `/B01` 这类短编号快速命中，也让斜杠候选项直接显示当前版本。
- Skill 版本 bump 后，文件夹名、YAML `name`、`workspace-spec.json` 引用必须同步更新。

**关键框架/模型**：
- 文件夹名：管理视角，负责磁盘排序和版本追踪。
- YAML `name`：调用视角，负责斜杠菜单显示、搜索和版本确认。
- `skillRegistry`：若后续版本 bump 频繁，用稳定编号降低引用路径同步成本。

**与其他话题的关联**：
- → 工作区标准：`.system/standards` 中的 Skills 管理标准需要与该规则保持一致。

---

## 2026-05-09 · 迁移清单边界

**核心观点**：
- 当前 15 个本地 Skill 全部需要迁移，因为没有任何一个同时满足新标准的文件夹名与 YAML `name`。
- 迁移不只是改 `SKILL.md` frontmatter，还必须同步 `workspace-spec.json`、BOM 脚本路径、规则文件、Skill 内部示例路径和 `agents/openai.yaml`。
- 8 个核心治理 Skill 牵动 `overwriteLayer.skills`；7 个带 BOM 要求的脚本牵动 `bomCheck.files`。

**关键框架/模型**：
- 本体变更：文件夹重命名 + YAML `name`。
- 引用变更：SSOT、Rules、SKILL.md、references、openai.yaml。
- 验证变更：迁移后必须跑框架体检，并重点看 `overwriteLayer.skills` 与 `bomCheck.files`。

**与其他话题的关联**：
- → `skillRegistry`：如果文件夹名持续带版本号，后续版本 bump 的引用同步成本会持续存在。

---

## 2026-05-09 · Skill 编号版本迁移执行

**核心观点**：
- 执行 Skill 编号版本迁移时，必须同时完成四层同步：文件夹名、YAML `name`、`agents/openai.yaml` 展示名、SSOT/规则/脚本引用。
- 子项目分类名（如 `02_课题研究`）不是 Skill 名，不能被机械替换成 `B05_课题研究_v1.0.0`。
- 对 `.ps1` 脚本做引用更新时，必须保持 UTF-8 with BOM，否则后续体检会报 BOM 问题。

**关键框架/模型**：
- 迁移前：备份所有 Skill 文件夹、Rules 和 `.system/standards`。
- 迁移中：先改本体，再改引用，再补展示配置。
- 迁移后：用框架体检验证 `overwriteLayer.skills`、`bomCheck.files`、BOM 和子项目结构。

**与其他话题的关联**：
- → 项目规范化：脚本 fallback 必须跟随 SSOT 更新，避免 spec 读取失败时回落到旧 Skill 名。

---

## 2026-05-10 · 稳定 ID 依赖

**核心观点**：
- 跨 Skill 依赖不宜散落完整实现名（如 `B04_子项目管理_v1.0.0`），否则每次版本 bump 都会触发大量反向文本更新。
- 依赖关系应使用稳定 ID（如 `B04`、`C03`），当前实现由 `workspace-spec.json` 的 `skillsManagement.registeredSkills` 解析。
- 只有调用契约不兼容时，才通过接口主版本（如 `project.create@2`）触发依赖方迁移。

**关键框架/模型**：
- 稳定 ID：负责“依赖谁”，不随版本变化。
- 注册表：负责从 `B04` 解析到当前唯一实现 `B04_..._vX.Y.Z`。
- 接口契约：负责判断兼容性，例如 `project.create@1`、`doris.show_create_table@1`。
- 完整实现名：只用于落盘文件夹、YAML name、命令文件、路径示例和历史说明。

**与其他话题的关联**：
- → Skills管理标准：后续应补充稳定 ID 依赖规则、接口契约表和依赖声明模板。
- → 框架体检：后续可检查 `registeredSkills` 稳定 ID 唯一性和 `dependencies` 可解析性。

---
