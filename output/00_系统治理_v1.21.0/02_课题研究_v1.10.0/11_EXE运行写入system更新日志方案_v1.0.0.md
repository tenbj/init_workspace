# EXE 运行写入 .system 更新日志方案

> 主题：每次运行初始化工具 EXE，都在 `.history/.system/更新日志.md` 记录本次是初始化还是升级。
> 对象：`output/00_系统治理_v1.19.0/03_代码程序_v2.10.0/src/init_workspace.py`
> 日期：2026-05-12

---

## 结论

建议在 `init_workspace.py` 中新增“运行事件日志”能力：每次 EXE 运行结束时，向 `.history/.system/更新日志.md` 追加一条 `init_workspace_run_{yyyyMMddHHmmss}` 记录，明确本次是 `初始化` 还是 `升级`，并记录工具版本、工作区路径、覆盖/补缺/备份统计和执行结果。

这条记录不要伪装成 `.system/standards_{timestamp}` 快照记录，而应作为同一个更新日志文件里的另一类事件。这样既保留现有 B02 的 `.system` 快照日志语义，也能覆盖 EXE 运行这种“骨架级操作”。

---

## 为什么要这么做

当前 `.history/.system/更新日志.md` 主要记录 B02 对 `.system/standards/` 做 FOLDER 快照的历史，标题形如：

```text
## standards_20260512010651
```

但 EXE 运行有两个特点：

1. 它可能是第一次初始化：没有旧 `.system/standards/` 可备份，但仍然是一次重要系统事件。
2. 它可能是升级：会覆盖 `.system/standards/*`、`.agents/*`、入口文件和 Claude 命令，但当前没有一条总览记录说明“这次运行是升级”。

所以要补的是“运行事件”，不是单纯再补一个标准文件快照。

---

## 判断初始化还是升级

建议新增函数：

```python
def detect_operation_type(workspace: Path) -> str:
    markers = [
        workspace / ".agents",
        workspace / ".system" / "standards" / "workspace-spec.json",
        workspace / "AGENTS.md",
        workspace / "CLAUDE.md",
        workspace / "output",
    ]
    return "升级" if any(p.exists() for p in markers) else "初始化"
```

判断要在创建目录之前完成，否则新建目录后就无法区分。

当前 `main()` 已经用 `.agents` 是否存在内容来决定是否弹出“继续升级”确认框。这个判断可以继续保留，但运行日志建议使用上面的更宽标记，因为有些旧工作区可能缺 `.agents`，却已经有 `.system`、入口文件或 `output`。

---

## 日志条目格式

建议追加如下 Markdown：

```markdown
## init_workspace_run_20260512023015

- 运行时间：2026-05-12 02:30:15
- 操作类型：升级
- 工具版本：v2.11.0
- 工作区路径：`E:\...\工作区工作测试`
- 模板来源：EXE 内置模板
- 执行结果：完成

| 项目 | 数量/结果 |
|------|-----------|
| Rule 覆盖 | 4 |
| Skill 覆盖 | 25 |
| Rule 备份 | 4 |
| Skill 备份 | 25 |
| Standard 备份 | 4 |
| Codex 入口备份 | 1 |
| Claude 接入层备份 | 26 |
| Claude 命令生成 | 25 |
| `.memory` 处理 | 只补缺 |
| `input/output/.temp` 处理 | 只补缺 |

---
```

初始化场景中，`操作类型` 写 `初始化`，备份数量通常为 0。

升级场景中，`操作类型` 写 `升级`，备份数量反映本轮实际覆盖前留痕数量。

---

## 代码改造点

### 1. 在 `main()` 中提前判断操作类型

```python
def main():
    workspace = get_workspace_root()
    templates = get_templates_dir()
    operation_type = detect_operation_type(workspace)
```

这个判断必须放在 `initialize_workspace()` 之前。

### 2. 将操作类型传入初始化主流程

```python
stats = initialize_workspace(workspace, templates, operation_type)
show_result_dialog(workspace, stats)
```

并调整签名：

```python
def initialize_workspace(workspace: Path, templates: Path, operation_type: str) -> dict:
```

在 `stats` 中保留：

```python
"operation_type": operation_type,
"run_logged": False,
```

### 3. 新增日志追加函数

```python
def append_system_run_log(workspace: Path, ts: str, stats: dict):
    log_path = workspace / ".history" / ".system" / "更新日志.md"
    ensure_dir(log_path.parent)

    if not log_path.exists():
        log_path.write_text(
            "# .system 更新日志\n\n"
            "> 记录 `.system` 快照与初始化工具运行事件。\n\n"
            "---\n",
            encoding="utf-8",
        )

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result = "有警告" if stats.get("errors") else "完成"
    entry = f"""

## init_workspace_run_{ts}

- 运行时间：{now}
- 操作类型：{stats["operation_type"]}
- 工具版本：v{SKELETON_VERSION}
- 工作区路径：`{workspace}`
- 模板来源：EXE 内置模板
- 执行结果：{result}

| 项目 | 数量/结果 |
|------|-----------|
| Rule 覆盖 | {stats["rules"]} |
| Skill 覆盖 | {len(stats["skills"])} |
| Rule 备份 | {stats["rule_backups"]} |
| Skill 备份 | {stats["skill_backups"]} |
| Standard 备份 | {stats["standards_backups"]} |
| Codex 入口备份 | {stats["codex_backups"]} |
| Claude 接入层备份 | {stats["claude_backups"]} |
| Claude 命令生成 | {stats["claude_commands"]} |
| `.memory` 处理 | 只补缺 |
| `input/output/.temp` 处理 | 只补缺 |

---
"""
    with log_path.open("a", encoding="utf-8") as f:
        f.write(entry)
    stats["run_logged"] = True
```

### 4. 在初始化流程末尾调用

建议放在 `_init_core_subproject(workspace)` 之后、`return stats` 之前：

```python
append_system_run_log(workspace, ts, stats)
```

这样统计数据已经完整，日志能反映本轮真实备份和生成数量。

### 5. 弹窗提示中显示日志状态

可在结果弹窗里增加：

```text
· .system 更新日志：已追加本次初始化/升级记录
```

这能让用户知道本次操作已留痕。

---

## 是否需要改 B01

建议轻微调整 B01，而不是大改。

现有 B01 已检查 `.history/.system/{文件夹}_{时间戳}` 快照是否被 `.history/.system/更新日志.md` 覆盖。新增 `init_workspace_run_*` 条目后，B01 不应把它当作快照条目要求存在同名文件夹。

因此 B01 的校验口径应是：

- `standards_yyyyMMddHHmmss` 这类快照条目继续按现有规则检查。
- `init_workspace_run_yyyyMMddHHmmss` 这类运行事件只检查格式完整，不要求有对应快照目录。

最低限度可以先不新增 B01 检查，只要现有快照覆盖检查不会误判 `init_workspace_run_*` 即可。

---

## 版本建议

这是初始化工具行为增强，建议：

- `SKELETON_VERSION`：`2.10.0 -> 2.11.0`
- `build.ps1` 的 `$Version` 同步改为 `2.11.0`
- 重建 `dist/初始化工作区_v2.11.0.exe`
- 系统治理 `03_代码程序` 文件夹版本同步到 `v2.11.0`

---

## 验收口径

1. 在空目录运行新 EXE：
   - `.history/.system/更新日志.md` 存在。
   - 包含 `操作类型：初始化`。
   - 备份数量基本为 0。

2. 在已有工作区运行新 EXE：
   - `.history/.system/更新日志.md` 追加新条目。
   - 包含 `操作类型：升级`。
   - 能看到 Rule、Skill、Standard、入口文件、Claude 命令等备份统计。

3. B01 体检：
   - 原有 `.system` 快照覆盖检查继续通过。
   - `init_workspace_run_*` 不被误判为缺失快照目录。

4. 用户可读性：
   - 打开 `.history/.system/更新日志.md`，能直接看出每次 EXE 运行是初始化还是升级。

---

## 最小实现顺序

1. 修改 `init_workspace.py`：新增 `detect_operation_type()` 和 `append_system_run_log()`。
2. 调整 `initialize_workspace()` 签名与 `main()` 调用链。
3. 弹窗补充“已写入 .system 更新日志”。
4. 如 B01 对新增标题误判，再补 B01 规则。
5. 升级版本号并重建 EXE。
