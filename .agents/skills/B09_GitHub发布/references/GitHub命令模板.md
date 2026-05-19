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

远端已存在时：

```powershell
git remote set-url origin https://github.com/<owner>/<repo>.git
git push -u origin main
```

## 版本准备

```powershell
git add CHANGELOG.md README.md docs/GitHub发布授权与Release流程.md .github/release-notes/vX.Y.Z.md
git commit -m "chore(release): prepare vX.Y.Z"
git tag vX.Y.Z
git push origin main
git push origin vX.Y.Z
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
