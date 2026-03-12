# 功能

`babel` 用来批量扫描一个或多个代码仓库里的中文硬编码，按规则做出分类，并生成可离线查看的 HTML 报告，方便做国际化治理、整改排期和抽样复核。

它当前主要解决这几件事：

- 从源码、模板、配置、注释中提取中文文本
- 按上下文把命中归类为用户可见文案、错误提示、配置项、协议/持久化字面量，以及注释、Swagger 文档、普通文档、数据库脚本、日志、测试样例等
- 通过本地 Web 服务在页面上配置扫描目录、发起扫描、查看进度和结果
- 扫描完成后把结果写到 `babel/results/`，覆盖同目录下已有的 `findings.json`、`summary.json`、`report.html`
- 支持研发在结果页中把部分 `需要整改` 命中标注为 `无需修改`
- 支持在本地服务的“模型配置”页里维护 OpenAI-compatible 模型配置，也支持通过项目根目录的 `zh-audit.config.json` 提供可随仓库分发的默认值
- 支持在“码值校译”页中对中英 `.properties` 码表做 AI 校对、审批和回写，并强制应用项目内 `resources/terminology.xlsx` 中的标准术语
- 标注会持久化到 `results/annotations.json`，服务配置会持久化到 `results/app_state.json`

# 动作说明

- `需要整改`：包含用户可见文案、错误与校验提示、配置项、协议/持久化字面量、逻辑判断与字面量处理、未知待确认。
- `保持不动`：包含代码注释、Swagger 文档、任务描述、普通文档、数据库脚本、Shell 脚本、指定文件、国际化文件、日志审计与调试、测试与样例、标注无需修改。

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
- 在“模型配置”页中查看或覆盖项目默认模型配置
- 点击“开始扫描”后实时展示扫描进度
- 扫描完成后在“扫描结果”页中查看与 `report.html` 同风格的结果界面，并生成结果文件
- 在“码值校译”页中输入中英配置文件绝对路径，按标准术语词典和模型建议逐条审批翻译

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

项目内还维护一份术语词典 Excel：

- `resources/terminology.xlsx`

它会被“码值校译”页加载，凡是命中词典中文术语的翻译都必须使用词典中定义的英文，不允许模型自由改写。

# 模型配置

如果你希望把默认模型配置随项目一起发给其他研发，可以在项目根目录放一个 `zh-audit.config.json`：

```json
{
  "model_config": {
    "base_url": "http://100.7.69.249:7777/v1",
    "api_key": "",
    "model": "deepseek-v3",
    "max_tokens": 100
  }
}
```

本地服务启动时会按下面的优先级取模型配置：

1. 硬编码默认值
2. 项目根目录下的 `zh-audit.config.json`
3. `results/app_state.json` 中由 UI 保存的本地覆盖值

也可以显式指定配置文件路径：

```bash
PYTHONPATH=src python3 -m zh_audit serve --config /absolute/path/to/zh-audit.config.json
```

模型配置页里的“供应商”固定为 `openai compatible`。`Base URL` 支持填写主机根、`/v1` 或完整 `/v1/chat/completions`，保存时会自动归一化为 `.../v1`。UI 保存只会写本地 `results/app_state.json`，不会回写项目默认配置文件。
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
