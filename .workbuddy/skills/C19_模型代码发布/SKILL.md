---
name: C19_模型代码发布
description: 当用户需要发布数仓模型加工SQL到GitLab时，完成仓库更新、规范落位、分支提交、MR核对，并调用F05发送钉钉通知。
---
# C19_模型代码发布 · WorkBuddy桥接

先读取工作区AGENTS及 `.agents/skills/C19_模型代码发布/SKILL.md`，按源入口执行。
scripts、references、assets均以 `.agents/skills/C19_模型代码发布/` 为基准。
稳定编号按当前注册表解析；桥接不授予额外权限。B01仅人工显式调用。
