# 功能

`babel` 用来批量扫描一个或多个代码仓库里的中文硬编码，按规则做出分类，并生成可离线查看的 HTML 报告，方便做国际化治理、整改排期和抽样复核。

它当前主要解决这几件事：

- 从源码、模板、配置、注释中提取中文文本
- 按上下文把命中归类为用户可见文案、错误提示、配置项、协议/持久化字面量，以及注释、Swagger 文档、普通文档、数据库脚本、日志、测试样例等
- 通过本地 Web 服务在页面上配置扫描目录、发起扫描、查看进度和结果
- 扫描完成后把结果写到 `babel/results/`，覆盖同目录下已有的 `findings.json`、`summary.json`、`report.html`
- 支持研发在结果页中把部分 `需要整改` 命中标注为 `无需修改`
- 标注会持久化到 `results/annotations.json`，服务配置会持久化到 `results/app_state.json`

# 动作说明

- `需要整改`：包含用户可见文案、错误与校验提示、配置项、协议/持久化字面量、未知待确认。
- `保持不动`：包含代码注释、Swagger 文档、任务描述、普通文档、数据库脚本、Shell 脚本、指定文件、国际化文件、逻辑判断与字面量处理、日志审计与调试、测试与样例、标注无需修改。

# 本地服务模式

项目现在只保留本地服务模式，推荐直接启动：

Linux or Mac：

```bash
PYTHONPATH=src python3 -m zh_audit serve
```

Windows PowerShell：

```powershell
$env:PYTHONPATH = "src"
python3 -m zh_audit serve
```

它会默认：

- 启动本地 HTTP 服务
- 自动打开默认浏览器首页
- 在首页中配置多个扫描目录
- 支持 `results/` 为空时冷启动，首页会先显示“暂无当前会话扫描结果”空态
- 点击“开始扫描”后实时展示扫描进度
- 扫描完成后在首页内嵌展示与 `report.html` 同风格的结果界面，并生成结果文件

如果不希望自动打开浏览器：

Linux or Mac：

```bash
PYTHONPATH=src python3 -m zh_audit serve --no-browser
```

Windows PowerShell：

```powershell
$env:PYTHONPATH = "src"
python3 -m zh_audit serve --no-browser
```

服务相关文件默认写到 `results/`：

- `findings.json`
- `summary.json`
- `report.html`
- `annotations.json`
- `app_state.json`

# 运行要求

- Python 3.6.1+
- 不支持 Python 2

# 结果文件

服务运行中会按需生成这些文件：

- `findings.json`
- `summary.json`
- `report.html`
- `annotations.json`
- `app_state.json`

其中：

- 首次启动时 `results/` 可以为空，不要求预先存在结果文件
- `findings.json / summary.json / report.html` 会在首次扫描完成后生成
- `app_state.json` 会在保存扫描目录或设置后生成
- `annotations.json` 会在首次标注“无需修改”后生成

# 校验模式

`validate` 仍然保留，适合研发或规则维护者对已有扫描结果做质量校验，不是普通用户的日常入口。
