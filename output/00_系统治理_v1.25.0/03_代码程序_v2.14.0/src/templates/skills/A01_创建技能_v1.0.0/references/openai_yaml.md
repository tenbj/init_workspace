# `agents/openai.yaml` 速查

`agents/openai.yaml` 是面向 UI 的展示层元数据，不是业务真相源。当前本地生成脚本支持以下字段：

- `display_name`
- `short_description`
- `icon_small`
- `icon_large`
- `brand_color`
- `default_prompt`

## 默认要求

1. `display_name` 必须等于完整标准 Skill 名，即 `{域代码}{编号}_{技能名}_v{MAJOR}.{MINOR}.{PATCH}`，并与文件夹名、`SKILL.md` YAML `name` 保持一致。
2. `short_description` 用一句短中文说明这项 skill 的典型用途。
3. 如果填写 `default_prompt`，必须使用 Codex/OpenAI 展示层调用名 `$编号`，例如 `$B10`。
4. `default_prompt` 不得使用完整 Skill 名称（如 `$B10_课题分离_v1.0.0`），也不得使用 Claude 斜杠命令（如 `/B10`）。
5. 只有在确实提供了图标或品牌色时，才补对应可选字段。

## 什么时候需要重读这份文件

- 需要确认展示名是否与标准 Skill 名一致
- 需要补图标路径或默认提示词
- 需要确认生成脚本支持哪些字段

## 生成命令

```powershell
python scripts/generate_openai_yaml.py <skill_dir>
python scripts/generate_openai_yaml.py <skill_dir> --interface "short_description=一句短说明"
```

`display_name` 不允许通过 `--interface` 覆盖；脚本会从 `SKILL.md` frontmatter 的 `name` 读取完整标准名并写入。
