# 功能

`babel` 用来批量扫描一个或多个代码仓库里的中文硬编码，按规则做出分类，并生成可离线查看的 HTML 报告，方便做国际化治理、整改排期和抽样复核。

它当前主要解决这几件事：

- 从源码、模板、配置、注释中提取中文文本
- 按上下文把命中归类为用户可见文案、错误提示、配置项、协议/持久化字面量，以及注释、Swagger 文档、普通文档、数据库脚本、日志、测试样例等
- 产出离线报告到 `babel/results/`，默认覆盖同目录下已有的 `findings.json`、`summary.json`、`report.html`

# 动作说明

- `需要整改`：包含用户可见文案、错误与校验提示、配置项、协议/持久化字面量、未知待确认。
- `保持不动`：包含注释、Swagger 文档、普通文档、数据库脚本、Shell 脚本、指定文件、国际化文件、条件判断字面量、日志审计与调试、测试与样例。

# 配置

编辑项目根目录下的 `repos.json` 文件，填写需要扫描的项目的本地绝对路径，例如：

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

# 运行

要求：

- Python 3.6.1+
- 不支持 Python 2

在项目根目录直接运行：

Linux or Mac：

```bash
PYTHONPATH=src python3 -m zh_audit scan --manifest repos.json --pretty
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
