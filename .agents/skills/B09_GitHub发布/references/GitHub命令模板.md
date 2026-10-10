# GitHub 命令模板

## 登录

```powershell
gh auth status
gh auth login
```

默认选择：

```text
GitHub.com
HTTPS
Authenticate Git with your GitHub credentials: Yes
Login with a web browser
```

## 仓库

创建新仓库并推送：

```powershell
gh repo create <owner>/<repo> --public --source . --remote origin --push
```

远端已存在时先只读核对，不自动改 remote URL：

```powershell
git remote -v
git branch --show-current
```

## 版本准备与 PR 合并

以下占位符须替换成已确认的仓库、工作分支、目标基线和提交；不要整段原样执行。

```powershell
git add -- CHANGELOG.md README.md .github/release-notes/vX.Y.Z.md
git commit -m "chore(release): 发布X.Y.Z"
git push -u origin <工作分支>
gh pr create --repo <owner/repo> --base <目标基线> --head <工作分支> --title "发布变更的中文标题" --body-file <PR说明文件>
gh pr view <PR编号> --repo <owner/repo> --json state,mergeable,statusCheckRollup,commits
```

完成检查且已有合并授权后，要求保留分类提交的任务使用 merge commit：

```powershell
gh pr merge <PR编号> --repo <owner/repo> --merge --match-head-commit <已核验分支末端SHA> --subject "merge: 中文合并说明" --body-file <合并说明文件>
git fetch origin <目标基线>
python .agents/skills/B11_Git分支工作流/scripts/verify_pr_merge.py --repo <owner/repo> --base <目标基线> --commit <PR合并SHA> --expected-commit <分类提交SHA1> --expected-commit <分类提交SHA2>
```

仅在上一步成功后对同一个合并 SHA 打标签，不从未合并的本地 HEAD 发版：

```powershell
git tag -a vX.Y.Z <PR合并SHA> -m "发布X.Y.Z"
git push origin refs/tags/vX.Y.Z
```

## 更新初始化程序

默认定位当前 `output/00_系统治理/03_代码程序/src`，全量刷新模板并写入更新清单：

```powershell
powershell -ExecutionPolicy Bypass -File ".agents\skills\B09_GitHub发布\scripts\update_init_program.ps1" -Version "X.Y.Z"
```

只预览将要更新的路径，不写入文件：

```powershell
powershell -ExecutionPolicy Bypass -File ".agents\skills\B09_GitHub发布\scripts\update_init_program.ps1" -Version "X.Y.Z" -WhatIf
```

## 重新封装初始化工具

```powershell
powershell -ExecutionPolicy Bypass -File ".agents\skills\B09_GitHub发布\scripts\build_init_exe.ps1" -ExpectedVersion "X.Y.Z"
```

如果只是检查命令顺序：

```powershell
powershell -ExecutionPolicy Bypass -File ".agents\skills\B09_GitHub发布\scripts\build_init_exe.ps1" -ExpectedVersion "X.Y.Z" -WhatIf
```

## 计算 SHA256

```powershell
Get-FileHash -Algorithm SHA256 "path\to\asset.exe"
```

## 创建 Release

```powershell
gh release create vX.Y.Z `
  "path\to\asset.exe" `
  --verify-tag `
  --title "init_workspace vX.Y.Z" `
  --notes-file ".github\release-notes\vX.Y.Z.md"
```

## 查看 Release

```powershell
gh release view vX.Y.Z --web
gh release view vX.Y.Z
```

## 更新 Release 附件

谨慎使用，先确认用户确实要替换附件：

```powershell
gh release upload vX.Y.Z "path\to\asset.exe" --clobber
```

## 比较链接

```text
https://github.com/<owner>/<repo>/compare/vOLD...vNEW
```
