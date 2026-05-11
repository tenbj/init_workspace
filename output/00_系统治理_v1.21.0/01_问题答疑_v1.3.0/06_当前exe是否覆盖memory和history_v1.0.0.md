# 当前 exe 是否覆盖 memory 和 history

> 调查对象：`output/00_系统治理_v1.18.0/03_代码程序_v2.10.0/dist/初始化工作区_v2.10.0.exe`
> 源码依据：`output/00_系统治理_v1.18.0/03_代码程序_v2.10.0/src/init_workspace.py`
> 构建依据：`output/00_系统治理_v1.18.0/03_代码程序_v2.10.0/src/build.ps1`
> 调查时间：2026-05-12

---

## 结论

当前 `初始化工作区_v2.10.0.exe` 不会整体覆盖 `.memory/`，也不会整体覆盖 `.history/`。

更准确地说：

| 路径 | 当前 exe 行为 | 是否覆盖已有内容 |
|------|---------------|------------------|
| `.memory/对话记录/` | 确保目录存在 | 否 |
| `.memory/知识提炼/` | 确保目录存在 | 否 |
| `.memory/系统记录/` | 确保目录存在；缺少固定系统记录文件时才创建 | 否 |
| `.memory/全局知识地图.md` | 文件不存在时写入初始模板 | 否，存在则跳过 |
| `.memory/对话记录/00_系统治理_v1.0.0.md` | 仅在不存在 `output/00_系统治理_v*` 时创建核心子项目，并补建初始对话记录 | 否，已有核心子项目则跳过 |
| `.history/` | 确保历史目录结构存在；升级时向其中追加受管资产备份 | 否，不删除、不整体替换 |

需要注意的是：`.history/` 会新增备份文件或快照。这不是覆盖，而是升级前留痕。

---

## 源码证据

### 1. `.memory` 使用补缺逻辑

源码中 `write_if_missing(path, content)` 的判断是：

```python
if not path.exists():
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")
```

因此 `.memory/全局知识地图.md` 和 `.memory/系统记录/*.md` 只有在目标文件不存在时才写入。已有文件不会被改写。

在主初始化流程中，`.memory` 相关代码明确标注为：

```python
# 4. 初始化 .memory 文件（仅当文件不存在时写入）
```

对应写入对象只有：

- `.memory/全局知识地图.md`
- `.memory/系统记录/规则变更记录.md`
- `.memory/系统记录/技能变更记录.md`
- `.memory/系统记录/脚本治理记录.md`
- `.memory/系统记录/教训库.md`
- `.memory/系统记录/索引.md`

### 2. `.history` 使用建目录和追加备份逻辑

主流程中的 `skeleton_dirs` 会确保这些目录存在：

- `.history/output`
- `.history/AGENTS`
- `.history/CLAUDE`
- `.history/.agents/rules`
- `.history/.agents/skills`
- `.history/.claude`
- `.history/.claude/commands`
- `.history/.memory/对话记录`
- `.history/.memory/系统记录`
- `.history/.memory/知识提炼`
- `.history/.memory/全局知识地图`
- `.history/.system`
- `.history/.system/standards`

目录创建调用的是：

```python
path.mkdir(parents=True, exist_ok=True)
```

这意味着目录已存在时不会清空。

升级时，exe 会把受管资产备份进 `.history/`，例如：

- `.agents/rules/*.md` 覆盖前备份到 `.history/.agents/rules/`
- `.agents/skills/*/` 替换前备份到 `.history/.agents/skills/`
- `.system/standards/*` 覆盖前备份到 `.history/.system/standards/`
- `AGENTS.md` 覆盖前备份到 `.history/AGENTS/`
- `CLAUDE.md` 覆盖前备份到 `.history/CLAUDE/`
- `.claude/commands/*.md` 重写前备份到 `.history/.claude/commands/`

备份文件名使用时间戳，并通过 `unique_path()` 避免同名覆盖。

---

## 真正会覆盖的范围

当前 exe 的覆盖范围不是 `.memory` / `.history`，而是受管骨架资产：

| 资产 | 行为 |
|------|------|
| `.agents/rules/*.md` | 先备份，再用内置模板覆盖 |
| `.agents/skills/*/` | 先备份旧文件夹，再删除 live 文件夹并复制内置模板 |
| `.system/standards/*` | 先备份，再用内置模板覆盖 |
| `AGENTS.md` | 先备份，再用内置模板覆盖 |
| `CLAUDE.md` | 先备份，再用内置模板覆盖 |
| `.claude/commands/*.md` | 先备份，再按当前 Skill 列表重写 |

此外，`.Claude.json` 和 `.claude/settings.local.json` 走 `write_if_missing()`，属于私有配置补缺，不覆盖已有真实配置。

---

## 回答用户问题

如果你问的是“运行当前 exe 会不会把我现有 `.memory` 和 `.history` 清掉或重写”，答案是：不会。

如果你问的是“运行当前 exe 会不会碰到 `.memory` 和 `.history`”，答案是：会碰到，但方式不同：

- `.memory`：只补缺目录和缺失的初始文件。
- `.history`：只补缺目录，并把被覆盖的受管骨架资产追加备份进去。

所以它的风险点不在 `.memory` / `.history` 被覆盖，而在 `.agents`、`.system`、入口文件和 Claude 命令这些受管骨架资产会被当前 exe 模板替换。
