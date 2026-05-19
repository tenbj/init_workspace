---
name: B09_GitHub发布
description: 当用户需要把项目提交 GitHub、创建 tag、发布 Release、维护 CHANGELOG 或生成 Release Notes 时使用；覆盖发布流程、更新日志方案、发布前检查和回滚边界。
---

# GitHub 发布

## 这项技能解决什么问题

- 把当前工作区按安全、可追溯、可发布的方式提交到 GitHub。
- 维护项目级 `CHANGELOG.md`、Release Notes、tag、Release 附件和校验信息。
- 将内部 `output/*/版本记录.md`、Git commit 和 GitHub Release 分层，避免把内部治理噪声直接发布给用户。

## 先读哪些本地知识

- 先读 `references/发布流程.md`，确认默认发布顺序。
- 涉及更新日志、版本号、Release Notes 时，读 `references/更新日志方案.md`。
- 涉及发布前验收、安全扫描、资产校验时，读 `references/发布前检查.md`。
- 需要执行命令或生成命令时，读 `references/GitHub命令模板.md`。

## 固定动作

1. 先运行 `scripts/update_init_program.ps1` 更新 `output/00_系统治理/03_代码程序/src` 内的初始化程序：全量刷新 `src/templates`，同步版本常量，并生成 `.b09_update_manifest.json`。
2. 确认第 1 步成功后，再运行 `scripts/build_init_exe.ps1` 重封装 `dist/初始化工作区_v*.exe`；该脚本默认要求存在更新清单，否则停止构建。
3. 确认发布目标：仓库、公开版本号、主要交付物、是否需要上传 Release 附件。
4. 按 B01/B02/B03/B08 的强制门处理体检、备份、任务进度和记忆。
5. 汇总 Git 差异、内部版本记录和构建产物，整理 `CHANGELOG.md` 与 Release Notes。
6. 执行发布前检查：工作区状态、敏感信息、忽略规则、构建产物、hash、体检结果。
7. 按用户授权执行 GitHub 推送、tag、Release 创建和附件上传；没有授权时只给可执行命令清单。
8. 发布后记录 Release URL、tag、资产名、SHA256、验证结果和后续事项。

## 什么时候再读本 skill 的 references

- 只问“怎么设计更新日志”时，重点读 `references/更新日志方案.md`。
- 要真正发布或推送时，完整读 `references/发布流程.md` 与 `references/发布前检查.md`。
- 需要复制命令、改版本号、算 hash 或创建 Release 时，读 `references/GitHub命令模板.md`。
- 遇到 tag 已存在、Release 创建失败、远端不同步、敏感扫描失败时，回到 `references/发布流程.md` 的异常边界。

## 边界

- 不在未完成敏感信息检查时推送公开仓库或创建 Release。
- 不跳过 `00_系统治理` 内初始化程序更新脚本与 exe 重封装脚本就进入 GitHub 发布。
- 不手工比对或零散复制初始化程序模板；更新程序时以当前 live 工作区为权威源，全量刷新到最新。
- 不把 `.history/`、`.memory/`、`input/`、`.temp/`、本机私有配置或 `*.exe` 直接提交进 Git。
- 不把 GitHub 自动生成 Release Notes 当作唯一事实源；它只能作为草稿辅助。
- 不覆盖用户已有 Git 配置、远端、tag 或 Release；冲突时先报告并等待用户确认。
- 不在聊天、文档、脚本或命令历史中暴露 GitHub token。
