import json


DISPLAY_MAPS = {
    "category": {
        "USER_VISIBLE_COPY": "用户可见文案",
        "ERROR_VALIDATION_MESSAGE": "错误与校验提示",
        "LOG_AUDIT_DEBUG": "日志审计与调试",
        "COMMENT": "代码注释",
        "SWAGGER_DOCUMENTATION": "Swagger 文档",
        "GENERIC_DOCUMENTATION": "普通文档",
        "DATABASE_SCRIPT": "数据库脚本",
        "SHELL_SCRIPT": "Shell 脚本",
        "NAMED_FILE": "指定文件",
        "I18N_FILE": "国际化文件",
        "CONDITION_EXPRESSION_LITERAL": "逻辑判断与字面量处理",
        "TASK_DESCRIPTION": "任务描述",
        "ANNOTATED_NO_CHANGE": "标注无需修改",
        "TEST_SAMPLE_FIXTURE": "测试与样例",
        "CONFIG_ITEM": "配置项",
        "PROTOCOL_OR_PERSISTED_LITERAL": "协议/持久化字面量",
        "UNKNOWN": "未知待确认",
    },
    "action": {
        "fix": "需要整改",
        "keep": "保持不动",
    },
    "language": {
        "java": "Java",
        "go": "Go",
        "python": "Python",
        "vm": "VM 模板",
        "yaml": "YAML 配置",
        "json": "JSON 配置",
        "properties": "Properties 配置",
        "html": "HTML 模板",
        "markdown": "Markdown 文档",
        "shell": "Shell 脚本",
        "sql": "SQL",
        "xml": "XML",
        "text": "普通文本",
        "toml": "TOML 配置",
        "css": "CSS",
        "javascript": "JavaScript",
        "typescript": "TypeScript",
    },
    "skip_reason": {
        "binary_extension": "二进制扩展名",
        "binary_content": "二进制内容",
        "stat_error": "文件状态读取失败",
        "read_error": "文件读取失败",
        "too_large": "文件过大",
        "decode_error": "文本解码失败",
        "excluded_by_policy": "命中排除策略",
        "named_file": "指定文件名",
    },
    "reason": {
        "No strong rule matched.": "没有命中更强的规则，需要人工确认。",
        "Comment context.": "当前命中位于代码注释上下文。",
        "Test/sample path context.": "当前命中位于测试或样例路径上下文。",
        "Logging API context.": "当前命中位于日志接口上下文。",
        "Error/exception context.": "当前命中位于异常或错误处理上下文。",
        "Error semantics in string literal.": "当前命中带有明显错误或校验语义。",
        "Configuration item context.": "当前命中位于配置项上下文。",
        "Markup or front-end text context.": "当前命中位于模板或前端资源上下文。",
        "Looks like protocol or persisted value.": "当前命中看起来像协议值或持久化字面量。",
        "String literal with Chinese text.": "当前命中是包含中文的字符串字面量。",
        "Documentation asset context.": "当前命中位于普通文档资产中。",
        "Database script context.": "当前命中位于数据库脚本中。",
        "Shell script context.": "当前命中位于 Shell 脚本中。",
        "Swagger/OpenAPI annotation context.": "当前命中位于 Swagger/OpenAPI 注解上下文。",
        "Named file context.": "当前命中位于指定文件中。",
        "I18n messages file context.": "当前命中位于国际化文件中。",
        "Condition expression literal context.": "当前命中用于逻辑判断或字符串处理。",
        "Logic processing literal context.": "当前命中用于逻辑判断或字符串处理。",
        "Task description annotation context.": "当前命中位于任务描述注解中。",
        "Annotated no change context.": "当前命中已被人工标注为无需修改。",
    },
}

PAGE_SIZES = [10, 100, 500]


def render_report(summary, findings, client_config=None):
    payload = json.dumps({"summary": summary, "findings": findings}, ensure_ascii=False)
    display_maps = json.dumps(DISPLAY_MAPS, ensure_ascii=False)
    page_sizes = json.dumps(PAGE_SIZES, ensure_ascii=False)
    resolved_client_config = {
        "mode": "static",
        "annotation_api_path": "",
        "annotation_remove_api_path": "",
        "readonly_message": "",
        "annotation_path": "",
    }
    if client_config:
        resolved_client_config.update(client_config)
    client_config_payload = json.dumps(resolved_client_config, ensure_ascii=False)

    template = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>中文硬编码盘点报告</title>
  <style>
    :root {
      --bg: #f4efe8;
      --panel: #fffdfa;
      --ink: #1f2328;
      --muted: #6a6f76;
      --line: #d8cbbd;
      --accent: #9f3d2a;
      --accent-soft: #ead6c3;
      --warn: #b36b00;
      --danger: #9d2f2f;
      --ok: #2d6a4f;
      --soft-bg: rgba(255, 255, 255, 0.72);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Iowan Old Style", "Noto Serif SC", serif;
      color: var(--ink);
      overflow: hidden;
      background:
        radial-gradient(circle at top left, rgba(159,61,42,0.12), transparent 32%),
        radial-gradient(circle at top right, rgba(45,106,79,0.10), transparent 28%),
        linear-gradient(180deg, #f8f3ec 0%, var(--bg) 100%);
    }
    h2, h3 { margin: 0; }
    main {
      height: 100vh;
      padding: 28px 32px 40px;
      display: flex;
      gap: 24px;
      align-items: flex-start;
      position: relative;
    }
    .summary-shell {
      width: 360px;
      flex: 0 0 360px;
      position: sticky;
      top: 28px;
      max-height: calc(100vh - 56px);
      overflow: auto;
    }
    .detail-shell {
      flex: 1 1 auto;
      min-width: 0;
      min-height: 0;
      align-self: stretch;
    }
    .summary-panel {
      padding: 16px;
      overflow: hidden;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px 18px;
      box-shadow: 0 10px 30px rgba(64, 47, 30, 0.06);
    }
    .label {
      font-size: 12px;
      letter-spacing: 0.08em;
      color: var(--muted);
      text-transform: none;
    }
    .value { font-size: 28px; margin-top: 10px; }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 18px;
    }
    .detail-shell .panel {
      height: calc(100vh - 68px);
      display: flex;
      flex-direction: column;
      min-height: 0;
    }
    .panel h2 {
      margin: 0 0 14px;
      font-size: 18px;
    }
    .summary-head {
      display: flex;
      align-items: flex-start;
      justify-content: flex-start;
      gap: 16px;
      margin-bottom: 18px;
    }
    .summary-heading h2 {
      margin-top: 4px;
      font-size: 22px;
    }
    .summary-kicker {
      font-size: 11px;
      color: var(--muted);
      letter-spacing: 0.14em;
      text-transform: uppercase;
    }
    .summary-body {
      display: grid;
      gap: 16px;
    }
    .summary-meta {
      display: grid;
      gap: 10px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: linear-gradient(135deg, rgba(159,61,42,0.08), rgba(255,255,255,0.92));
    }
    .summary-meta-row {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
      font-size: 13px;
    }
    .summary-meta-row span {
      color: var(--muted);
      flex-shrink: 0;
    }
    .summary-meta-row strong {
      text-align: right;
      font-weight: 600;
    }
    .summary-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .summary-grid .card {
      padding: 14px 16px;
    }
    .summary-grid .value {
      font-size: 24px;
      margin-top: 8px;
    }
    .summary-section {
      display: grid;
      gap: 10px;
    }
    .summary-section h3 {
      font-size: 16px;
    }
    .summary-skip {
      display: grid;
      gap: 14px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.82);
    }
    .summary-skip-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    .summary-skip-header h3 {
      font-size: 16px;
    }
    .summary-skip-stats {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .summary-skip-item {
      padding: 12px;
      border: 1px solid #eadfd3;
      border-radius: 14px;
      background: rgba(244, 239, 232, 0.65);
    }
    .summary-skip-item span {
      display: block;
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 6px;
    }
    .summary-skip-item strong {
      display: block;
      font-size: 24px;
      line-height: 1.2;
    }
    .metric-list {
      list-style: none;
      padding: 0;
      margin: 0;
      display: grid;
      gap: 10px;
    }
    .metric-list li {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      border-bottom: 1px dashed var(--line);
      padding-bottom: 8px;
    }
    .filters {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-bottom: 16px;
      align-items: center;
    }
    select, input {
      width: 100%;
      padding: 10px 12px;
      border-radius: 12px;
      border: 1px solid var(--line);
      background: #fff;
      font: inherit;
    }
    button {
      padding: 10px 14px;
      border-radius: 12px;
      border: none;
      font: inherit;
      cursor: pointer;
      transition: opacity 0.18s ease, transform 0.18s ease;
    }
    button:hover:not(:disabled) {
      opacity: 0.92;
      transform: translateY(-1px);
    }
    button:disabled {
      cursor: not-allowed;
      opacity: 0.4;
    }
    .export-btn {
      width: 100%;
      background: var(--accent);
      color: #fff;
    }
    .secondary-btn {
      background: var(--soft-bg);
      color: var(--ink);
      border: 1px solid var(--line);
    }
    .table-toolbar {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
      margin-bottom: 12px;
      flex-wrap: wrap;
    }
    .pagination {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .inline-field {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 13px;
      white-space: nowrap;
    }
    .inline-field select,
    .inline-field input {
      width: auto;
      min-width: 86px;
      padding: 8px 10px;
    }
    .page-meta {
      color: var(--muted);
      font-size: 13px;
    }
    .table-wrap {
      flex: 1 1 auto;
      min-height: 0;
      overflow: auto;
      border-radius: 18px;
    }
    .findings-table {
      width: 100%;
      min-width: 1320px;
      border-collapse: collapse;
      table-layout: fixed;
      font-size: 14px;
    }
    .findings-table col.col-project { width: 90px; }
    .findings-table col.col-location { width: 270px; }
    .findings-table col.col-text { width: 360px; }
    .findings-table col.col-category { width: 150px; }
    .findings-table col.col-action { width: 220px; }
    .position-cell {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      width: 100%;
      min-width: 0;
    }
    .path-text {
      flex: 1 1 auto;
      font-family: "SFMono-Regular", "Menlo", monospace;
      font-size: 13px;
      overflow-wrap: anywhere;
      word-break: normal;
      line-height: 1.5;
      min-width: 0;
    }
    .copy-btn {
      width: 32px;
      height: 32px;
      margin-left: auto;
      padding: 0;
      border-radius: 10px;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--muted);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .copy-btn svg {
      width: 16px;
      height: 16px;
    }
    .copy-btn.copied {
      background: var(--accent);
      border-color: var(--accent);
      color: #fff;
    }
    .copy-toast {
      position: fixed;
      right: 24px;
      bottom: 24px;
      padding: 10px 14px;
      border-radius: 12px;
      background: rgba(31, 35, 40, 0.92);
      color: #fff;
      font-size: 13px;
      box-shadow: 0 12px 30px rgba(31, 35, 40, 0.18);
      z-index: 20;
    }
    .copy-toast.is-error {
      background: rgba(157, 47, 47, 0.94);
    }
    th, td {
      text-align: left;
      padding: 10px 8px;
      border-bottom: 1px solid #eadfd3;
      vertical-align: top;
    }
    th {
      color: var(--muted);
      font-size: 12px;
      text-transform: none;
      letter-spacing: 0.06em;
    }
    .findings-table thead th {
      position: sticky;
      top: 0;
      z-index: 1;
      background: var(--panel);
    }
    .pill {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 12px;
      background: var(--accent-soft);
    }
    .pill.fix { background: rgba(157,47,47,0.12); color: var(--danger); }
    .pill.keep { background: rgba(45,106,79,0.12); color: var(--ok); }
    .project-cell,
    .category-cell {
      white-space: nowrap;
      word-break: keep-all;
    }
    .text-cell {
      line-height: 1.65;
      overflow-wrap: anywhere;
    }
    .text-cell {
      font-family: "SFMono-Regular", "Menlo", monospace;
      font-size: 12px;
    }
    .readonly-notice {
      margin: 0 0 12px;
      padding: 10px 12px;
      border-radius: 12px;
      border: 1px solid #eadfd3;
      background: rgba(244, 239, 232, 0.72);
      color: var(--muted);
      font-size: 13px;
      line-height: 1.6;
    }
    .readonly-notice[hidden] {
      display: none;
    }
    .action-cell {
      white-space: normal;
    }
    .action-stack {
      display: grid;
      gap: 8px;
      align-items: flex-start;
    }
    .annotation-row {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .annotation-btn {
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.92);
      color: var(--ink);
      font-size: 12px;
    }
    .annotation-btn.is-danger {
      border-color: rgba(157,47,47,0.24);
      color: var(--danger);
      background: rgba(157,47,47,0.08);
    }
    .annotation-note {
      display: inline-flex;
      align-items: center;
      max-width: 100%;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.5;
      overflow-wrap: anywhere;
    }
    .annotation-note strong {
      font-weight: 600;
      color: var(--ink);
      margin-right: 6px;
    }
    .annotation-dialog {
      width: min(560px, calc(100vw - 32px));
      border: none;
      border-radius: 20px;
      padding: 0;
      background: var(--panel);
      box-shadow: 0 28px 80px rgba(31, 35, 40, 0.24);
    }
    .annotation-dialog::backdrop {
      background: rgba(31, 35, 40, 0.38);
      backdrop-filter: blur(4px);
    }
    .annotation-dialog-panel {
      padding: 24px;
      display: grid;
      gap: 14px;
    }
    .annotation-dialog-actions {
      display: flex;
      justify-content: flex-end;
      gap: 10px;
    }
    .annotation-dialog-path,
    .annotation-dialog-text {
      font-family: "SFMono-Regular", "Menlo", monospace;
      font-size: 12px;
      line-height: 1.6;
      overflow-wrap: anywhere;
      padding: 10px 12px;
      border-radius: 12px;
      background: rgba(244, 239, 232, 0.62);
      border: 1px solid #eadfd3;
    }
    .annotation-dialog textarea {
      width: 100%;
      min-height: 96px;
      resize: vertical;
      padding: 10px 12px;
      border-radius: 12px;
      border: 1px solid var(--line);
      background: #fff;
      font: inherit;
    }
    .skip-dialog {
      width: min(980px, calc(100vw - 48px));
      max-width: 980px;
      padding: 0;
      border: none;
      border-radius: 24px;
      background: var(--panel);
      box-shadow: 0 28px 80px rgba(31, 35, 40, 0.24);
    }
    .skip-dialog::backdrop {
      background: rgba(31, 35, 40, 0.38);
      backdrop-filter: blur(4px);
    }
    .skip-dialog-panel {
      padding: 24px;
      display: grid;
      gap: 18px;
    }
    .skip-dialog-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
    }
    .skip-dialog-header h3 {
      margin-top: 4px;
      font-size: 24px;
    }
    .skip-dialog-meta {
      display: flex;
      gap: 16px;
      flex-wrap: wrap;
      color: var(--muted);
      font-size: 13px;
      margin-top: 10px;
    }
    .skip-chip-list {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }
    .skip-chip {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.92);
      color: var(--ink);
    }
    .skip-chip.is-active {
      background: var(--accent);
      border-color: var(--accent);
      color: #fff;
    }
    .skip-chip strong {
      font-size: 12px;
      font-weight: 600;
    }
    .skip-dialog-table-wrap {
      max-height: 420px;
      overflow: auto;
      border: 1px solid #efe2d4;
      border-radius: 16px;
    }
    .skip-table {
      width: 100%;
      min-width: 720px;
      border-collapse: collapse;
      font-size: 14px;
    }
    .skip-table th {
      position: sticky;
      top: 0;
      background: var(--panel);
      z-index: 1;
    }
    .skip-file-path {
      font-family: "SFMono-Regular", "Menlo", monospace;
      font-size: 13px;
      overflow-wrap: anywhere;
      line-height: 1.6;
    }
    .skip-reason-main {
      font-weight: 600;
      line-height: 1.5;
    }
    .skip-reason-detail {
      margin-top: 4px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.55;
      overflow-wrap: anywhere;
    }
    .skip-nowrap {
      white-space: nowrap;
    }
    .skip-empty {
      text-align: center;
      color: var(--muted);
      padding: 28px 12px;
    }
    .footer {
      color: var(--muted);
      font-size: 12px;
      margin-top: 12px;
    }
    .empty-row {
      text-align: center;
      color: var(--muted);
      padding: 24px 8px;
    }
    @media (max-width: 960px) {
      body {
        overflow: auto;
      }
      main {
        padding-left: 18px;
        padding-right: 18px;
      }
      main {
        display: grid;
        height: auto;
      }
      .summary-shell {
        position: static;
        width: 100%;
        flex-basis: auto;
        max-height: none;
        overflow: visible;
      }
      .detail-shell {
        min-height: auto;
        align-self: auto;
      }
      .panel {
        height: auto;
      }
      .table-wrap {
        flex: initial;
        min-height: auto;
      }
      .table-toolbar { flex-direction: column; align-items: stretch; }
      .pagination { justify-content: flex-start; }
      .skip-dialog {
        width: calc(100vw - 24px);
      }
    }
  </style>
</head>
<body>
  <main>
    <aside class="summary-shell">
      <div class="panel summary-panel">
        <div class="summary-head">
          <div class="summary-heading">
            <div class="summary-kicker">Summary</div>
            <h2>扫描摘要</h2>
          </div>
        </div>
        <div class="summary-body">
          <div class="summary-meta">
            <div class="summary-meta-row">
              <span>扫描批次</span>
              <strong id="summaryRunId"></strong>
            </div>
            <div class="summary-meta-row">
              <span>项目范围</span>
              <strong id="summaryProjects"></strong>
            </div>
            <div class="summary-meta-row">
              <span>处理策略</span>
              <strong>纯规则扫描 + 路径排除策略</strong>
            </div>
          </div>
          <div class="summary-grid" id="cards"></div>
          <div class="summary-skip">
            <div class="summary-skip-header">
              <h3>跳过文件</h3>
              <button id="openSkipDialogBtn" class="secondary-btn" type="button">查看跳过详情</button>
            </div>
            <div class="summary-skip-stats">
              <div class="summary-skip-item">
                <span>已跳过文件</span>
                <strong id="summarySkippedFiles"></strong>
              </div>
              <div class="summary-skip-item">
                <span>策略排除</span>
                <strong id="summaryExcludedFiles"></strong>
              </div>
            </div>
          </div>
          <div class="summary-section">
            <h3>分类分布</h3>
            <ul class="metric-list" id="categoryList"></ul>
          </div>
        </div>
      </div>
    </aside>

    <section class="detail-shell">
      <div class="panel">
      <h2>明细筛选</h2>
      <div class="filters">
        <select id="projectFilter"></select>
        <select id="actionFilter"></select>
        <select id="categoryFilter"></select>
        <select id="langFilter"></select>
        <input id="keywordFilter" placeholder="按文本、路径、分类或标注理由搜索">
        <button id="exportBtn" class="export-btn">导出全部结果到 Excel</button>
      </div>
      <div id="readonlyNotice" class="readonly-notice" hidden></div>
      <div class="table-toolbar">
        <div class="footer" id="resultCount"></div>
        <div class="pagination">
          <label class="inline-field">每页条数
            <select id="pageSizeSelect"></select>
          </label>
          <label class="inline-field">页码
            <input id="pageInput" type="number" min="1" step="1" inputmode="numeric">
          </label>
          <button id="goPageBtn" class="secondary-btn">跳转</button>
          <button id="prevPageBtn" class="secondary-btn">上一页</button>
          <button id="nextPageBtn" class="secondary-btn">下一页</button>
          <span class="page-meta" id="pageInfo"></span>
        </div>
      </div>
      <div class="table-wrap">
        <table class="findings-table">
          <colgroup>
          <col class="col-project">
          <col class="col-location">
          <col class="col-text">
          <col class="col-category">
          <col class="col-action">
          </colgroup>
          <thead>
            <tr>
              <th>项目</th>
              <th>位置</th>
              <th>文本</th>
              <th>分类</th>
              <th>动作</th>
            </tr>
          </thead>
          <tbody id="rows"></tbody>
        </table>
      </div>
      </div>
    </section>
  </main>
  <dialog id="skipDialog" class="skip-dialog">
    <div class="skip-dialog-panel">
      <div class="skip-dialog-header">
        <div>
          <div class="summary-kicker">Skip Details</div>
          <h3>跳过文件详情</h3>
          <div class="skip-dialog-meta">
            <span id="skipDialogTotal"></span>
            <span id="skipDialogExcluded"></span>
          </div>
        </div>
        <button id="closeSkipDialogBtn" class="secondary-btn" type="button">关闭</button>
      </div>
      <div class="skip-chip-list" id="skipReasonChips"></div>
      <div class="skip-dialog-table-wrap">
        <table class="skip-table">
          <thead>
            <tr>
              <th>文件</th>
              <th>原因</th>
              <th>语言</th>
              <th>大小</th>
            </tr>
          </thead>
          <tbody id="skipRows"></tbody>
        </table>
      </div>
    </div>
  </dialog>
  <dialog id="annotationDialog" class="annotation-dialog">
    <div class="annotation-dialog-panel">
      <div>
        <div class="summary-kicker">Annotation</div>
        <h3>标注无需修改</h3>
      </div>
      <div>
        <div class="label">位置</div>
        <div id="annotationDialogPath" class="annotation-dialog-path"></div>
      </div>
      <div>
        <div class="label">文本</div>
        <div id="annotationDialogText" class="annotation-dialog-text"></div>
      </div>
      <label>
        <div class="label">理由（可选）</div>
        <textarea id="annotationReasonInput" placeholder="可填写不需要修改的原因"></textarea>
      </label>
      <div class="annotation-dialog-actions">
        <button id="annotationCancelBtn" class="secondary-btn" type="button">取消</button>
        <button id="annotationSaveBtn" class="export-btn" type="button">保存标注</button>
      </div>
    </div>
  </dialog>
  <div class="copy-toast" id="copyToast" hidden></div>
  <script>
    const payload = __PAYLOAD__;
    const DISPLAY_MAP = __DISPLAY_MAP__;
    const PAGE_SIZES = __PAGE_SIZES__;
    const CLIENT_CONFIG = __CLIENT_CONFIG__;
    let summary = payload.summary;
    let findings = payload.findings.slice();
    const numberFormatter = new Intl.NumberFormat("zh-CN");
    const state = {
      currentPage: 1,
      pageSize: 10,
      skipReasonFilter: "",
      pendingAnnotationId: "",
      filters: {
        project: "",
        action: "fix",
        category: "",
        lang: "",
      },
    };

    const openSkipDialogBtn = document.getElementById("openSkipDialogBtn");
    const skipDialog = document.getElementById("skipDialog");
    const closeSkipDialogBtn = document.getElementById("closeSkipDialogBtn");
    const skipReasonChips = document.getElementById("skipReasonChips");
    const skipRows = document.getElementById("skipRows");
    const projectFilter = document.getElementById("projectFilter");
    const langFilter = document.getElementById("langFilter");
    const categoryFilter = document.getElementById("categoryFilter");
    const actionFilter = document.getElementById("actionFilter");
    const keywordFilter = document.getElementById("keywordFilter");
    const rows = document.getElementById("rows");
    const tableWrap = document.querySelector(".table-wrap");
    const resultCount = document.getElementById("resultCount");
    const pageSizeSelect = document.getElementById("pageSizeSelect");
    const pageInput = document.getElementById("pageInput");
    const pageInfo = document.getElementById("pageInfo");
    const prevPageBtn = document.getElementById("prevPageBtn");
    const nextPageBtn = document.getElementById("nextPageBtn");
    const goPageBtn = document.getElementById("goPageBtn");
    const readonlyNotice = document.getElementById("readonlyNotice");
    const annotationDialog = document.getElementById("annotationDialog");
    const annotationDialogPath = document.getElementById("annotationDialogPath");
    const annotationDialogText = document.getElementById("annotationDialogText");
    const annotationReasonInput = document.getElementById("annotationReasonInput");
    const annotationCancelBtn = document.getElementById("annotationCancelBtn");
    const annotationSaveBtn = document.getElementById("annotationSaveBtn");
    const copyToast = document.getElementById("copyToast");
    let copyToastTimer;

    function toFiniteNumber(value, fallback = 0) {
      const number = Number(value);
      return Number.isFinite(number) ? number : fallback;
    }

    function formatNumber(value) {
      return numberFormatter.format(toFiniteNumber(value));
    }

    function formatPercent(value) {
      return `${(toFiniteNumber(value) * 100).toFixed(1)}%`;
    }

    function formatBytes(value) {
      const size = toFiniteNumber(value);
      if (size <= 0) {
        return "-";
      }
      const units = ["B", "KB", "MB", "GB"];
      let current = size;
      let unitIndex = 0;
      while (current >= 1024 && unitIndex < units.length - 1) {
        current /= 1024;
        unitIndex += 1;
      }
      const digits = current >= 10 || unitIndex === 0 ? 0 : 1;
      return `${current.toFixed(digits)} ${units[unitIndex]}`;
    }

    function labelFor(group, value) {
      if (value === undefined || value === null || value === "") {
        return "";
      }
      const key = String(value);
      const mapping = DISPLAY_MAP[group] || {};
      if (Object.prototype.hasOwnProperty.call(mapping, key)) {
        return mapping[key];
      }
      if (group === "language") {
        return key.toUpperCase();
      }
      return key;
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
    }

    function escapeAttr(value) {
      return escapeHtml(value).replaceAll('"', "&quot;");
    }

    function baseName(path) {
      const normalized = String(path || "").replaceAll("\\\\", "/");
      const parts = normalized.split("/");
      const fileName = parts[parts.length - 1] || normalized;
      const extensionIndex = fileName.lastIndexOf(".");
      return extensionIndex > 0 ? fileName.slice(0, extensionIndex) : fileName;
    }

    function displayPath(item) {
      return item.relative_path || item.path || "";
    }

    function skipDetail(item) {
      return item.skip_detail || "";
    }

    function displaySnippet(item) {
      return item.snippet || item.normalized_text || item.text || "";
    }

    function annotationTooltip(item) {
      const parts = [];
      if (item.original_category) {
        parts.push(`原分类：${labelFor("category", item.original_category)}`);
      }
      if (item.annotation_reason) {
        parts.push(`理由：${item.annotation_reason}`);
      }
      return parts.join("\\n");
    }

    function isReviewMode() {
      return CLIENT_CONFIG.mode === "review";
    }

    function setOptions(select, values, label, group, selectedValue) {
      const unique = [...new Set(values.filter(value => value !== undefined && value !== null && value !== ""))]
        .sort((left, right) => labelFor(group, left).localeCompare(labelFor(group, right), "zh-CN"));
      const resolved = selectedValue && unique.indexOf(selectedValue) === -1 ? "" : (selectedValue || "");
      select.innerHTML = [`<option value="">全部${label}</option>`].concat(
        unique.map(value => `<option value="${escapeAttr(value)}">${escapeHtml(labelFor(group, value))}</option>`)
      ).join("");
      select.value = resolved;
      return resolved;
    }

    function setPageSizeOptions() {
      pageSizeSelect.innerHTML = PAGE_SIZES
        .map(value => {
          return `<option value="${value}" ${value === state.pageSize ? "selected" : ""}>${value} 条</option>`;
        })
        .join("");
    }

    function filterValue(item, key) {
      if (key === "project") return item.project;
      if (key === "action") return item.action;
      if (key === "category") return item.category;
      if (key === "lang") return item.lang;
      return "";
    }

    function matchesFilters(item, excludedKey = "") {
      const keyword = keywordFilter.value.trim().toLowerCase();
      if (excludedKey !== "project" && state.filters.project && item.project !== state.filters.project) return false;
      if (excludedKey !== "action" && state.filters.action && item.action !== state.filters.action) return false;
      if (excludedKey !== "category" && state.filters.category && item.category !== state.filters.category) return false;
      if (excludedKey !== "lang" && state.filters.lang && item.lang !== state.filters.lang) return false;
      if (keyword) {
        const target = `${item.path} ${item.text} ${item.snippet || ""} ${labelFor("category", item.category)} ${labelFor("action", item.action)} ${item.annotation_reason || ""}`.toLowerCase();
        if (!target.includes(keyword)) return false;
      }
      return true;
    }

    function filteredFindings() {
      return findings.filter(item => matchesFilters(item));
    }

    function availableValues(filterKey) {
      return findings
        .filter(item => matchesFilters(item, filterKey))
        .map(item => filterValue(item, filterKey))
        .filter(value => value !== undefined && value !== null && value !== "");
    }

    function renderFilterOptions() {
      const configs = [
        { key: "project", node: projectFilter, label: "项目", group: "project" },
        { key: "action", node: actionFilter, label: "动作", group: "action" },
        { key: "category", node: categoryFilter, label: "分类", group: "category" },
        { key: "lang", node: langFilter, label: "语言", group: "language" },
      ];
      let changed = false;
      let attempts = 0;
      do {
        changed = false;
        configs.forEach(config => {
          const resolved = setOptions(
            config.node,
            availableValues(config.key),
            config.label,
            config.group,
            state.filters[config.key]
          );
          if (resolved !== state.filters[config.key]) {
            state.filters[config.key] = resolved;
            changed = true;
          }
        });
        attempts += 1;
      } while (changed && attempts < 6);
    }

    function paginateFindings(items) {
      const total = items.length;
      const pageSize = state.pageSize;
      const totalPages = Math.max(1, Math.ceil(total / pageSize));
      state.currentPage = Math.min(Math.max(1, state.currentPage), totalPages);
      const startIndex = total === 0 ? 0 : (state.currentPage - 1) * pageSize;
      const endIndex = total === 0 ? 0 : Math.min(startIndex + pageSize, total);
      return {
        items: items.slice(startIndex, endIndex),
        totalPages,
        startIndex,
        endIndex,
      };
    }

    function sortedSkippedFiles() {
      const skippedFiles = (summary.files || []).filter(item => item.skip_reason);
      return skippedFiles.slice().sort((left, right) => {
        const leftReason = labelFor("skip_reason", left.skip_reason);
        const rightReason = labelFor("skip_reason", right.skip_reason);
        const reasonCompare = leftReason.localeCompare(rightReason, "zh-CN");
        if (reasonCompare !== 0) {
          return reasonCompare;
        }
        return displayPath(left).localeCompare(displayPath(right), "zh-CN");
      });
    }

    function filteredSkippedFiles() {
      const items = sortedSkippedFiles();
      if (!state.skipReasonFilter) {
        return items;
      }
      return items.filter(item => item.skip_reason === state.skipReasonFilter);
    }

    function renderSkipReasonChips() {
      const skippedFiles = (summary.files || []).filter(item => item.skip_reason);
      const reasonEntries = Object.entries(summary.skip_reasons || {}).sort((left, right) => {
        if (right[1] !== left[1]) {
          return right[1] - left[1];
        }
        return labelFor("skip_reason", left[0]).localeCompare(labelFor("skip_reason", right[0]), "zh-CN");
      });
      const chips = [
        `<button class="skip-chip ${state.skipReasonFilter ? "" : "is-active"}" type="button" data-reason="">
          <span>全部</span>
          <strong>${formatNumber(skippedFiles.length)}</strong>
        </button>`,
      ].concat(
        reasonEntries.map(([reason, count]) => `
          <button class="skip-chip ${state.skipReasonFilter === reason ? "is-active" : ""}" type="button" data-reason="${escapeAttr(reason)}">
            <span>${escapeHtml(labelFor("skip_reason", reason))}</span>
            <strong>${formatNumber(count)}</strong>
          </button>
        `)
      );
      skipReasonChips.innerHTML = chips.join("");
    }

    function renderSkipRows() {
      const items = filteredSkippedFiles();
      if (items.length === 0) {
        skipRows.innerHTML = '<tr><td colspan="4" class="skip-empty">当前条件下没有跳过文件</td></tr>';
        return;
      }
      skipRows.innerHTML = items.map(item => `
        <tr>
          <td><div class="skip-file-path">${escapeHtml(displayPath(item))}</div></td>
          <td>
            <div class="skip-reason-main">${escapeHtml(labelFor("skip_reason", item.skip_reason))}</div>
            <div class="skip-reason-detail">${escapeHtml(skipDetail(item) || "未提供额外说明。")}</div>
          </td>
          <td class="skip-nowrap">${escapeHtml(labelFor("language", item.lang) || item.lang || "-")}</td>
          <td class="skip-nowrap">${escapeHtml(formatBytes(item.size_bytes))}</td>
        </tr>
      `).join("");
    }

    function openSkipDialog() {
      const skippedFiles = (summary.files || []).filter(item => item.skip_reason);
      if (!skippedFiles.length) {
        return;
      }
      state.skipReasonFilter = "";
      renderSkipReasonChips();
      renderSkipRows();
      if (typeof skipDialog.showModal === "function") {
        skipDialog.showModal();
      } else {
        skipDialog.setAttribute("open", "open");
      }
    }

    function closeSkipDialog() {
      if (typeof skipDialog.close === "function") {
        skipDialog.close();
      } else {
        skipDialog.removeAttribute("open");
      }
    }

    function positionMarkup(item) {
      const fileName = baseName(item.path);
      const location = `${item.path}:${item.line}`;
      return `
        <div class="position-cell">
          <div class="path-text">${escapeHtml(location)}</div>
          <button
            class="copy-btn"
            type="button"
            data-filename="${escapeAttr(fileName)}"
            aria-label="${escapeAttr(`复制文件名 ${fileName}`)}"
            title="${escapeAttr(`复制文件名 ${fileName}`)}"
          >
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <rect x="9" y="9" width="10" height="10" rx="2" stroke="currentColor" stroke-width="1.8"></rect>
              <path d="M15 9V7a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"></path>
            </svg>
          </button>
        </div>
      `;
    }

    function actionMarkup(item) {
      const noteTitle = annotationTooltip(item);
      const note = item.annotated
        ? `<div class="annotation-note"${noteTitle ? ` title="${escapeAttr(noteTitle)}"` : ""}><strong>已标注</strong>${escapeHtml(item.annotation_reason || "无需修改")}</div>`
        : "";

      if (isReviewMode()) {
        if (item.annotated) {
          return `
            <div class="action-stack">
              <span class="pill ${item.action}">${escapeHtml(labelFor("action", item.action))}</span>
              ${note}
              <div class="annotation-row">
                <button class="annotation-btn is-danger" type="button" data-action="remove-annotation" data-id="${escapeAttr(item.id)}">撤销标注</button>
              </div>
            </div>
          `;
        }
        if (item.action === "fix") {
          return `
            <div class="action-stack">
              <span class="pill ${item.action}">${escapeHtml(labelFor("action", item.action))}</span>
              <div class="annotation-row">
                <button class="annotation-btn" type="button" data-action="annotate" data-id="${escapeAttr(item.id)}">标注无需修改</button>
              </div>
            </div>
          `;
        }
      }

      if (item.action === "fix") {
        return `
          <div class="action-stack">
            <span class="pill ${item.action}">${escapeHtml(labelFor("action", item.action))}</span>
            <div class="annotation-row">
              <button class="annotation-btn" type="button" disabled title="${escapeAttr(CLIENT_CONFIG.readonly_message || "请使用 zh-audit review 打开可编辑版本。")}">标注无需修改</button>
            </div>
          </div>
        `;
      }

      return `
        <div class="action-stack">
          <span class="pill ${item.action}">${escapeHtml(labelFor("action", item.action))}</span>
          ${note}
        </div>
      `;
    }

    function renderRows() {
      const current = filteredFindings();
      const page = paginateFindings(current);

      if (current.length === 0) {
        resultCount.textContent = `当前筛选 0 条，共 ${formatNumber(findings.length)} 条`;
        rows.innerHTML = `<tr><td colspan="5" class="empty-row">当前筛选条件下没有命中记录</td></tr>`;
      } else {
        resultCount.textContent =
          `当前筛选 ${formatNumber(current.length)} 条，共 ${formatNumber(findings.length)} 条；本页显示第 ${formatNumber(page.startIndex + 1)} - ${formatNumber(page.endIndex)} 条`;
        rows.innerHTML = page.items.map(item => `
          <tr>
            <td class="project-cell">${escapeHtml(item.project)}</td>
            <td class="location-cell">${positionMarkup(item)}</td>
            <td class="text-cell">${escapeHtml(displaySnippet(item) || "-")}</td>
            <td class="category-cell">${escapeHtml(labelFor("category", item.category))}</td>
            <td class="action-cell">${actionMarkup(item)}</td>
          </tr>
        `).join("");
      }

      pageInput.value = String(state.currentPage);
      pageInfo.textContent = `第 ${formatNumber(state.currentPage)} / ${formatNumber(page.totalPages)} 页`;
      prevPageBtn.disabled = state.currentPage <= 1 || current.length === 0;
      nextPageBtn.disabled = state.currentPage >= page.totalPages || current.length === 0;
    }

    function scrollResultsToTop() {
      if (tableWrap) {
        tableWrap.scrollTop = 0;
      }
      window.scrollTo(0, 0);
    }

    function exportCsv() {
      const current = filteredFindings();
      const headers = ["项目", "位置", "文本", "分类", "动作"];
      const rows = current.map(item => [
        item.project || "",
        `${item.path || ""}:${item.line ?? ""}`,
        displaySnippet(item),
        labelFor("category", item.category),
        labelFor("action", item.action),
      ]);
      const lines = [headers.map(csvEscape).join(",")].concat(rows.map(row => row.map(csvEscape).join(",")));
      const blob = new Blob(["\\ufeff", lines.join("\\n")], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `zh-audit-${summary.run_id}.csv`;
      link.click();
      URL.revokeObjectURL(url);
    }

    function csvEscape(value) {
      const text = String(value ?? "");
      return `"${text.replaceAll('"', '""')}"`;
    }

    function resetAndRender() {
      state.currentPage = 1;
      renderFilterOptions();
      renderRows();
      scrollResultsToTop();
    }

    function goToPage() {
      const value = Number.parseInt(pageInput.value, 10);
      if (Number.isNaN(value)) {
        state.currentPage = 1;
      } else {
        state.currentPage = value;
      }
      renderRows();
      scrollResultsToTop();
    }

    function showCopyToast(message, isError = false) {
      copyToast.hidden = false;
      copyToast.textContent = message;
      copyToast.classList.toggle("is-error", isError);
      window.clearTimeout(copyToastTimer);
      copyToastTimer = window.setTimeout(() => {
        copyToast.hidden = true;
      }, 1400);
    }

    async function copyFileName(fileName, button) {
      try {
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(fileName);
        } else {
          const input = document.createElement("textarea");
          input.value = fileName;
          input.setAttribute("readonly", "readonly");
          input.style.position = "fixed";
          input.style.opacity = "0";
          document.body.appendChild(input);
          input.select();
          document.execCommand("copy");
          document.body.removeChild(input);
        }
        button.classList.add("copied");
        window.setTimeout(() => button.classList.remove("copied"), 1200);
        showCopyToast(`已复制文件名：${fileName}`);
      } catch (error) {
        showCopyToast(`复制失败，请手动记录文件名：${fileName}`, true);
      }
    }

    function renderSummary() {
      const skippedFiles = (summary.files || []).filter(item => item.skip_reason);
      const cards = [
        ["项目数", (summary.scanned_projects || []).length],
        ["已扫描文件", summary.scanned_files],
        ["命中次数", summary.occurrence_count],
        ["未知占比", formatPercent(summary.unknown_rate || 0)],
      ];

      document.getElementById("summaryRunId").textContent = summary.run_id || "-";
      document.getElementById("summaryProjects").textContent =
        (summary.scanned_projects || []).join("、") || "-";
      document.getElementById("summarySkippedFiles").textContent = formatNumber(summary.skipped_files || 0);
      document.getElementById("summaryExcludedFiles").textContent = formatNumber(summary.excluded_files || 0);
      document.getElementById("skipDialogTotal").textContent = `已跳过文件 ${formatNumber(summary.skipped_files || 0)}`;
      document.getElementById("skipDialogExcluded").textContent = `策略排除 ${formatNumber(summary.excluded_files || 0)}`;

      if (!skippedFiles.length) {
        openSkipDialogBtn.disabled = true;
        openSkipDialogBtn.textContent = "暂无跳过文件";
      } else {
        openSkipDialogBtn.disabled = false;
        openSkipDialogBtn.textContent = "查看跳过详情";
        renderSkipReasonChips();
        renderSkipRows();
      }

      document.getElementById("cards").innerHTML = cards.map(([label, value]) => `
        <div class="card">
          <div class="label">${escapeHtml(label)}</div>
          <div class="value">${typeof value === "string" && value.endsWith("%") ? escapeHtml(value) : formatNumber(value)}</div>
        </div>
      `).join("");

      const categoryList = document.getElementById("categoryList");
      categoryList.innerHTML = Object.entries(summary.by_category || {})
        .sort((a, b) => b[1] - a[1])
        .map(([name, count]) => `<li><span>${escapeHtml(labelFor("category", name))}</span><strong>${formatNumber(count)}</strong></li>`)
        .join("");
    }

    function findFinding(id) {
      return findings.find(item => item.id === id) || null;
    }

    function openAnnotationDialog(findingId) {
      const item = findFinding(findingId);
      if (!item || !isReviewMode()) {
        return;
      }
      state.pendingAnnotationId = findingId;
      annotationDialogPath.textContent = `${item.path || ""}:${item.line || ""}`;
      annotationDialogText.textContent = displaySnippet(item) || "-";
      annotationReasonInput.value = item.annotation_reason || "";
      if (typeof annotationDialog.showModal === "function") {
        annotationDialog.showModal();
      } else {
        annotationDialog.setAttribute("open", "open");
      }
    }

    function closeAnnotationDialog() {
      state.pendingAnnotationId = "";
      annotationReasonInput.value = "";
      if (typeof annotationDialog.close === "function") {
        annotationDialog.close();
      } else {
        annotationDialog.removeAttribute("open");
      }
    }

    async function requestAnnotation(path, payload) {
      const response = await fetch(path, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "请求失败");
      }
      return data;
    }

    function applyServerUpdate(data) {
      summary = data.summary || summary;
      if (data.finding && data.finding.id) {
        findings = findings.map(item => item.id === data.finding.id ? data.finding : item);
      }
      renderSummary();
      renderFilterOptions();
      renderRows();
    }

    async function saveAnnotation() {
      if (!state.pendingAnnotationId) {
        return;
      }
      annotationSaveBtn.disabled = true;
      try {
        const data = await requestAnnotation(CLIENT_CONFIG.annotation_api_path, {
          finding_id: state.pendingAnnotationId,
          reason: annotationReasonInput.value.trim(),
        });
        applyServerUpdate(data);
        closeAnnotationDialog();
      } catch (error) {
        showCopyToast(error.message || "保存标注失败", true);
      } finally {
        annotationSaveBtn.disabled = false;
      }
    }

    async function removeAnnotation(findingId) {
      try {
        const data = await requestAnnotation(CLIENT_CONFIG.annotation_remove_api_path, {
          finding_id: findingId,
        });
        applyServerUpdate(data);
      } catch (error) {
        showCopyToast(error.message || "撤销标注失败", true);
      }
    }
    setPageSizeOptions();
    if (CLIENT_CONFIG.readonly_message) {
      readonlyNotice.hidden = false;
      readonlyNotice.textContent = CLIENT_CONFIG.readonly_message;
    }

    [
      ["project", projectFilter],
      ["action", actionFilter],
      ["category", categoryFilter],
      ["lang", langFilter],
    ].forEach(([key, node]) => {
      node.addEventListener("change", () => {
        state.filters[key] = node.value;
        resetAndRender();
      });
    });
    keywordFilter.addEventListener("input", resetAndRender);
    pageSizeSelect.addEventListener("change", () => {
      state.pageSize = Number.parseInt(pageSizeSelect.value, 10) || 10;
      state.currentPage = 1;
      renderRows();
      scrollResultsToTop();
    });
    goPageBtn.addEventListener("click", goToPage);
    pageInput.addEventListener("keydown", event => {
      if (event.key === "Enter") {
        goToPage();
      }
    });
    prevPageBtn.addEventListener("click", () => {
      state.currentPage -= 1;
      renderRows();
      scrollResultsToTop();
    });
    nextPageBtn.addEventListener("click", () => {
      state.currentPage += 1;
      renderRows();
      scrollResultsToTop();
    });
    document.getElementById("exportBtn").addEventListener("click", exportCsv);
    openSkipDialogBtn.addEventListener("click", openSkipDialog);
    closeSkipDialogBtn.addEventListener("click", closeSkipDialog);
    annotationCancelBtn.addEventListener("click", closeAnnotationDialog);
    annotationSaveBtn.addEventListener("click", saveAnnotation);
    skipReasonChips.addEventListener("click", event => {
      const target = event.target instanceof Element ? event.target : null;
      const chip = target ? target.closest(".skip-chip") : null;
      if (!chip) {
        return;
      }
      state.skipReasonFilter = chip.dataset.reason || "";
      renderSkipReasonChips();
      renderSkipRows();
    });
    skipDialog.addEventListener("click", event => {
      const rect = skipDialog.getBoundingClientRect();
      const withinDialog =
        rect.top <= event.clientY &&
        event.clientY <= rect.bottom &&
        rect.left <= event.clientX &&
        event.clientX <= rect.right;
      if (!withinDialog) {
        closeSkipDialog();
      }
    });
    rows.addEventListener("click", event => {
      const target = event.target instanceof Element ? event.target : null;
      const button = target ? target.closest(".copy-btn") : null;
      if (button) {
        copyFileName(button.dataset.filename || "", button);
        return;
      }
      const actionButton = target ? target.closest(".annotation-btn") : null;
      if (!actionButton || actionButton.disabled) {
        return;
      }
      const action = actionButton.dataset.action || "";
      const findingId = actionButton.dataset.id || "";
      if (action == "annotate") {
        openAnnotationDialog(findingId);
      } else if (action == "remove-annotation") {
        removeAnnotation(findingId);
      }
    });
    annotationDialog.addEventListener("click", event => {
      const rect = annotationDialog.getBoundingClientRect();
      const withinDialog =
        rect.top <= event.clientY &&
        event.clientY <= rect.bottom &&
        rect.left <= event.clientX &&
        event.clientX <= rect.right;
      if (!withinDialog) {
        closeAnnotationDialog();
      }
    });

    renderSummary();
    renderFilterOptions();
    renderRows();
  </script>
</body>
</html>"""

    return (
        template.replace("__PAYLOAD__", payload)
        .replace("__DISPLAY_MAP__", display_maps)
        .replace("__PAGE_SIZES__", page_sizes)
        .replace("__CLIENT_CONFIG__", client_config_payload)
    )
