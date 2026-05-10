# SSOT 架构决策对 exe 的影响

> 创建时间：2026-05-05  
> 关联：`.system/standards/workspace-spec.json`  
> 关联：`09_项目检查标准_v1.5.0/02_课题研究_v1.0.0/08_SSOT标准架构设计.md`

---

## 一、exe 需要适配的变更

### 1. 骨架目录从 13 → 17

新增 4 个目录到 `skeleton_dirs`：

```python
# 新增
".history/.memory/对话记录",
".history/.memory/系统记录",
".system/standards",
# 已有但需确认
".history/.memory/知识提炼",      # ✅ 已有
".history/.memory/全局知识地图",   # ✅ 已有
```

### 2. 新增核心骨架子项目 `00_系统治理`

exe 应在 `output/` 下补建 `00_系统治理_v1.0.0/`（含 3 子文件夹 + 2 固定文件），仅在不存在时创建。

### 3. 新增 `.memory/对话记录/00_系统治理_v1.0.0.md`

00 子项目的对话记录，仅在不存在时创建。

### 4. 新增 `.system/standards/` 内容

exe 模板的 `templates/` 下需包含：
- `standards/workspace-spec.json`
- `standards/工作区骨架规格.md`

复制逻辑：类似 rules，每次运行覆盖（备份旧版）。

### 5. init_workspace.py 改造

从硬编码 → 读取 `workspace-spec.json`：
- `skeleton_dirs` 列表改为从 JSON `requiredLayer.directories` 读取
- `SYSTEM_RECORD_FILES` 改为从 JSON `naming.systemRecord.fixedNames` 读取
- 新增：00 子项目创建逻辑
- 新增：`.system/standards/` 部署逻辑

---

## 二、模板文件同步清单

除架构改造外，仍需同步 3 个不匹配文件：

| 文件 | 方向 |
|------|------|
| `记忆管理/SKILL.md` | live → templates |
| `项目规范化/SKILL.md` | live → templates |
| `项目规范化/scripts/normalize.ps1` | live → templates |

---

## 三、exe 版本规划

当前 exe：`v1.7.2`（`SKELETON_VERSION`）

改造完成后建议：`v2.0.0`（MAJOR，因为新增 `.system/` 目录、改变骨架定义方式）
