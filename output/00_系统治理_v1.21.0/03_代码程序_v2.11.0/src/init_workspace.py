"""
初始化工作区.py
──────────────────────────────────────────────────────────────────────
将本脚本（或由其编译出的 EXE）放到任意目录，双击运行后，
会在该目录下自动创建完整的「知识研究工作区」骨架：
  .agents/rules/       ← 4 条 Rule 文件
  .agents/skills/      ← 23 个 Skill 完整文件夹
  AGENTS.md            ← Codex 会话入口规则
  CLAUDE.md            ← Claude Code 会话入口规则
  .claude/commands/    ← Claude 斜杠命令
  .memory/            ← 初始化记忆目录
  .history/           ← 历史归档目录（空）
  .temp/              ← 临时文件与规范化异常归档目录
  input/
  output/

如果目标目录已是旧工作区，会先把受管 Rules/Skills 备份到 .history，
再用 EXE 内置模板替换对应骨架资产；memory、temp、input、output 只补缺。

完成后弹出提示窗口，告知初始化结果。
"""

import os
import sys
import shutil
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
from pathlib import Path

SKELETON_VERSION = "2.11.0"
SSO_SPEC_VERSION = "1.14.0"

SYSTEM_RECORD_FILES = {
    "规则变更记录.md": "规则变更记录",
    "技能变更记录.md": "技能变更记录",
    "脚本治理记录.md": "脚本治理记录",
    "教训库.md": "教训库",
    "索引.md": "系统记录索引",
}

CLAUDE_COMMAND_TEMPLATE = "请读取并执行 .agents/skills/{skill}/SKILL.md\n"


# ──────────────────────────────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────────────────────────────

def get_templates_dir() -> Path:
    """
    PyInstaller 打包后，附加数据会解压到 sys._MEIPASS；
    开发调试时，templates/ 就在脚本同级目录。
    """
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent
    return base / "templates"


def get_workspace_root() -> Path:
    """EXE 所在目录即目标工作区根目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    i = 2
    while True:
        candidate = parent / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def copy_tree_no_pycache(src: Path, dst: Path):
    """递归复制目录，自动跳过 __pycache__。"""
    ensure_dir(dst)
    for item in src.iterdir():
        if item.name == "__pycache__":
            continue
        target = dst / item.name
        if item.is_dir():
            copy_tree_no_pycache(item, target)
        else:
            shutil.copy2(item, target)


def backup_existing_file(src: Path, history_dir: Path, ts: str) -> Path | None:
    if not src.exists():
        return None
    ensure_dir(history_dir)
    backup = unique_path(history_dir / f"{src.stem}_{ts}{src.suffix}")
    shutil.copy2(src, backup)
    return backup


def backup_existing_dir(src: Path, history_dir: Path, ts: str) -> Path | None:
    if not src.exists():
        return None
    ensure_dir(history_dir)
    backup = unique_path(history_dir / f"{src.name}_{ts}")
    shutil.copytree(src, backup, ignore=shutil.ignore_patterns("__pycache__"))
    return backup


def replace_managed_skill(src: Path, dst: Path, history_dir: Path, ts: str) -> Path | None:
    backup = backup_existing_dir(dst, history_dir, ts)
    if dst.exists():
        shutil.rmtree(dst)
    copy_tree_no_pycache(src, dst)
    return backup


# ──────────────────────────────────────────────────────────────────────
# 初始化记忆文件内容
# ──────────────────────────────────────────────────────────────────────

def memory_global_map_content() -> str:
    return """\
<!-- memory-version: 1.0.0 -->
# 全局知识地图

> 所有研究子项目的总索引，新建子项目时自动更新。

| 话题 | 子项目文件夹 | 创建时间 | 状态 | 核心结论（一句话） |
|------|------------|---------|------|----------------|
"""


def memory_system_record_content() -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""\
# 系统记录 · 初始化记录

> 记录工作区初始化与骨架升级事件，按时间追加。

---

## {now}

**用户操作**：运行「初始化工作区」工具
**工具做了**：创建或升级工作区骨架，版本 v{SKELETON_VERSION}

---
"""


def named_system_record_content(title: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""\
# 系统记录 · {title}

> 按时间追加记录。

---

## {now}

**用户操作**：运行「初始化工作区」工具
**工具做了**：补建系统记录文件，骨架版本 v{SKELETON_VERSION}

---
"""


def write_if_missing(path: Path, content: str):
    if not path.exists():
        ensure_dir(path.parent)
        path.write_text(content, encoding="utf-8")


def detect_operation_type(workspace: Path) -> str:
    """在创建任何目录之前判断本次是初始化还是升级。"""
    markers = [
        workspace / ".agents",
        workspace / ".system" / "standards" / "workspace-spec.json",
        workspace / "AGENTS.md",
        workspace / "CLAUDE.md",
        workspace / "output",
    ]
    return "升级" if any(marker.exists() for marker in markers) else "初始化"


# ──────────────────────────────────────────────────────────────────────
# .system/standards 初始化（SSOT 标准文件）
# ──────────────────────────────────────────────────────────────────────

def _system_spec_placeholder() -> str:
    return f"""\
{{
  "$schema": "workspace-spec/{SSO_SPEC_VERSION}",
  "version": "{SSO_SPEC_VERSION}",
  "description": "工作区骨架规格 — 单一事实源（SSOT）。由 init_workspace v{SKELETON_VERSION} 初始化占位。请从官方模板获取完整内容。"
}}
"""


def _system_skeleton_md_placeholder() -> str:
    return f"""\
# 工作区骨架规格

> 版本：{SSO_SPEC_VERSION}
> 由 init_workspace v{SKELETON_VERSION} 初始化占位。请从官方模板获取完整内容。
"""


def _system_naming_md_placeholder() -> str:
    return f"""\
# 工作区命名规范

> 版本：{SSO_SPEC_VERSION}
> 由 init_workspace v{SKELETON_VERSION} 初始化占位。请从官方模板获取完整内容。
"""


def _init_system_standards(workspace: Path, templates: Path, ts: str, stats: dict):
    """初始化 .system/standards/ 下标准文件（覆盖层：备份旧版，强制替换为模板新版）。"""
    std_dir = workspace / ".system" / "standards"
    ensure_dir(std_dir)

    history_dir = workspace / ".history" / ".system" / "standards"
    standard_files = [
        "workspace-spec.json",
        "工作区骨架规格.md",
        "工作区命名规范.md",
        "Skills管理标准.md",
    ]

    standards_template = templates / "system" / "standards"
    if standards_template.exists():
        for name in standard_files:
            src = standards_template / name
            dst = std_dir / name
            if not src.exists():
                continue
            backup = backup_existing_file(dst, history_dir, ts)
            if backup:
                stats["standards_backups"] += 1
            shutil.copy2(src, dst)
        return

    for name in standard_files:
        dst = std_dir / name
        backup = backup_existing_file(dst, history_dir, ts)
        if backup:
            stats["standards_backups"] += 1
    write_if_missing(std_dir / "workspace-spec.json", _system_spec_placeholder())
    write_if_missing(std_dir / "工作区骨架规格.md", _system_skeleton_md_placeholder())
    write_if_missing(std_dir / "工作区命名规范.md", _system_naming_md_placeholder())


# ──────────────────────────────────────────────────────────────────────
# AI 接入层初始化
# ──────────────────────────────────────────────────────────────────────

def _claude_env_placeholder() -> str:
    return """\
{
  "env": {},
  "hasCompletedOnboarding": true
}
"""


def _claude_settings_placeholder() -> str:
    return """\
{
  "permissions": {
    "allow": []
  }
}
"""


def _init_ai_entrypoints(workspace: Path, templates: Path, ts: str, stats: dict):
    """初始化 Codex / Claude 接入层。私有配置只补缺，不覆盖真实值。"""
    agents_history = workspace / ".history" / "AGENTS"
    agents_src = templates / "AGENTS.md"
    agents_dst = workspace / "AGENTS.md"
    if agents_src.exists():
        backup = backup_existing_file(agents_dst, agents_history, ts)
        if backup:
            stats["codex_backups"] += 1
        shutil.copy2(agents_src, agents_dst)
    else:
        write_if_missing(
            agents_dst,
            "# AGENTS.md - Codex 工作区入口\n\n> 由初始化工具补缺。请从官方模板获取完整内容。\n",
        )

    claude_dir = workspace / ".claude"
    commands_dir = claude_dir / "commands"
    ensure_dir(commands_dir)
    ensure_dir(workspace / ".history" / ".claude" / "commands")

    history_claude = workspace / ".history" / "CLAUDE"
    guide_src = templates / "CLAUDE.md"
    guide_dst = workspace / "CLAUDE.md"
    if guide_src.exists():
        backup = backup_existing_file(guide_dst, history_claude, ts)
        if backup:
            stats["claude_backups"] += 1
        shutil.copy2(guide_src, guide_dst)
    else:
        write_if_missing(
            guide_dst,
            "# CLAUDE.md — AI 操作规则\n\n> 由初始化工具补缺。请从官方模板获取完整内容。\n",
        )

    local_config_template = templates / ".Claude.json"
    settings_template = templates / ".claude" / "settings.local.json"
    local_config_content = (
        local_config_template.read_text(encoding="utf-8")
        if local_config_template.exists()
        else _claude_env_placeholder()
    )
    settings_content = (
        settings_template.read_text(encoding="utf-8")
        if settings_template.exists()
        else _claude_settings_placeholder()
    )
    write_if_missing(workspace / ".Claude.json", local_config_content)
    write_if_missing(claude_dir / "settings.local.json", settings_content)

    skills_dir = workspace / ".agents" / "skills"
    if not skills_dir.exists():
        return
    for skill_dir in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        if not (skill_dir / "SKILL.md").exists():
            continue
        command_path = commands_dir / f"{skill_dir.name}.md"
        backup = backup_existing_file(
            command_path,
            workspace / ".history" / ".claude" / "commands",
            ts,
        )
        if backup:
            stats["claude_backups"] += 1
        command_path.write_text(
            CLAUDE_COMMAND_TEMPLATE.format(skill=skill_dir.name),
            encoding="utf-8",
        )
        stats["claude_commands"] += 1


# ──────────────────────────────────────────────────────────────────────
# 核心骨架子项目 00_系统治理 初始化
# ──────────────────────────────────────────────────────────────────────

def _core_catalog_content() -> str:
    return """\
# 目录 · 系统治理

> 核心骨架子项目，用于记录工作区治理决策、规则变更、Skill 升级等系统性内容。

---

## 01_问题答疑

| # | 文件 | 说明 | 首次落盘 | 最近更新 |
|---|------|------|---------|---------|

## 02_课题研究

| # | 文件 | 说明 | 首次落盘 | 最近更新 |
|---|------|------|---------|---------|

## 03_代码程序

| # | 文件 | 说明 | 首次落盘 | 最近更新 |
|---|------|------|---------|---------|
"""


def _core_version_record_content() -> str:
    now = datetime.now().strftime("%Y-%m-%d")
    return f"""\
# 版本记录 · 系统治理

> 核心骨架子项目的版本变更历史。

---

## v1.0.0 ({now})

**变更类型**：MAJOR
**变更描述**：由 init_workspace v{SKELETON_VERSION} 自动创建核心骨架子项目。

---
"""


def _core_conv_record_content() -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""\
# 对话记录 · 系统治理

> 记录本话题所有对话的关键摘要，按时间追加。

---

## {now}

**用户问**：运行「初始化工作区」工具
**AI做了**：自动创建核心骨架子项目 00_系统治理_v1.0.0，骨架版本 v{SKELETON_VERSION}

---
"""


def _init_core_subproject(workspace: Path):
    """创建核心骨架子项目 output/00_系统治理_v1.0.0（仅当不存在时）。"""
    import glob
    output_dir = workspace / "output"
    # 检查是否已存在 00_系统治理_v* 子项目
    existing = list(output_dir.glob("00_系统治理_v*"))
    if existing:
        return  # 已存在，跳过

    core_dir = output_dir / "00_系统治理_v1.0.0"
    ensure_dir(core_dir / "01_问题答疑_v0.0.0")
    ensure_dir(core_dir / "02_课题研究_v0.0.0")
    ensure_dir(core_dir / "03_代码程序_v0.0.0")
    write_if_missing(core_dir / "目录.md", _core_catalog_content())
    write_if_missing(core_dir / "版本记录.md", _core_version_record_content())
    # 对话记录
    conv_record = workspace / ".memory" / "对话记录" / "00_系统治理_v1.0.0.md"
    write_if_missing(conv_record, _core_conv_record_content())


# ──────────────────────────────────────────────────────────────────────
# .system 更新日志：EXE 运行事件
# ──────────────────────────────────────────────────────────────────────

def _system_update_log_header() -> str:
    return """\
# .system 更新日志

> 记录 `.system` 快照与初始化工具运行事件。

---
"""


def append_system_run_log(workspace: Path, templates: Path, ts: str, stats: dict):
    """每次运行初始化工具后追加一条初始化/升级事件记录。"""
    log_path = workspace / ".history" / ".system" / "更新日志.md"
    ensure_dir(log_path.parent)
    if not log_path.exists():
        log_path.write_text(_system_update_log_header(), encoding="utf-8")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result = "有警告" if stats["errors"] else "完成"
    template_source = "EXE 内置模板" if getattr(sys, "frozen", False) else f"源码模板：`{templates}`"
    warnings = "\n".join(f"- {item}" for item in stats["errors"]) if stats["errors"] else "- 无"

    entry = f"""

## init_workspace_run_{ts}

- 运行时间：{now}
- 操作类型：{stats["operation_type"]}
- 工具版本：v{SKELETON_VERSION}
- 工作区路径：`{workspace}`
- 模板来源：{template_source}
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

**警告信息**：
{warnings}

---
"""
    with log_path.open("a", encoding="utf-8") as f:
        f.write(entry)
    stats["run_logged"] = True


# ──────────────────────────────────────────────────────────────────────
# 主初始化逻辑
# ──────────────────────────────────────────────────────────────────────


def initialize_workspace(workspace: Path, templates: Path, operation_type: str) -> dict:
    """
    在 workspace 下创建完整骨架。
    返回统计信息字典，用于弹窗展示。
    """
    stats = {
        "rules": 0,
        "skills": [],
        "rule_backups": 0,
        "skill_backups": 0,
        "standards_backups": 0,
        "claude_commands": 0,
        "codex_backups": 0,
        "claude_backups": 0,
        "operation_type": operation_type,
        "run_logged": False,
        "errors": [],
    }
    ts = datetime.now().strftime("%Y%m%d%H%M%S")

    # 1. 必须创建的空目录（对应 workspace-spec.json v1.11.0 requiredLayer.directories）
    skeleton_dirs = [
        ".agents/rules",
        ".agents/skills",
        ".claude/commands",
        ".history/output",
        ".history/AGENTS",
        ".history/CLAUDE",
        ".history/.agents/rules",
        ".history/.agents/skills",
        ".history/.claude",
        ".history/.claude/commands",
        ".history/.memory/对话记录",
        ".history/.memory/系统记录",
        ".history/.memory/知识提炼",
        ".history/.memory/全局知识地图",
        ".history/.system",
        ".history/.system/standards",
        ".memory/对话记录",
        ".memory/知识提炼",
        ".memory/系统记录",
        ".system/standards",
        ".temp",
        "input",
        "output",
    ]
    for d in skeleton_dirs:
        ensure_dir(workspace / d)

    # 2. 复制 rules
    rules_src = templates / "rules"
    rules_dst = workspace / ".agents" / "rules"
    if rules_src.exists():
        for f in rules_src.iterdir():
            if f.is_file():
                backup = backup_existing_file(
                    rules_dst / f.name,
                    workspace / ".history" / ".agents" / "rules",
                    ts,
                )
                if backup:
                    stats["rule_backups"] += 1
                shutil.copy2(f, rules_dst / f.name)
                stats["rules"] += 1
    else:
        stats["errors"].append("模板 rules/ 目录不存在")

    # 3. 复制 skills
    skills_src = templates / "skills"
    skills_dst = workspace / ".agents" / "skills"
    if skills_src.exists():
        for skill_dir in sorted(skills_src.iterdir()):
            if skill_dir.is_dir():
                backup = replace_managed_skill(
                    skill_dir,
                    skills_dst / skill_dir.name,
                    workspace / ".history" / ".agents" / "skills",
                    ts,
                )
                if backup:
                    stats["skill_backups"] += 1
                stats["skills"].append(skill_dir.name)
    else:
        stats["errors"].append("模板 skills/ 目录不存在")

    # 4. 初始化 .memory 文件（仅当文件不存在时写入）
    write_if_missing(
        workspace / ".memory" / "全局知识地图.md",
        memory_global_map_content(),
    )
    for file_name, title in SYSTEM_RECORD_FILES.items():
        write_if_missing(
            workspace / ".memory" / "系统记录" / file_name,
            named_system_record_content(title),
        )

    # 5. 初始化 .system/standards/ 标准文件（覆盖层：备份旧版，替换为新版）
    _init_system_standards(workspace, templates, ts, stats)

    # 6. 初始化 AI 接入层
    _init_ai_entrypoints(workspace, templates, ts, stats)

    # 7. 创建核心骨架子项目 00_系统治理（仅当不存在时）
    _init_core_subproject(workspace)

    # 8. 记录本次 EXE 运行事件（初始化/升级）
    append_system_run_log(workspace, templates, ts, stats)

    return stats


# ──────────────────────────────────────────────────────────────────────
# 弹窗
# ──────────────────────────────────────────────────────────────────────

def show_result_dialog(workspace: Path, stats: dict):
    """弹出自定义结果窗口，展示初始化详情。"""
    root = tk.Tk()
    root.withdraw()  # 先隐藏主窗口

    if stats["errors"]:
        error_text = "\n".join(f"  ⚠ {e}" for e in stats["errors"])
        message = (
            f"工作区初始化完成（部分警告）\n\n"
            f"路径：{workspace}\n\n"
            f"本次操作：{stats.get('operation_type', '-')}\n"
            f".system 更新日志：{'已追加运行事件' if stats.get('run_logged') else '未写入'}\n\n"
            f"警告：\n{error_text}"
        )
        messagebox.showwarning("初始化完成（有警告）", message)
    else:
        skills_text = "\n".join(f"    · {s}" for s in stats["skills"])
        message = (
            f"✅  工作区骨架创建/升级完成！\n\n"
            f"路径：{workspace}\n\n"
            f"本次操作：{stats['operation_type']}\n\n"
            f"已创建：\n"
            f"  · .agents/rules       （{stats['rules']} 个 Rule 文件）\n"
            f"  · .agents/skills      （{len(stats['skills'])} 个 Skill 文件夹）\n"
            f"{skills_text}\n"
            f"  · AGENTS.md / CLAUDE.md / .claude （{stats['claude_commands']} 个斜杠命令）\n"
            f"  · .memory/           （已初始化记忆文件）\n"
            f"  · .system/standards  （已更新标准文件）\n"
            f"  · .system 更新日志  （{'已追加运行事件' if stats.get('run_logged') else '未写入'}）\n"
            f"  · .history/          （空的历史归档目录）\n"
            f"  · .temp/             （临时文件与异常归档目录）\n"
            f"  · input/  output/\n\n"
            f"升级备份：\n"
            f"  · Rule 备份 {stats['rule_backups']} 个\n"
            f"  · Skill 备份 {stats['skill_backups']} 个\n"
            f"  · Standard 备份 {stats['standards_backups']} 个\n"
            f"  · Codex 入口备份 {stats['codex_backups']} 个\n"
            f"  · Claude 接入层备份 {stats['claude_backups']} 个\n\n"
            f"现在可以开始使用这个工作区了。"
        )
        messagebox.showinfo("🎉 初始化完成", message)

    root.destroy()


# ──────────────────────────────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────────────────────────────

def main():
    workspace = get_workspace_root()
    templates = get_templates_dir()
    operation_type = detect_operation_type(workspace)

    # 安全检查：已有工作区运行时，确认是否继续升级骨架。
    if operation_type == "升级":
        root = tk.Tk()
        root.withdraw()
        answer = messagebox.askyesno(
            "目录已存在内容",
            f"目标目录已存在工作区内容：\n{workspace}\n\n是否继续升级骨架？\n\n工具会先备份受管 Rules/Skills/入口/标准，再替换为内置 v{SKELETON_VERSION} 模板；output、input、memory、temp 只补缺。",
        )
        root.destroy()
        if not answer:
            return

    stats = initialize_workspace(workspace, templates, operation_type)
    show_result_dialog(workspace, stats)


if __name__ == "__main__":
    main()
