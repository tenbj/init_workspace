---
name: A02_安装技能
description: 当用户要评估、安装或本地化外部 Skill 时使用；完成适装判断、迁入、中文薄化与骨架补齐。
metadata:
  short-description: 评估、安装并本地化外部技能
---

# 安装技能

## 这项技能解决什么问题

- 列出可安装的外部 skill
- 在安装前做适装评估
- 把外部 skill 迁入当前项目
- 把迁入的旧 skill 本地化、汉化、薄化

## 先读哪些本地知识

- 先读 `references/主控适装评估与本地化规则.md`
- 需要通用安装流程和适装判断时，再读 `references/通用安装与适装流程.md`
- 需要确认远端抓取、鉴权和 git 降级逻辑时，再读 `references/远端抓取与降级策略.md`
- 需要确认安装后如何做中文化、薄化和骨架补齐时，再读 `references/安装后本地化检查清单.md`
- 需要核对外部 skill 原始长说明时，再读迁入 skill 自己的 `references/原始技能说明.md`

## 固定动作

1. 先判断本次是“列清单”“适装评估”“项目级安装”还是“旧 skill 迁移/本地化”
2. 只要出现安装意图，就先做适装评估
3. 用 `scripts/list-skills.py` 或 `scripts/install-skill-from-github.py` 执行实际抓取
4. 安装后立即把 skill 整理成标准命名的中文薄入口，并补齐 `agents/`、`references/`、`scripts/`、`assets/`
5. 检查迁入 skill 是否和当前主控/工作区规则冲突，再决定是否保留为 runtime skill

## 什么时候再读本 skill 的 references

- 需要判断某个 skill 该不该装、装到哪一层时，再读 `references/主控适装评估与本地化规则.md`
- 需要完整适装评估结构、结论格式和动态判断原则时，再读 `references/通用安装与适装流程.md`
- 需要确认下载、git sparse checkout、权限和目录占用处理时，再读 `references/远端抓取与降级策略.md`
- 需要确认安装后哪些内容要汉化、哪些要拆进 references、哪些噪音文件该清理时，再读 `references/安装后本地化检查清单.md`
- 需要确认安装后必须做哪些本地化动作时，也再读这份文件

## 边界

- 不因为用户点名了某个 skill 就跳过适装评估
- 不把迁入 skill 原样保留成厚 `SKILL.md`
- 不依赖已经退休的用户级 `.system/skill-installer`
- 不把全局通用能力和当前项目本地能力混成同一份漂移规则
- 不把中文短名写入 YAML `name`；`name` 必须等于标准目录名，`agents/openai.yaml` 的 `display_name` 必须等于标准目录名加三段式版本号
