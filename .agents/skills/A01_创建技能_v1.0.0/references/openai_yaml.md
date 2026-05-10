# `agents/openai.yaml` 速查

`agents/openai.yaml` 是面向 UI 的展示层元数据，不是业务真相源。当前本地生成脚本支持以下字段：

- `display_name`
- `short_description`
- `icon_small`
- `icon_large`
- `brand_color`
- `default_prompt`

## 默认要求

1. `display_name` 用人能快速看懂的中文名称。
2. `short_description` 用一句短中文说明这项 skill 的典型用途。
3. 只有在确实提供了图标或品牌色时，才补对应可选字段。

## 什么时候需要重读这份文件

- 需要手动覆盖默认展示名
- 需要补图标路径或默认提示词
- 需要确认生成脚本支持哪些字段

## 生成命令

```powershell
python scripts/generate_openai_yaml.py <skill_dir>
python scripts/generate_openai_yaml.py <skill_dir> --interface "display_name=自定义名称"
python scripts/generate_openai_yaml.py <skill_dir> --interface "short_description=一句短说明"
```
