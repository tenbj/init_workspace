---
name: J01_HyperFrames视频制作
description: 当用户需要用 HyperFrames 制作、编辑、复刻网页动效视频、产品演示片或动态字幕时使用；按需桥接上游完整技能包完成工程创建、质检预览与 MP4 渲染。
---

# J01_HyperFrames视频制作

## 这项技能解决什么问题

- 将外部 `heygen-com/hyperframes` 的 9 个官方 Skill（343 文件 / 122 脚本）收敛为工作区内的 **1 个中文薄桥接入口**，在不膨胀核心骨架的前提下 100% 发挥上游原生能力。
- 面向产品发布片、数据可视化动画、代码/PR 演示、口播动态字幕、参考视频复刻（reverse）等场景，串联剧本、HTML 动效、素材/音频、抽帧质检与确定性 MP4 渲染。
- 在上游能力外层叠加本工作区的子项目归属、省钱红线、Windows 与中文处理避坑约束。

## 先读哪些本地知识

- 先读 `references/子技能路由表.md`：定位本机上游完整 `skills/` 目录与 `plugin-cli.mjs`，按场景只展开必需的 1~2 个上游子 Skill。
- 执行任何命令或素材生成前，先读 `references/工作区适配与避坑守则.md`（子项目落点、免费优先红线、Windows/中文避坑、遥测边界）。
- 需要确认交付物清单与验收标准时，读 `references/输出契约.md`。

## 固定动作

1. **归属与建项**：先按 `B04` 确认目标子项目，在 `output/<子项目>/03_代码程序/<纯英文工程名>/` 下初始化或定位 HyperFrames 工程；同步按 `B08` 记录任务进度。
2. **定位上游包并校验环境**：按 `references/子技能路由表.md` 解析上游 `skills/` 根目录；核查本机 Node（`>=22`）、FFmpeg（或 `--docker`）与无头 Chrome（`browser ensure`）。
3. **按需加载上游子 Skill**：先读上游 `hyperframes/SKILL.md` 遵循渲染契约，再按本轮任务需要只读对应子 Skill（如 `hyperframes-cli`、`hyperframes-registry`、`media-use`、`reverse-any-video` 等），不一次性全量展开 9 个 Skill。
4. **编剧→构建→质检闭环**：长片（>15s）先出 3 套故事线经用户确认后再写 `SPEC.md` 与 HTML；改动后依次跑 `lint` → `check --json` → `snapshot` 看图验收 → `preview` 给用户确认。
5. **渲染与收尾**：用户确认后执行 `render` 导出 MP4 并校验非空与时长；按 `references/输出契约.md` 交付路径，最后按 `B03` 沉淀记忆并关闭 `B08`。

## 什么时候再读本 skill 的 references

- 定位上游 `skills/` 路径、选择具体子 Skill 或升级上游包时，读 `references/子技能路由表.md`。
- 处理费用边界、PowerShell JSON 传参、中文语音转写、Windows 本地模型差异或关闭遥测时，读 `references/工作区适配与避坑守则.md`。
- 核对最终件/中间件/日志要求或维护本 Skill 的 11 段结构落点时，读 `references/输出契约.md` 与 `references/结构融合索引.md`。

## 边界

- **方案 A 桥接定位**：不把 3.79 MB 上游第三方文件拷入本 Skill，不改写上游 122 个脚本内部相对路径；上游包缺失时报错指引补齐，不凭空手造缩水替代品。
- **费用红线**：默认优先纯免费本地与免费登录资源；任何触发 HeyGen 付费积分、外部付费 API 或云端渲染计费的操作前，必须先明确告知并获用户同意。
- **不越界触发**：普通静态网页报告/图示走 `G01`~`G03`，架构图走 `D04`，交互原型走 `H01`，纯模板化一键口播批产可转评 MoneyPrinterTurbo，不强行用本 Skill 替代。
- **不留噪音与密钥**：不生成 README/CHANGELOG 等噪音文件，不把 API Key 或登录态写入 Skill 文档或 Git 跟踪文件（凭据统一走 `B12`）。
