# 当前项目使用 OMM Skill 示例

> 回答问题：以当前项目为例，D01/D02/D03 这三个 OMM skill 怎么用？

---

## 当前项目适合怎么扫

当前项目是一个“工作区治理 + Skill 管理 + DWD 开发链路”的本地工作区，根目录里有这些关键层：

- `.agents/skills/`：18 个项目级 skill，包括 A/B/C/D 四个域
- `.agents/rules/`：对话归属、命名、记忆、备份等执行规则
- `.system/standards/`：工作区标准 SSOT
- `.memory/`：对话记录、系统记录、知识提炼、全局知识地图
- `output/`：所有知识产出与子项目
- `.claude/commands/`：Claude 斜杠命令入口
- `AGENTS.md`、`CLAUDE.md`：Codex / Claude 的薄入口

所以 D01 扫描时，不应该把它当成普通代码库只画“src 到 dist”的图，而应该重点画“治理链路”和“Skill 调用链路”。

---

## 使用前置条件

当前环境检查结果：`omm` CLI 尚未安装。

因此第一次使用前需要先安装：

```powershell
npm install -g oh-my-mermaid
```

安装后验证：

```powershell
omm --version
```

如果希望 `.omm/` 字段内容使用中文，应先确认 OMM 的语言配置。D01 原始流程会读取：

```powershell
omm config language
```

---

## 第一步：用 D01 生成当前项目架构文档

可以这样对 AI 下达任务：

```text
执行 D01_OMM架构扫描，扫描当前工作区架构。
重点覆盖：工作区骨架、Skill 管理体系、强制门流程、记忆系统、DWD 开发链路、Claude/Codex 接入层。
```

或简短一点：

```text
omm scan 当前项目，生成 .omm 架构图。
```

D01 应该做的事：

1. 检查 `omm` CLI 是否可用
2. 阅读根目录、`.agents/skills/`、`.agents/rules/`、`.system/standards/`、`.memory/`、`output/`
3. 选择适合当前项目的架构视角
4. 用 `omm write` 写入 `.omm/` 架构文档
5. 汇总生成了哪些视角，并建议用 D02 查看

当前项目建议生成这些视角：

| 视角 | 说明 |
|------|------|
| `overall-architecture` | 总览工作区各层：入口、规则、skill、标准、记忆、输出 |
| `skill-management-flow` | A01/A02、Skills 管理标准、注册表、`.claude/commands` 如何协同 |
| `governance-gates` | B01/B02/B03/B04 等强制门的执行顺序 |
| `memory-flow` | 对话记录、系统记录、知识提炼、全局知识地图如何写入 |
| `dwd-development-flow` | C03/C05/C06/C07 如何支撑 ODS 到 DWD 的开发产物 |
| `agent-entrypoints` | `AGENTS.md`、`CLAUDE.md`、`.claude/commands` 如何接入 |

D01 的产物不是普通 Markdown，而是 `.omm/` 目录下的一组结构化字段和 Mermaid 图。

---

## 第二步：用 D02 本地查看架构图

当 D01 已经生成 `.omm/` 后，可以这样说：

```text
执行 D02_OMM架构查看，打开当前项目的架构查看器，端口用 3010。
```

或：

```text
omm view --port 3010
```

D02 应该做的事：

1. 运行 `omm list`，确认 `.omm/` 中有内容
2. 有内容时运行 `omm view --port 3010`
3. 返回本地地址，例如 `http://localhost:3010`

如果还没有 `.omm/`，D02 不应该启动空查看器，而应该提示先执行 D01。

---

## 第三步：用 D03 推送到云端

只有当你明确要把架构图分享给别人，才使用 D03。

可以这样说：

```text
执行 D03_OMM云端推送，把当前项目的 .omm 架构文档推送到云端。
```

D03 应该做的事：

1. 运行 `omm share` 检查是否登录
2. 未登录时引导 `omm login`
3. 没有关联项目时运行 `omm link`
4. 状态就绪后运行 `omm push`
5. 返回云端查看地址

注意：D03 会涉及登录、OAuth、网络和云端上传，不能在用户只是想“看本地架构图”时自动执行。

---

## 当前项目的一条完整示例链路

最自然的一条链路是：

```text
1. 执行 D01，扫描当前工作区，生成 .omm 架构图。
2. 执行 D02，用 3010 端口打开本地查看器。
3. 如果图谱确认没问题，再执行 D03 推送到云端分享。
```

对应到当前项目：

- D01 会把 `.agents/skills`、`.system/standards`、`.memory`、`output` 等画成架构关系
- D02 会让你在浏览器里点开这些视角和子节点
- D03 会把这套图谱发布到 oh-my-mermaid 云端

---

## 不同需求该怎么说

| 你想要 | 可以这样说 |
|--------|------------|
| 生成架构图 | `执行 D01，扫描当前项目架构，重点看 Skill 管理体系。` |
| 只更新某一块 | `执行 D01，只刷新 Skill 管理和记忆系统相关的 .omm 图谱。` |
| 本地打开查看 | `执行 D02，端口 3010。` |
| 上传分享 | `执行 D03，推送当前项目 .omm 到云端。` |
| 先别联网 | `只执行 D01 和 D02，不执行 D03。` |

---

## 最重要的边界

- D01 是“生成/更新文档”，会写 `.omm/`
- D02 是“本地查看”，不改 `.omm/`
- D03 是“云端发布”，会联网和上传

对当前项目来说，建议先用 D01 生成“治理链路图”，再用 D02 本地检查；D03 放到图谱确认可公开之后再用。
