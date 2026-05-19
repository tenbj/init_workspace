---
name: A03_系统更新
description: 当核心骨架变更需要同步系统标准时使用；识别差异并更新 .system，不更新 exe。
---

# A03_系统更新

## 这项技能解决什么问题

- 识别工作区核心骨架的结构、注册表、标准和命令入口变更。
- 在确认变更应进入系统标准后，只更新 `.system/standards/`。
- 与发布和初始化工具构建解耦，不更新 `00_系统治理` 内程序，也不重新封装 exe。

## 先读哪些本地知识

- 先读 `.system/standards/workspace-spec.json` 和 `.system/standards/Skills管理标准.md`。
- 涉及目录、命名、历史或初始化层时，再读对应 `.system/standards/*.md`。
- 需要展开识别口径、更新矩阵和禁止项时，再读 `references/核心骨架识别规则.md`。

## 固定动作

1. 运行 `scripts/detect_core_skeleton_changes.py`，识别 Skill 注册、Claude 命令、Rule、标准文件和 BOM 脚本清单差异。
2. 判断差异是否属于核心骨架：目录骨架、必备文件、`.system` 标准、Skill 注册表、命令入口、初始化覆盖层或编码检查清单。
3. 只修改 `.system/standards/` 中需要同步的标准文件，保持机器可读 SSOT 与人类可读标准一致。
4. 修改后复查 `.system` 内引用是否闭环：注册表、映射表、路径、版本号和命名口径互相一致。
5. 若用户还需要更新初始化工具或 exe，转交 B09；本 Skill 到 `.system` 更新为止。

## 什么时候再读本 skill 的 references

- 不确定某类变更是否属于核心骨架时，读 `references/核心骨架识别规则.md`。
- 不确定应修改哪一个 `.system/standards/` 文件时，读 `references/核心骨架识别规则.md` 的更新矩阵。
- 遇到“要不要同步 exe、00 程序或模板”的判断时，读 `references/核心骨架识别规则.md` 的边界。

## 边界

- 不修改 `output/00_系统治理/03_代码程序/src`、`src/templates`、`dist/*.exe` 或任何封装产物。
- 不执行 PyInstaller、`build.ps1`、GitHub Release、tag 或发布动作。
- 不把一次性讨论、业务研究结论或临时方案写进 `.system`。
- 不把稳定业务真相直接塞进 `SKILL.md`，展开规则放入 `references/`。
