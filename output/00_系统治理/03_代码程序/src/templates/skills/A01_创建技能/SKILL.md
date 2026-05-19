---
name: A01_创建技能
description: 当用户要新建、重写或薄化本地 Skill 时使用；生成标准骨架、薄入口、references 路由与校验结果。
metadata:
  short-description: 新建、重写与薄化本地技能
---

# 创建技能

## 这项技能解决什么问题

- 新建主控或工作区本地 skill
- 重写已有 skill 的入口说明
- 把厚 `SKILL.md` 拆成薄入口 + `references/`
- 在工作区建骨架、改造现成目录时补齐本地 skill

## 先读哪些本地知识

- 先读 `references/主控技能创建增量规则.md`
- 需要通用设计原则与取舍方法时，再读 `references/通用技能设计原则.md`
- 需要判断怎样把 skill 做成薄入口时，再读 `references/薄技能设计模式.md`
- 需要完整创建步骤、命名和校验清单时，再读 `references/技能创建完整流程.md`
- 需要生成或补 `agents/openai.yaml` 时，再读 `references/openai_yaml.md`

## 固定动作

1. 先判断本次是“新建 skill”“重写 skill”“薄化 skill”还是“补工作区本地 skill 骨架”
2. 先拆清楚：哪些内容留在薄 `SKILL.md`，哪些下沉到 `references/`、`scripts/`、`assets/`
3. 用 `scripts/init_skill.py` 按 `{域代码}{编号}_{技能名}` 生成或补齐标准骨架；版本通过 `--version` 写入 `agents/openai.yaml` 的 `display_name`
4. 把 `SKILL.md` 收口成薄入口，只保留触发、动作骨架、references 路由和边界
5. 用 `scripts/generate_openai_yaml.py` 生成或更新 `agents/openai.yaml`，其中 `display_name` 必须等于稳定标准 Skill 名加三段式版本号
6. 用 `scripts/quick_validate.py` 校验产物是否仍是薄 skill

## 什么时候再读本 skill 的 references

- 需要判断主控场景下该不该新建独立 runtime skill 时，再读 `references/主控技能创建增量规则.md`
- 需要补技能设计原则、自由度选择、适装自检时，再读 `references/通用技能设计原则.md`
- 需要设计 references/scripts/assets 的分工，或把厚 `SKILL.md` 拆成薄入口时，再读 `references/薄技能设计模式.md`
- 需要完整创建步骤、命名约束、反模式和校验清单时，再读 `references/技能创建完整流程.md`
- 需要核对 `display_name`、`short_description`、图标等 UI 字段时，再读 `references/openai_yaml.md`

## 边界

- 不把稳定业务知识重新塞回 `SKILL.md`
- 不为了形式主义生成 README、CHANGELOG、安装说明等噪音文件
- 不把偶发冷规则误做成新的 runtime skill
- 不生成缺少 `agents/`、`references/`、`scripts/`、`assets/` 的半成品 skill
- 不接受缺少域编号的 Skill 名称，也不接受在目录名或 `SKILL.md` YAML `name` 中写版本号
