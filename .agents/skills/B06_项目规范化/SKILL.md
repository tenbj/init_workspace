---
name: B06_项目规范化
description: 严格按工作区标准执行结构规范化：先脚本检查修复，再由大模型对 output、.history、.memory 等区域做标准自查、语义迁移和异常留痕。
metadata:
  short-description: 脚本修复 + 大模型标准自查
---

# 项目规范化

## 何时使用

- 用户说“规范化项目”“严格按标准整理”“检查并修正工作区结构”
- 脚本、Skill、Rule、初始化 EXE 修改后，需要确认产物与 `.system/standards/` 完全对齐
- 发现 `output/`、`.history/`、`.memory/`、`.system/` 存在旧结构、命名残留、迁移异常
- 需要把脚本无法理解的遗留结构交给大模型按标准判断、匹配和落盘记录

## 这项技能解决什么问题

本 Skill 不是单纯运行 `normalize.ps1`。它的职责是把工作区整理到“脚本可检查 + 大模型可理解 + 标准可追溯”的状态。

执行时必须先让脚本完成确定性检查与机械修复，再由大模型读取标准，对 `output/`、`.history/`、`.memory/`、`.system/` 做语义自查。凡是脚本结果与标准不一致、标准未覆盖、或需要人工理解归类的情况，都由大模型按标准补齐；不能确定的异常必须记录到 `00_系统治理` 子项目。

## 固定动作

1. 读取 `.system/standards/workspace-spec.json`、`工作区骨架规格.md`、`工作区命名规范.md`、`Skills管理标准.md`
2. 按 `references/严格规范化流程.md` 运行脚本阶段：先 `--Check`，需要修复时再 `--Fix`
3. 按 `references/标准自查清单.md` 做大模型复核，重点覆盖 `output/`、`.history/`、`.memory/`
4. 对 PowerShell 文本读取命令做编码自查；`Get-Content` 读取 UTF-8 文本必须显式使用 `-Encoding UTF8`
5. 对可确定的差异执行标准化修改；修改前必须按 `B02` Skill 备份目标
6. 对无法安全自动判断的异常，按 `references/异常记录规范.md` 写入 `00_系统治理`
7. 修复后再次运行脚本检查，并人工确认剩余 WARN/FAIL 是否已记录或已有处理结论
8. 结束前按 `B03` Skill 写入系统治理记录

## 先读哪些本地知识

- 先读 `.system/standards/workspace-spec.json`
- 再读 `.system/standards/工作区骨架规格.md`
- 再读 `.system/standards/工作区命名规范.md`
- 涉及 Skill、Rule、脚本或 `.agents/skills/` 时，再读 `.system/standards/Skills管理标准.md`
- 需要执行细节时，按下方路由读取本 Skill 的 references

## 什么时候再读本 skill 的 references

- 需要知道脚本命令、阶段顺序、二次检查口径时，读 `references/严格规范化流程.md`
- 需要判断 `output/`、`.history/`、`.memory/` 是否和标准一致时，读 `references/标准自查清单.md`
- 需要记录无法迁移、语义不明、标准缺口、脚本遗漏时，读 `references/异常记录规范.md`

## 边界

- 不把脚本结果当最终答案；脚本只是第一阶段
- 不允许平铺老项目仅因“脚本未报错”而视为合规
- 不静默忽略 `.history/`、`.memory/` 的标准差异
- 不改写 `.system/standards/` 作为迁就现状的手段；标准本身需要更新时，必须走系统治理记录
- 不删除异常项；能迁移则迁移，不能确定则留痕，确认为多余时移入 `.temp/规范化异常_{yyyyMMddHHmmss}/`
