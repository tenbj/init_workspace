# 输入契约

## 默认输入

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--standard-library` | `input/标准库.xlsx` | 标准库 Excel，包含规则标准库和映射标准库 |
| `--model-design` | 无 | 待处理模型设计 Excel，必须显式传入 |
| `--sample-design` | 无 | 可选，已完结样例设计文档 |
| `--data-assets` | 无 | 可选，代码资产目录；第一版只记录路径，不扫描语义 |
| `--run-dir` | 无 | 显式指定本次运行目录，适合试跑 |
| `--output-root` | 当前模型设计标准化子项目的 `03_代码程序_v*/` | 未传 `--run-dir` 时在其下创建 `runs/{run_id}` |
| `--task-name` | 模型设计文件名清洗后生成 | run_id 的中文短名 |

## 推荐试跑命令

```powershell
python .agents\skills\E01_模型设计标准化_v1.0.0\scripts\01_parse_workbooks.py `
  --model-design "input\模型设计 - 利润核算（快报）.xlsx" `
  --standard-library "input\标准库.xlsx" `
  --run-dir ".temp\e01_runs\利润核算快报"
```

然后继续：

```powershell
python .agents\skills\E01_模型设计标准化_v1.0.0\scripts\02_build_ai_batches.py `
  --run-dir ".temp\e01_runs\利润核算快报"
```

## 正式输出到 output/

正式运行前应先按 B02 备份 `output/01_模型设计标准化_v*` 子项目，然后让脚本自动在当前子项目的 `03_代码程序_v*/runs/{run_id}/` 下落盘。

## 路径原则

- 输入文件只记录路径、大小和 hash，第一版不强制复制原始 Excel。
- 每次运行生成独立 run 目录，不覆盖旧 run。
- 如果用户显式传入 `--run-dir`，脚本只写该目录。
