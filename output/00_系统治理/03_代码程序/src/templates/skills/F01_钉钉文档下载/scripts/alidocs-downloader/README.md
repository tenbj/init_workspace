# Alidocs Downloader

用于通过已登录 Chrome 会话下载钉钉/阿里在线表格的小型脚本项目。

面向 F01 使用者的最短命令见：

```text
../../references/脚本使用说明.md
```

本 README 只保留脚本维护者需要的接口说明。

## 脚本入口

| 文件 | 定位 |
|------|------|
| `scripts/download_alidocs.py` | 推荐主入口，无额外依赖，支持校验和显式路径参数 |
| `scripts/download-alidocs.mjs` | Node 版本，逻辑与 Python 版本保持一致 |
| `scripts/download-alidocs.ps1` | PowerShell 薄包装，转调 Node 版本 |

## 推荐调用

```powershell
python ".\scripts\download_alidocs.py" `
  --doc "标准库" `
  --download-dir "F:\Projects\workspace\output\<当前子项目>\03_代码程序\downloads" `
  --output "标准库.xlsx" `
  --profile-dir "F:\Projects\workspace\.temp\F01\alidocs-chrome-profile"
```

只校验已下载文件：

```powershell
python ".\scripts\download_alidocs.py" `
  --doc "标准库" `
  --download-dir "F:\Projects\workspace\output\<当前子项目>\03_代码程序\downloads" `
  --output "标准库.xlsx" `
  --validate-only
```

Node 版本：

```powershell
node ".\scripts\download-alidocs.mjs" --doc "标准库" --download-dir "<downloads>" --output "标准库.xlsx" --profile-dir "<profile>"
```

PowerShell 包装：

```powershell
.\scripts\download-alidocs.ps1 -Doc "标准库" -DownloadDir "<downloads>" -Output "标准库.xlsx" -ProfileDir "<profile>"
```

## 配置

文档登记在 `config/docs.json`：

```json
"文档标记名": {
  "type": "dingtalk-alidocs-spreadsheet",
  "url": "https://alidocs.dingtalk.com/...",
  "outputFile": "文档标记名.xlsx",
  "format": "xlsx",
  "expectedSheets": []
}
```

运行时参数优先级高于配置文件：

- `--download-dir` 覆盖 `downloadDir`
- `--profile-dir` 覆盖 `chromeProfileDir`
- `--output` 覆盖文档项的 `outputFile`
- `--port` 覆盖 `chromeDebugPort`

## 工作方式

1. 启动或复用带调试端口的 Chrome。
2. 打开配置中的钉钉在线表格链接。
3. 自动点击 `菜单 -> 表格 -> 下载为 -> Excel (.xlsx，表格整体)`。
4. 监听 Chrome DevTools Protocol 的下载事件。
5. 获取钉钉生成的短期签名下载地址。
6. 立即用该地址下载 `.xlsx` 到本地。
7. 校验 `.xlsx` 文件结构、工作表名称和行列范围。

## 安全说明

- 脚本不会保存账号密码明文。
- Chrome profile 中会保留 cookies/session，用于下次复用登录态。
- 钉钉生成的短期签名下载地址只在运行时使用，不写入配置。
