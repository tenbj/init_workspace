# YAML name 命名未遵守的根因与根治方案

## 问题

连续使用 `A01_创建技能` 和 `A02_安装技能` 创建或迁入 Skill 时，为什么会反复生成不符合 `.system/standards/Skills管理标准.md` 的 YAML `name`？

标准已经明确要求：

```yaml
name: {域代码}{编号}_{技能名}_v{MAJOR}.{MINOR}.{PATCH}
```

并且 YAML `name` 必须与 Skill 文件夹名完全一致、必须带版本号。

## 复核结论

当前 live Skill 目录本身已经全部符合规则：`.agents/skills/` 下 23 个 Skill 的文件夹名均满足 `{域代码}{编号}_{技能名}_v{MAJOR}.{MINOR}.{PATCH}`，且 `SKILL.md` 的 YAML `name` 均与文件夹名一致。

但创建和安装链路仍然存在复发风险，因为执行层没有完全收敛到最新 SSOT。

## 为什么没有遵守

根因不是 `.system/standards/Skills管理标准.md` 写得不清楚，而是 A01/A02 的热路径仍保留了旧口径，并且缺少硬校验。

### 1. A01 的参考规则仍是旧命名口径

`A01_创建技能/references/技能创建完整流程.md` 仍写着：

```text
不把运行环境、时间戳或版本号写进目录名
```

这与当前 Skill 管理标准直接冲突。模型执行 A01 时，如果更多依赖 A01 的 references，而没有重新读取 `.system/standards/Skills管理标准.md`，就会自然回到旧口径。

### 2. A01 的生成脚本只校验“中文名”，不校验标准 Skill 名

`A01_创建技能/scripts/init_skill.py` 当前把传入的 `skill_name` 同时当作目录名和 YAML `name`，但 `validate_skill_name()` 只检查：

- 名称不能为空
- 不能含路径分隔符
- 必须包含中文

它没有校验：

- 是否以 `A01_`、`B07_` 这类域编号开头
- 是否带 `_v1.0.0` 这类三段式版本号
- YAML `name` 是否与文件夹名一致

所以脚本层会接受 `原子拆解技能` 这类中文名，并原样生成：

```yaml
name: 原子拆解技能
```

### 3. A02 的本地化脚本也把“中文显示名”误当成“Skill 标准名”

`A02_安装技能/scripts/install-skill-from-github.py` 中，`suggest_local_name()` 倾向返回中文名，`thin_skill_markdown()` 又直接写：

```yaml
name: {local_name}
```

这等于把“人看得懂的显示名”和“系统标准 Skill 名”混成了一个字段。当前标准下，显示名可以进入 `agents/openai.yaml` 的 `display_name`，但 `SKILL.md` 的 YAML `name` 必须是完整标准名。

### 4. quick_validate 只检查“有 name 且含中文”，没有检查“等于文件夹名”

`A01_创建技能/scripts/quick_validate.py` 当前只会拦截没有 `name` 或 `name` 不含中文的情况。

它不会拦截这些错误：

```yaml
name: 创建技能
name: 原子拆解技能
name: A01_创建技能
name: A01_创建技能_v1.0
```

只要有中文，就可能通过。这就是“标准存在，但错误没有被挡住”的关键。

### 5. B01 框架体检没有检查 Skill YAML name 合约

当前 `B01_框架体检/scripts/framework-check.ps1` 已检查 registeredSkills、Claude commands、目录骨架、BOM、目录链接等，但没有单独检查：

- 每个 `.agents/skills/*/` 文件夹名是否符合 Skill 命名正则
- 每个 `SKILL.md` YAML `name` 是否等于文件夹名
- `workspace-spec.json` 的 `skillsManagement.registeredSkills` 是否与实际目录一致

因此创建时错了，体检也不一定能在第一时间以 FAIL 报出来。

## 最终判断

这类问题不能靠“提醒模型注意标准”根治。因为 A01/A02 是执行入口，模型在实际创建时会优先走入口 Skill 的 references 和脚本；只要入口和脚本还允许旧格式，错误就会复发。

根治方式必须是：把标准变成生成器默认值、安装器默认值、局部校验器、全局体检器四道硬门。

## 最小根治方案

| 优先级 | 意图指向 | 具体落点 | 要做什么 | 验收标准 |
|--------|----------|----------|----------|----------|
| P0 | A01：生成即正确 | `A01/scripts/init_skill.py`、A01 references | `skill_name` 必须匹配 `^[A-Z]\d{2}_.+_v\d+\.\d+\.\d+$`；默认新建版本为 `v1.0.0`；`SKILL.md` YAML `name` 写入完整文件夹名 | 传入 `原子拆解技能` 直接失败；传入 `F01_原子拆解技能_v1.0.0` 成功，YAML `name` 等于文件夹名 |
| P0 | A02：迁入即本地标准化 | `A02/scripts/install-skill-from-github.py`、A02 references | `--name` 改为标准 Skill 文件夹名；中文显示名改放 `agents/openai.yaml display_name`；生成薄 `SKILL.md` 时 `name` 等于目录名 | 安装外部 skill 后，目录名与 YAML `name` 均为完整标准名 |
| P0 | A01：局部校验必须挡错 | `A01/scripts/quick_validate.py` | 增加文件夹名正则校验、YAML `name` 正则校验、二者一致性校验 | 中文短名、缺版本号、版本号不完整、YAML 与目录不一致均返回非 0 |
| P0 | B01：全局体检必须挡错 | `B01/scripts/framework-check.ps1` | 新增 “Skill Naming Contract” 检查：目录名、YAML `name`、registeredSkills、`.claude/commands` 全链路一致 | 任一 Skill name 不合规时，B01 输出 FAIL |
| P1 | B06：批量规范化兜底 | `B06` 规范化脚本 | 在规范化中复用同一套 Skill naming 检查，必要时只报告不自动改名 | 批量治理后能发现漂移 |
| P1 | 去重校验逻辑 | 新增共享脚本或函数 | 把 Skill 名称正则、frontmatter 读取和一致性检查抽为共享逻辑，供 A01/A02/B01/B06 调用 | 不再出现多个脚本各写一套不一致规则 |

## 推荐实现顺序

1. 先修改 A01 references 和 `init_skill.py`，让新建 Skill 从源头只能生成标准名。
2. 再修改 A02 references 和安装脚本，让迁入 Skill 不能再用中文短名做 YAML `name`。
3. 再强化 `quick_validate.py`，把旧格式作为错误拦住。
4. 最后强化 B01 框架体检，把所有现存和未来漂移都变成全局 FAIL。
5. 修改任何 Skill 前先执行 B02；如果 Skill 需要版本 bump，必须同步更新文件夹名、YAML `name`、`workspace-spec.json`、`.claude/commands` 和 Skills 管理标准映射表。

## 不做事项

- 不修改 `.system/standards/Skills管理标准.md` 的命名规则；标准本身已经正确。
- 不把 `display_name` 和 YAML `name` 混用；前者是展示名，后者是标准调用入口。
- 不只在文档里提醒“必须带版本号”；必须让脚本和体检直接失败。
- 不在没有 `.system` 具体授权的情况下更新 `workspace-spec.json` 或 Skills 管理标准映射表。

## 验收口径

根治完成后，至少要能通过以下验收：

```powershell
python .agents\skills\A01_创建技能\scripts\init_skill.py 原子拆解技能
```

必须失败，并提示名称应为 `{域代码}{编号}_{技能名}_v{MAJOR}.{MINOR}.{PATCH}`。

```powershell
python .agents\skills\A01_创建技能\scripts\init_skill.py F01_原子拆解技能_v1.0.0
python .agents\skills\A01_创建技能\scripts\quick_validate.py .agents\skills\F01_原子拆解技能_v1.0.0
```

必须成功，且 `SKILL.md` 中为：

```yaml
name: F01_原子拆解技能_v1.0.0
```

手动把某个 `SKILL.md` 改成：

```yaml
name: 原子拆解技能
```

再运行：

```powershell
powershell -ExecutionPolicy Bypass -File .agents\skills\B01_框架体检\scripts\framework-check.ps1
```

必须输出 FAIL，而不是 WARN 或 PASS。

## 一句话结论

反复不遵守 YAML `name` 命名规则，是因为标准已经升级，但 A01/A02 的创建、安装、校验和 B01 体检没有同步升级成硬门。根治不是再写一遍规则，而是让“非标准 Skill 名”在生成、安装、局部校验、全局体检四个环节都无法通过。
