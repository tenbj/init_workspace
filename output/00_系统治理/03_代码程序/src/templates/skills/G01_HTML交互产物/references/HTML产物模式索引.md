# HTML产物模式索引

## 适装评估

- 结论：条件安装
- 建议范围：当前项目项目级聚合安装
- 新增知识价值：补充 HTML 作为可交互输出面的模式库，覆盖报告、图示、决策矩阵、数据探索、路线图和编辑器等高结构产物。
- 能力重叠度：与通用前端实现能力有交集，但它提供的是“何时用哪类 HTML 产物”的产物模式，而不是 Web App 工程能力。
- 运行环境耦合度：原仓库服务器回传链路依赖 Claude Code；本地化后只保留剪贴板降级与单文件 HTML，耦合可控。
- 流程负担：若 16 个 Skill 全部注册会显著扩大触发面；聚合入口可把负担降到可接受。
- 触发范围：仅在用户需要视觉化、交互式或可分享 HTML 成果时触发。
- 上下文成本：薄入口 + 按需 references，避免常驻加载原始长说明。
- 简短结论：值得安装，但必须聚合、薄化，并禁用 Claude Code 专属监听假设。

## 模式清单

| 原始 Skill | 本地用途 |
|---|---|
| `html-spec-planning` | 规格、RFC、实现计划、方案探索 |
| `html-code-review` | PR 说明、重构风险图、代码走读 |
| `html-design-prototypes` | 组件原型、动画调参、设计系统探索 |
| `html-research-reports` | 多来源研究报告、事故复盘、状态报告 |
| `html-throwaway-editor` | 一次性编辑器、排序、标注、配置整理 |
| `html-interactive-playground` | 参数滑块、调参面板、实时对比 |
| `html-brainstorm-grid` | 未命名候选的多方案发散比较 |
| `html-svg-diagrams` | 通用流程图、时序图、状态机、依赖图 |
| `html-slideshow-deck` | 键盘可导航 HTML 幻灯片 |
| `html-design-tokens` | 色板、字体、间距、阴影、动效 token 展示 |
| `html-architecture-diagrams` | 系统架构、部署拓扑、服务依赖、数据所有权 |
| `html-data-explorer` | CSV/JSON/log 的过滤表格、搜索和轻量图表 |
| `html-comparison-matrix` | 已命名候选的加权决策矩阵 |
| `html-timeline-roadmap` | 时间线、路线图、甘特视图、发布计划 |
| `html-erd-explorer` | ERD、数据模型、表关系、迁移前后对比 |
| `html-mind-map` | 分支想法、知识结构、调试假设、概念地图 |

## 分流规则

- 已经有明确候选并要求比较：用 `html-comparison-matrix`。
- 还没有候选，只是在探索方向：用 `html-brainstorm-grid` 或 `html-spec-planning`。
- 重点是系统、服务、部署、数据流：优先 `html-architecture-diagrams`。
- 重点是数据库表、模型、ER 关系：优先 `html-erd-explorer`。
- 重点是通用箭头、流程、状态、时序：优先 `html-svg-diagrams`。
- 重点是时间轴、里程碑、依赖排期：优先 `html-timeline-roadmap`。
- 重点是可筛选数据：优先 `html-data-explorer`。
- 重点是让用户编辑并回传结构：优先 `html-throwaway-editor`、`html-mind-map` 或 `html-interactive-playground`。

## 本地输出约束

- 默认生成单文件 `.html`，可直接在浏览器打开。
- CSS/JS 内联；除非用户明确要求，不依赖外部 CDN。
- 互动结果使用 `submit-handler.js` 的剪贴板路径；不要启动或引用 Claude Code 专属监听器。
- 文本、按钮、图形节点必须响应式且不溢出。
- 涉及当前工作区知识沉淀时，HTML 只是表现形式，仍必须遵守 output 和记忆规则。
