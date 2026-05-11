# docs 来源调查

> 调查对象：根目录 `docs/` 以及 `docs/GitHub发布授权与Release流程.md`。

## 结论

`docs/` 是一次 GitHub 发布准备过程中新增的仓库级文档目录，不是当前工作区骨架标准要求的必备目录，也不是 B04 子项目体系自动生成的目录。

它出现在根目录的直接原因是：提交 `5321f3a` 在 2026-05-10 19:09:46 +0800 新增了 `docs/GitHub发布授权与Release流程.md`，同时修改 `README.md`，在“发布与隐私”章节指向该文档。该提交信息为 `Document GitHub release authorization flow`。

## 证据

### 1. 当前文件状态

根目录存在 `docs/`，其中只有一个文件：

```text
docs/GitHub发布授权与Release流程.md
```

文件系统时间显示：

| 对象 | 时间 |
|------|------|
| `docs/` LastWriteTime | 2026-05-10 19:09 |
| `docs/GitHub发布授权与Release流程.md` CreationTime | 2026-05-10 19:09:17 |
| `docs/GitHub发布授权与Release流程.md` LastWriteTime | 2026-05-10 19:09:17 |

### 2. Git 提交记录

相关提交：

```text
5321f3ad3295276afc477fddd1a7ecdd878d02fb
AuthorDate: 2026-05-10 19:09:46 +0800
CommitDate: 2026-05-10 19:09:46 +0800
Message: Document GitHub release authorization flow
```

该提交做了两件事：

| 路径 | 变更 |
|------|------|
| `README.md` | 增加指向 `docs/GitHub发布授权与Release流程.md` 的说明 |
| `docs/GitHub发布授权与Release流程.md` | 新增文件 |

当前 `main` 与 `origin/main` 均包含该提交，`docs/GitHub发布授权与Release流程.md` 已被 Git 追踪，且 `git status -- docs README.md` 没有显示未提交差异。

### 3. 文档内容指向的用途

`docs/GitHub发布授权与Release流程.md` 的开头说明它适用于：

```text
把本工作区发布到 tenbj/init_workspace，并将初始化工具 exe 上传到 GitHub Release。
```

正文包含：

- GitHub CLI 安装与登录。
- 创建或设置 `tenbj/init_workspace` 仓库。
- 推送 `main` 与 `v2.6.1` tag。
- 使用 `gh release create v2.6.1` 上传 `初始化工作区_v2.6.1.exe`。
- 发布前检查，包括不提交 `.Claude.json`、不提交 `*.exe`、`input/` 和 `.temp/` 只保留占位等。

### 4. README 对它的引用

`README.md` 在“发布与隐私”章节写入了：

```text
GitHub 授权、创建仓库和发布 Release 的完整流程见：
docs/GitHub发布授权与Release流程.md
```

因此 `docs/` 的入口不是孤立文件，而是作为仓库发布说明的一部分被 README 暴露。

## 为什么会出现在根目录

从证据看，`docs/` 是为了 GitHub 仓库发布而放在根目录的公开文档目录。它承担的是“仓库使用者/发布者说明”职责，和 `.github/release-notes/v2.6.1.md`、`README.md` 属于同一条发布链路。

但从当前工作区 SSOT 看，`workspace-spec.json` 的 `rootDirectories` 只列出：

```text
.agents
.claude
.history
.memory
.system
.temp
input
output
```

也就是说，`docs/` 不属于工作区骨架的必备目录。`B01` 体检只校验必备目录和必备文件是否存在，没有禁止额外根目录，因此 `docs/` 不会被框架体检报错。

## 判断

`docs/` 不是误生成目录，而是一次发布流程文档化的结果。它“合理但未纳入骨架标准”：合理之处在于 GitHub 仓库通常会把公共说明放在根目录 `README.md` 与 `docs/` 下；未纳入之处在于当前工作区标准没有把 `docs/` 作为受管目录或允许目录写入 SSOT。

## 后续可选处理

如果目标是严格遵循当前工作区规则，可以选择：

1. 将这类流程说明迁移到 `output/00_系统治理/...`，然后让 `README.md` 指向 output 内的标准文档。
2. 或者在 `workspace-spec.json` 和人类可读标准中显式声明 `docs/` 为“仓库发布文档目录”，并定义其边界。
3. 若保持现状，也应记录它是 GitHub 发布文档的特殊目录，避免后续误判为框架污染。
