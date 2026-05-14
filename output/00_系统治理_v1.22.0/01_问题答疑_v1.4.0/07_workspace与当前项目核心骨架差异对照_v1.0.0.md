# `F:\Projects\workspace` 与当前项目核心骨架差异对照

> 对照日期：2026-05-14  
> 当前项目：`F:\Projects\init_workspace`  
> 对照项目：`F:\Projects\workspace`  
> 说明：采集差异时当前项目的系统治理子项目为 `00_系统治理_v1.21.0`；本报告落盘后，按 B02 备份规则升级为 `00_系统治理_v1.22.0`。

---

## 1. 总结论

`F:\Projects\workspace` 不是当前项目的简单副本。它在核心标准和 Skill 注册表上更靠后：`workspace-spec.json` 是 `v1.15.0`，比当前项目的 `v1.14.0` 多了 `F` 域办公自动化和 `F01_钉钉文档下载_v1.0.0`，并把 `C01_同步代码仓库` 从 `v1.0.0` 升到 `v1.0.1`。

当前项目的系统治理内容和初始化工具代码更多：采集时 `00_系统治理` 已到 `v1.21.0`，代码程序分类是 `v2.11.0`，含初始化工具源码、模板、构建脚本和 EXE。对照项目的 `00_系统治理` 是 `v1.6.0`，三分类结构完整，但 `03_代码程序_v0.0.0` 为空。

两边的入口文件和规则层基本一致：`AGENTS.md`、`CLAUDE.md`、`.agents/rules/*.md` 在忽略行尾差异后无实质差异。真正的骨架差异集中在 SSOT 版本、Skill 注册表、Claude 私有占位文件、`.history/.system` 快照、`00_系统治理` 内容层，以及对照项目新增的 F01 和更新后的 E01/C01。

---

## 2. 体检结果差异

| 项目 | 当前项目 `init_workspace` | 对照项目 `workspace` |
|---|---|---|
| `workspace-spec.json` | `v1.14.0` | `v1.15.0` |
| 注册 Skill 数 | 25 | 26 |
| 必备目录 | 27 个目录均存在 | 27 个目录均存在 |
| 必备文件 | 缺 `.Claude.json`、`.claude/settings.local.json` | 15 个必备文件均存在 |
| B01 体检红项 | 11 个：Claude 私有占位缺失、根目录 README 缺历史目录、若干业务子项目缺三分类子目录 | 2 个：全局知识地图仍指向 `01_模型设计标准化_v1.16.0`，但实际 output 是 `v1.17.0` |
| `.ps1` BOM | 通过 | 通过 |
| Skill 命名合约 | 25 个通过 | 26 个通过 |
| Claude commands | 与 25 个注册 Skill 对齐 | 与 26 个注册 Skill 对齐 |

判断：对照项目的“必备骨架完整性”更好；当前项目的系统治理积累更多，但当前现场有缺失文件和部分业务子项目结构红项。

---

## 3. 根目录层差异

两边共有的核心根目录包括：

- `.agents`
- `.claude`
- `.history`
- `.memory`
- `.system`
- `.temp`
- `input`
- `output`
- `AGENTS.md`
- `CLAUDE.md`

当前项目额外存在：

- `.git`
- `.gitattributes`
- `.github`
- `.gitignore`
- `.omm`
- `CHANGELOG.md`
- `docs`
- `README.md`
- `SECURITY.md`

对照项目额外存在：

- `.Claude.json`

补充说明：`.claude/settings.local.json` 不在对照项目根目录，而在 `F:\Projects\workspace\.claude\settings.local.json` 中；当前项目的 `.claude` 下只有 `commands` 目录，缺少该本机权限占位文件。

---

## 4. `.system/standards` 差异

四个标准文件两边都存在。

| 标准文件 | 差异 |
|---|---|
| `workspace-spec.json` | 不同。当前是 `v1.14.0`，对照项目是 `v1.15.0` |
| `Skills管理标准.md` | 不同。当前是 `v1.9.0`，对照项目是 `v1.10.0` |
| `工作区骨架规格.md` | 内容相同 |
| `工作区命名规范.md` | 内容相同 |

`workspace-spec.json` 的实质差异只有三处：

- 标准版本：`1.14.0` -> `1.15.0`
- 注册表中 `C01_同步代码仓库_v1.0.0` -> `C01_同步代码仓库_v1.0.1`
- 注册表新增 `F01_钉钉文档下载_v1.0.0`

`Skills管理标准.md` 的实质差异：

- 标准版本：`1.9.0` -> `1.10.0`
- `F` 域从保留域变为“办公自动化”
- 新增 `F01`：钉钉文档下载，职责是下载钉钉在线文档/表格、复用登录会话、导出本地文件并校验

---

## 5. `.agents/rules` 差异

规则文件名完全一致，且内容相同：

- `direction-rules.md`
- `filename-rules.md`
- `memory-rules.md`
- `version-control-rules.md`

判断：本轮未发现规则层制度差异。

---

## 6. `.agents/skills` 差异

### 6.1 Skill 清单差异

当前项目独有：

- `C01_同步代码仓库_v1.0.0`

对照项目独有：

- `C01_同步代码仓库_v1.0.1`
- `F01_钉钉文档下载_v1.0.0`

因此，对照项目比当前项目多 1 个注册 Skill，并包含一个更新后的 C01。

### 6.2 C01 差异

对照项目的 `C01_同步代码仓库_v1.0.1` 相比当前 `v1.0.0`，核心变化是目标仓库缺失或目标目录为空时，默认使用内部数据资产仓库地址克隆；仍可用 `DATA_ASSETS_REPO_URL` 或 `--clone-url` 覆盖。当前项目的 `v1.0.0` 要求必须通过环境变量或参数提供克隆地址。

风险提示：这属于行为差异。是否应同步到当前项目，需要按安全边界确认默认远端地址是否允许进入当前工作区。

### 6.3 F01 差异

对照项目新增完整 F01 目录，包含：

- `SKILL.md`
- `agents/openai.yaml`
- `references/下载工作流.md`
- `references/常用链接.md`
- `assets/.gitkeep`
- `scripts/.gitkeep`

当前项目没有 F 域，也没有 F01。

### 6.4 E01 差异

两边都有 `E01_模型设计标准化_v1.0.1`，但对照项目的 E01 有实质增强：

- 新增 `template_writeback` 模式
- 解析阶段新增 `workbook_layout.json`，记录 sheet 顺序、隐藏状态、合并单元格、行列尺寸和样式摘要
- AI 决策要求给人看的 `reason`、`human_question`、`suggested_standard` 等中文化
- 写回阶段支持生成 `{原文件名}_待标准化.xlsx` 与 `{原文件名}_已标准化.xlsx`
- `已标准化` 工作簿可原位维护目录页、实体表名和字段名
- 新增 `0 标准化结果` sheet，作为中文留痕清单，包含可点击跳转到原实体 sheet 单元格的链接
- `05_generate_run_summary.py` 能识别已标准化 Excel

对照项目 E01 下还出现了 `scripts/__pycache__/*.pyc`，这是运行生成物，不属于理想的核心骨架源文件。

### 6.5 其他 common Skill

多数同名 Skill 的正文和脚本在忽略行尾差异后无实质差异。初始 hash 对比显示大量差异，主要来自 CRLF/LF 行尾不同；用 `git diff --ignore-space-at-eol` 复核后，实质差异集中在 E01、C01 版本更替、F01 新增，以及对照项目中的 `__pycache__` 生成物。

---

## 7. `.claude` 差异

| 项目 | 当前项目 | 对照项目 |
|---|---|---|
| `.claude/commands` | 存在 | 存在 |
| `.claude/settings.local.json` | 缺失 | 存在 |
| command 数量 | 25 | 26 |
| command 清单差异 | `C01_同步代码仓库_v1.0.0.md` | `C01_同步代码仓库_v1.0.1.md`、`F01_钉钉文档下载_v1.0.0.md` |

同名 command 文件忽略空行和行尾差异后内容一致，都是薄包装：

```text
请读取并执行 .agents/skills/{Skill名}/SKILL.md
```

判断：Claude command 层跟随 Skill 注册表变化，没有发现额外制度差异。

---

## 8. `.history` 差异

两边都有 `.history` 的主要镜像目录：

- `.history/.agents`
- `.history/.claude`
- `.history/.memory`
- `.history/.system`
- `.history/AGENTS`
- `.history/CLAUDE`
- `.history/output`

`.history/.system` 差异明显：

| 项目 | `.history/.system` 内容 |
|---|---|
| 当前项目 | `.gitkeep`、`standards` |
| 对照项目 | `standards`、`standards_20260511172919`、`standards_20260513100950`、`standards_20260514091110`、`更新日志.md` |

判断：对照项目保留了 3 次 `.system/standards` 时间戳快照和更新日志；当前项目没有时间戳快照，也没有 `.history/.system/更新日志.md` 当前文件。当前项目 B01 之所以该项通过，是因为没有 timestamped snapshot 需要日志覆盖。

根目录 README 相关差异：

- 当前项目有 `README.md`，但缺 `.history/README/`，因此 B01 报红。
- 对照项目没有根目录 `README.md`，也没有 `.history/README/`，因此不会触发 README 历史目录红项。

---

## 9. `.memory` 差异

两边固定记忆文件都存在：

- `.memory/全局知识地图.md`
- `.memory/系统记录/规则变更记录.md`
- `.memory/系统记录/技能变更记录.md`
- `.memory/系统记录/脚本治理记录.md`
- `.memory/系统记录/教训库.md`
- `.memory/系统记录/索引.md`
- `.memory/任务进度/索引.md`

差异主要是内容态，而不是骨架缺失：

- 当前项目 output 有 6 个子项目，对照项目 output 有 5 个子项目。
- 当前项目任务进度有自己的运行态记录，本轮还新增了“比较双工作区核心骨架”任务。
- 对照项目 B01 报红是知识地图与 output 版本不一致：地图仍记录 `01_模型设计标准化_v1.16.0`，实际 output 是 `01_模型设计标准化_v1.17.0`。

---

## 10. `output/00_系统治理` 差异

采集时的核心子项目差异如下：

| 项目 | 当前项目 | 对照项目 |
|---|---|---|
| 核心子项目 | `00_系统治理_v1.21.0` | `00_系统治理_v1.6.0` |
| 固定文件 | `目录.md`、`版本记录.md` | `目录.md`、`版本记录.md` |
| `01_问题答疑` | `v1.3.0`，6 个文件 | `v1.2.0`，3 个文件 |
| `02_课题研究` | `v1.10.0`，11 个文件 | `v1.1.0`，2 个文件 |
| `03_代码程序` | `v2.11.0`，187 个文件 | `v0.0.0`，0 个文件 |

判断：

- 当前项目的 `00_系统治理` 是初始化工具和系统治理知识的主仓，内容显著更多。
- 对照项目虽然 SSOT 标准版本更高，但 `00_系统治理` 代码程序分类为空，不包含当前项目里的初始化工具源码、模板、构建脚本和 EXE。
- 当前项目这次新增本报告后，`00_系统治理` 已升级为 `v1.22.0`，`01_问题答疑` 已升级为 `v1.4.0`。

---

## 11. 业务子项目清单差异

当前项目 output：

- `00_系统治理_v1.21.0`（本报告落盘后为 `v1.22.0`）
- `01_DWD开发产物_v1.0.1`
- `02_Skills管理体系_v1.19.0`
- `03_模型设计标准化_v1.9.0`
- `04_减脂内容计划_v1.1.1`
- `05_原子拆解技能_v1.4.1`

对照项目 output：

- `00_系统治理_v1.6.0`
- `01_模型设计标准化_v1.17.0`
- `02_数据质量_v1.1.0`
- `03_实体模型拆分_v1.2.0`
- `04_钉钉文档下载_v1.3.0`

判断：对照项目围绕模型设计、数据质量、实体拆分和钉钉文档下载展开；当前项目围绕系统治理、DWD、Skills 体系、模型设计、减脂内容和原子拆解展开。业务项目不同，不应直接视为骨架缺失。

---

## 12. 可行动差异清单

若要让当前项目追上对照项目的核心骨架，最小同步项是：

1. 补齐 `.Claude.json` 与 `.claude/settings.local.json` 的脱敏占位文件。
2. 将 `.system/standards/workspace-spec.json` 从 `v1.14.0` 升到 `v1.15.0`，仅限用户直接授权修改 `.system` 后执行。
3. 将 `.system/standards/Skills管理标准.md` 从 `v1.9.0` 升到 `v1.10.0`，新增 F 域和 F01 注册说明，同样需要用户直接授权 `.system` 修改。
4. 将 `C01_同步代码仓库` 从 `v1.0.0` 评估升级到 `v1.0.1`，但需先确认默认内部远端地址是否允许进入当前项目。
5. 安装或迁入 `F01_钉钉文档下载_v1.0.0`，并同步 `.claude/commands/F01_钉钉文档下载_v1.0.0.md`。
6. 评估是否同步对照项目 E01 的 `template_writeback` 增强。
7. 清理或忽略对照项目里的 `__pycache__/*.pyc`，这类文件不应作为核心骨架源文件迁入。
8. 当前项目自身还需处理 B01 红项：缺失 Claude 私有占位、README 历史目录、部分业务子项目三分类目录缺失。

---

## 13. 一句话结论

对照项目 `F:\Projects\workspace` 的 SSOT 和 Skill 注册表更新，主要领先在 `F01`、`C01 v1.0.1` 和 E01 模板回填能力；当前项目 `F:\Projects\init_workspace` 的系统治理和初始化工具资产更完整，但现场骨架健康度有红项，需要补齐 Claude 占位和若干结构规范。
