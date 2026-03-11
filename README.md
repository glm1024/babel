# 功能

`babel` 用来批量扫描一个或多个代码仓库里的中文硬编码，按规则做出分类，并生成可离线查看的 HTML 报告，方便做国际化治理、整改排期和抽样复核。

它当前主要解决这几件事：

- 从源码、模板、配置、注释中提取中文文本
- 按上下文把命中归类为用户可见文案、错误提示、配置项、协议/持久化字面量，以及注释、Swagger 文档、普通文档、数据库脚本、日志、测试样例等
- 产出离线报告到 `babel/results/`，默认覆盖同目录下已有的 `findings.json`、`summary.json`、`report.html`
- 支持研发在本地服务首页直接配置扫描目录、发起扫描、查看进度，并在结果页中把部分 `需要整改` 命中标注为 `无需修改`
- 标注会持久化到 `results/annotations.json`，服务配置会持久化到 `results/app_state.json`

# 动作说明

- `需要整改`：包含用户可见文案、错误与校验提示、配置项、协议/持久化字面量、未知待确认。
- `保持不动`：包含代码注释、Swagger 文档、任务描述、普通文档、数据库脚本、Shell 脚本、指定文件、国际化文件、逻辑判断与字面量处理、日志审计与调试、测试与样例、标注无需修改。

# 扫描模式

如果你已经有 `repos.json`，仍然可以继续使用命令行扫描模式：

Linux or Mac：

```bash
PYTHONPATH=src python3 -m zh_audit scan --manifest repos.json --pretty
```

如果需要显式指定标注文件路径，可以追加：

```bash
PYTHONPATH=src python3 -m zh_audit scan --manifest repos.json --out results --annotations results/annotations.json --pretty
```

Windows PowerShell：

```powershell
$env:PYTHONPATH = "src"
python3 -m zh_audit scan --manifest repos.json --pretty
```

Windows Git Bash：

```bash
PYTHONPATH=src python3 -m zh_audit scan --manifest repos.json --pretty
```

# 本地服务模式

推荐直接启动本地服务：

```bash
PYTHONPATH=src python3 -m zh_audit serve --out results
```

它会默认：

- 启动本地 HTTP 服务
- 自动打开默认浏览器首页
- 在首页中配置多个扫描目录
- 点击“开始扫描”后实时展示扫描进度
- 扫描完成后在首页内嵌展示与 `report.html` 同风格的结果界面

如果不希望自动打开浏览器：

```bash
PYTHONPATH=src python3 -m zh_audit serve --out results --no-browser
```

服务相关文件默认写到 `results/`：

- `findings.json`
- `summary.json`
- `report.html`
- `annotations.json`
- `app_state.json`

# Manifest 配置

如果你仍然想使用 `repos.json` 驱动扫描，可以编辑项目根目录下的 `repos.json`，填写需要扫描的项目的本地绝对路径，例如：

Linux 或 Mac 可以这样写：

```json
[
  "/Users/mark/workspace/RuoYi"
]
```

Windows 可以这样写：

```json
[
  "D:/workspace/ICM-M/v8/icompute"
]
```

# 运行要求

- Python 3.6.1+
- 不支持 Python 2

# Review 模式

`review` 命令仍然保留，适合在已经存在 `findings.json / summary.json` 的前提下直接打开可编辑报告：

```bash
PYTHONPATH=src python3 -m zh_audit review --out results
```

默认标注会写到 `results/annotations.json`。后续重新执行 `scan` 时，会自动读取这个文件并把已标注项重新归类到 `标注无需修改 / 保持不动`。如果你是从零开始使用，优先推荐 `serve` 模式。
