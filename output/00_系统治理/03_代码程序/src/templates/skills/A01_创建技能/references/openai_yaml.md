# `agents/openai.yaml` 速查

`agents/openai.yaml` 是面向 UI 的展示层元数据，不是业务真相源。当前本地生成脚本支持以下字段：

- `display_name`
- `short_description`
- `icon_small`
- `icon_large`
- `brand_color`
- `default_prompt`

## 默认要求

1. 未显式覆盖时，`display_name` 默认写成 `{Skill名}_v{MAJOR}.{MINOR}.{PATCH}`。
2. `short_description` 用一句短中文说明这项 skill 的典型用途。
3. 如果填写 `default_prompt`，必须使用 Codex/OpenAI 展示层调用名 `$编号`，例如 `$B10`。
4. `default_prompt` 不得使用完整 Skill 名称（如 `$B10_课题分离`），也不得使用 Claude 斜杠命令（如 `/B10`）。
5. 只有在确实提供了图标或品牌色时，才补对应可选字段。

## 什么时候需要重读这份文件

- 需要确认展示名、短描述、图标或默认提示词
- 需要补图标路径或默认提示词
- 需要确认生成脚本支持哪些字段

## 生成命令

```powershell
python scripts/generate_openai_yaml.py <skill_dir>
python scripts/generate_openai_yaml.py <skill_dir> --interface "short_description=一句短说明"
python scripts/generate_openai_yaml.py <skill_dir> --interface "display_name=自定义展示名"
```

脚本会优先使用调用方传入的 `display_name`；未传时从 `SKILL.md` frontmatter 的 `name` 读取 Skill 名，并追加版本后写入。
