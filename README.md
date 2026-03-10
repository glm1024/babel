# 功能

`babel` 用来批量扫描一个或多个代码仓库里的中文硬编码，按规则做初步分类，并生成可离线查看的 HTML 报告，方便做国际化治理、整改排期和抽样复核。

它当前主要解决这几件事：

- 从源码、模板、配置、注释中提取中文文本
- 按上下文把命中归类为用户可见文案、错误提示、日志、注释、测试样例、配置元数据等
- 产出 离线报告 `report.html`

# 配置

编辑项目根目录下的 `repos.json` 文件，填写需要扫描的项目的本地绝对路径，例如：

```json
[
  "/Users/mark/workspace/RuoYi"
]
```

# 运行

要求：

- Python 3.6.1+

在项目根目录直接运行：

```bash
PYTHONPATH=src python -m zh_audit scan --manifest repos.json --pretty
```


