# GitHub 发布授权与 Release 流程

> 适用于把本工作区发布到 `tenbj/init_workspace`，并将初始化工具 exe 上传到 GitHub Release。

## 1. 授权方式

推荐使用 GitHub CLI。不要在聊天窗口、文档或命令历史里暴露 GitHub token。

### 安装 GitHub CLI

在本机 PowerShell 运行：

```powershell
winget install --id GitHub.cli -e
```

如提示确认协议，输入 `Y`。

安装完成后，关闭当前 PowerShell，再重新打开一个新的 PowerShell。

### 验证安装

```powershell
gh --version
```

能看到版本号即表示安装成功。

### 登录 GitHub

```powershell
gh auth login
```

按提示选择：

```text
GitHub.com
HTTPS
Authenticate Git with your GitHub credentials: Yes
Login with a web browser
```

随后浏览器会打开 GitHub 授权页。用 `tenbj` 账号登录，输入一次性 code 并授权。

### 验证登录

```powershell
gh auth status
```

看到 `Logged in to github.com account tenbj` 即可继续发布。

## 2. 创建仓库并推送

在项目根目录运行：

```powershell
gh repo create tenbj/init_workspace --public --source . --remote origin --push
git push origin v2.6.1
```

如果远端仓库已存在，则改用：

```powershell
git remote set-url origin https://github.com/tenbj/init_workspace.git
git push -u origin main
git push origin v2.6.1
```

## 3. 创建 Release 并上传 exe

```powershell
gh release create v2.6.1 `
  "output\00_系统治理_v1.6.1\03_代码程序_v2.6.1\dist\初始化工作区_v2.6.1.exe" `
  --title "init_workspace v2.6.1" `
  --notes-file ".github\release-notes\v2.6.1.md"
```

## 4. 发布前检查

发布前必须确认：

- `git status --short` 无未提交改动。
- `.Claude.json` 未入库。
- `input/` 和 `.temp/` 只保留 `.gitkeep`。
- `.history/` 只保留骨架目录 `.gitkeep`。
- 暂存区不包含 `*.exe`，exe 只作为 Release 附件上传。
- 暂存区敏感模式扫描通过。

## 5. 本次发布资产

```text
output/00_系统治理_v1.6.1/03_代码程序_v2.6.1/dist/初始化工作区_v2.6.1.exe
```
