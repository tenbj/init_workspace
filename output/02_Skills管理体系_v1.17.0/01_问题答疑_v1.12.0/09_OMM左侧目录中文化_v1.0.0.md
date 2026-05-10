# OMM 左侧目录中文化

## 结论

可以中文化，但不是只靠 `omm config language Chinese`。

当前 OMM 的语言配置会影响架构内容生成语言；左侧目录原本直接显示 perspective 名和节点文件夹名，例如 `overall-architecture`、`agent-entrypoints`。这些名字同时也是 OMM 的稳定路径 ID，直接改成中文目录会增加节点引用、URL 编码和后续 `omm validate` 的不确定性。

本次采用的方案是：底层目录和节点 ID 继续保持英文，给每个 `.omm/**/meta.yaml` 补中文 `title`，再让本地查看器左侧目录优先显示 `meta.title`。

## 本次处理

1. 调整本机 OMM 查看器：
   - 文件：`D:/npm/npm-global/node_modules/oh-my-mermaid/dist/viewer.html`
   - 增加 `navDisplayTitle` 显示函数。
   - 左侧顶层视角和子节点目录均优先读取 `classesData[*].meta.title`。
   - 没有中文标题时回退到原英文 ID。

2. 补齐当前项目 `.omm/` 的中文标题：
   - `overall-architecture` → `总体架构`
   - `governance-gates` → `治理强制门`
   - `skill-management-flow` → `技能管理流程`
   - 子节点同步补为 `智能体入口`、`工作区标准`、`技能运行层`、`记忆系统`、`稳定编号` 等中文标题。

3. 保持 OMM 内部引用稳定：
   - `.omm/` 目录名不改。
   - Mermaid 节点 ID 不改。
   - `children:` 列表不改。
   - 左侧目录只改“显示文本”，不改“真实路径”。

## 验证结果

- `http://localhost:3010/api/class/overall-architecture` 已返回 `meta.title = 总体架构`。
- `http://localhost:3010/api/class/overall-architecture/node/agent-entrypoints` 已返回 `meta.title = 智能体入口`。
- `http://localhost:3010/` 已加载带 `navDisplayTitle` 的新版查看器。
- `omm validate` 仍通过；仅保留原有提示：`overall-architecture` 节点数略多，建议后续按需要拆图。

## 使用方式

浏览器刷新 `http://localhost:3010/` 后，左侧目录应显示中文；如果页面仍显示英文，通常是旧前端脚本缓存，强制刷新一次即可。
