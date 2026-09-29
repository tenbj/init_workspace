# ASOC 协议

ASOC（AI Skill Output Contract）把 Skill 定义为完整能力封装，而不是 Prompt 或单文件生成器。

## 六段合同

1. **Intent**：解决什么问题、服务谁、成功是什么。
2. **Workflow**：步骤、输入输出、门禁、失败处理。
3. **Input Schema**：AI 可以可靠解析的输入结构。
4. **Output Schema**：必须交付的文件、字段与状态。
5. **Artifacts**：人类可体验、AI 可消费的实际产物。
6. **Evaluation**：结构、语义、交互和跨文件一致性验证。

## 三层交付

| 层 | 对象 | H01 必备产物 |
|---|---|---|
| Human Layer | 产品、设计、业务人员 | `prd.md`、`prototype.html`、`user-flow.md` |
| Machine Layer | 后续 AI 与自动化 Harness | `manifest.json`、`ui.schema.json`、`interaction.json`、`api.yaml`、`database.sql` |
| Evaluation Layer | 当前 AI、评审者、CI | `evaluation/report.json` |

只有三层齐全且验证通过，才是可交付的原型能力包。

运行脚本需要 Python 3、`jsonschema` 与 `PyYAML`；依赖声明见 `scripts/requirements.txt`。

## 最小交付不等于删文件

时间不足或某层暂不适用时，文件仍须存在：

- YAML：写 `x-asoc-not-applicable: true` 和 `reason`。
- SQL：写 `-- ASOC-NOT-APPLICABLE: <reason>`。
- 其他文件：使用显式 `not_applicable` 字段或章节。

这样可以保持协议稳定，让下游 AI 区分“未生成”和“确认不适用”。
