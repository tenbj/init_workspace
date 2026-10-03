---
name: H01_原型设计
description: 当用户需要交互原型时使用；默认设计手机与桌面兼容体验，输出ASOC合同、HTML、机器协议及响应式验证。
---

# H01_原型设计

## 这项技能解决什么问题

- 把产品需求封装为可浏览、可被 AI 继续消费、可自动验证的原型能力包。
- 统一 Human Layer、Machine Layer 与 Evaluation Layer，避免只交付图片、截图或单个 HTML。

## 先读哪些本地知识

- 先读 `references/用户固定设计偏好.md`，落实已确认的七项通用交互要求，并把适用项写入合同及验收场景。

- 本地编号、来源与兼容边界见 `references/本地迁入说明.md`。

- 先读 `references/ASOC协议.md`，确认能力包合同与最小交付集。
- 再读 `references/原型产物规格.md`，确认文件字段、关联 ID 和完成标准。
- Web 原型默认读 `references/移动端兼容设计与验收.md`，在信息架构阶段规划手机与桌面；用户明确限定桌面时记录排除理由。
- 需求不完整或需要降级时，读 `references/独立运行与迁移规则.md`。

## 固定动作

1. 按 `input.schema.json` 整理意图、用户、场景、需求、约束和验收标准；缺口写入假设，不静默猜测。
2. 按 `workflow.yaml` 执行需求建模、信息架构、交互设计、视觉原型、机器协议和验证；在 `ui.schema.json.responsive` 声明布局、视口和核心流程验收场景。
3. 用 `scripts/create_package.py --output <目录>` 初始化完整包，不手工遗漏必备文件。
4. 完成 `prd.md`、`prototype.html`、`ui.schema.json`、`interaction.json`、`user-flow.md`、`api.yaml`、`database.sql` 和 `manifest.json`。
5. 使用一致的需求 ID、组件 ID、事件 ID、状态和接口路径贯穿所有产物。
6. 运行 `scripts/check_responsive.py <目录>`，再运行 `scripts/validate_package.py <目录> --require-responsive --report <目录>/evaluation/report.json`；布局和实际操作均通过才交付。修改 HTML 或验收场景后重跑，旧报告不能复用。

## 什么时候再读本 skill 的 references

- 需要定义组件、状态、事件、接口和数据表时，读 `references/原型产物规格.md`。
- 遇到时间压力、后端不适用、输入不足或未来编号迁移时，读 `references/独立运行与迁移规则.md`。
- 需要人工复核时，执行 `evaluation/checklist.md`；需要行为回归时，执行 `evaluation/test_cases.json`。

## 边界

- 不输出图片、截图或单纯设计稿作为最终交付；它们只能是能力包附件。
- 不把单个 `prototype.html` 当成完整原型设计结果。
- 不因时间压力省略机器层或验证层；不适用项也必须保留文件并写明理由。
- 不依赖或路由任何外部系列 Skill；H01 必须能独立完成原型能力包。
- 不在 Skill 目录保存具体项目的运行产物；实际能力包写入调用方指定目录。
- 不把缩小桌面、隐藏横向溢出或仅有截图当作移动兼容；浏览器不可用时如实记录未验收，不标记通过。
