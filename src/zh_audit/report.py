import json


CATEGORY_DISPLAY_PRIORITY = [
    "FIX_REQUIRED_MERGED",
    "COMMENT",
    "LOG_AUDIT_DEBUG",
    "SWAGGER_DOCUMENTATION",
    "TASK_DESCRIPTION",
    "I18N_FILE",
    "DATABASE_SCRIPT",
    "SHELL_SCRIPT",
    "CONDITION_EXPRESSION_LITERAL",
    "ANNOTATED_NO_CHANGE",
    "NAMED_FILE",
    "GENERIC_DOCUMENTATION",
    "TEST_SAMPLE_FIXTURE",
    "UNKNOWN",
]


DISPLAY_MAPS = {
    "category": {
        "FIX_REQUIRED_MERGED": "中文硬编码",
        "USER_VISIBLE_COPY": "用户可见文案",
        "ERROR_VALIDATION_MESSAGE": "错误与校验提示",
        "LOG_AUDIT_DEBUG": "日志打印",
        "COMMENT": "代码注释",
        "SWAGGER_DOCUMENTATION": "Swagger注解",
        "GENERIC_DOCUMENTATION": "普通文档",
        "DATABASE_SCRIPT": "SQL脚本",
        "SHELL_SCRIPT": "Shell脚本",
        "NAMED_FILE": "排除文件",
        "I18N_FILE": "国际化文件",
        "CONDITION_EXPRESSION_LITERAL": "匹配条件",
        "TASK_DESCRIPTION": "ITask注解",
        "ANNOTATED_NO_CHANGE": "历史人工保留",
        "TEST_SAMPLE_FIXTURE": "测试与样例",
        "CONFIG_ITEM": "配置项",
        "PROTOCOL_OR_PERSISTED_LITERAL": "协议/持久化字面量",
        "UNKNOWN": "未知待确认",
    },
    "action": {
        "fix": "需要整改",
        "resolved": "完成整改",
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
        "named_file": "排除文件名",
    },
    "reason": {
        "No strong rule matched.": "没有命中更强的规则，需要人工确认。",
        "Comment context.": "当前命中位于代码注释上下文。",
        "Test/sample path context.": "当前命中位于测试或样例路径上下文。",
        "Logging API context.": "当前命中位于日志打印上下文。",
        "Error/exception context.": "当前命中位于异常或错误处理上下文。",
        "Error semantics in string literal.": "当前命中带有明显错误或校验语义。",
        "Configuration item context.": "当前命中位于配置项上下文。",
        "Markup or front-end text context.": "当前命中位于模板或前端资源上下文。",
        "Looks like protocol or persisted value.": "当前命中看起来像协议值或持久化字面量。",
        "String literal with Chinese text.": "当前命中是包含中文的字符串字面量。",
        "Documentation asset context.": "当前命中位于普通文档资产中。",
        "Database script context.": "当前命中位于 SQL脚本中。",
        "Shell script context.": "当前命中位于 Shell脚本中。",
        "Swagger/OpenAPI annotation context.": "当前命中位于 Swagger注解上下文。",
        "Named file context.": "当前命中位于排除文件中。",
        "I18n messages file context.": "当前命中位于国际化文件中。",
        "Condition expression literal context.": "当前命中用于匹配条件或字符串处理。",
        "Logic processing literal context.": "当前命中用于匹配条件或字符串处理。",
        "Task description annotation context.": "当前命中位于 ITask注解中。",
        "Annotated no change context.": "当前命中来自历史人工保留记录。",
        "Custom keep category rule matched.": "当前命中命中了自定义免改规则。",
    },
}

PAGE_SIZES = [10, 100, 500]


def render_report(summary, findings, client_config=None):
    payload = json.dumps({"summary": summary, "findings": findings}, ensure_ascii=False)
    display_maps = json.dumps(DISPLAY_MAPS, ensure_ascii=False)
    category_display_priority = json.dumps(CATEGORY_DISPLAY_PRIORITY, ensure_ascii=False)
    page_sizes = json.dumps(PAGE_SIZES, ensure_ascii=False)
    resolved_client_config = {"mode": "static"}
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
      --muted: #555b65;
      --line: #d8cbbd;
      --accent: #9f3d2a;
      --accent-soft: #ead6c3;
      --warn: #b36b00;
      --danger: #9d2f2f;
      --ok: #2d6a4f;
      --soft-bg: rgba(255, 255, 255, 0.84);
      --font-ui: "Segoe UI Variable", "Segoe UI", "Microsoft YaHei UI", "PingFang SC", "Hiragino Sans GB", "Noto Sans SC", sans-serif;
      --font-mono: "Cascadia Code", "Consolas", "SFMono-Regular", "Menlo", monospace;
      --text-xs: 12px;
      --text-sm: 13px;
      --text-md: 15px;
      --text-lg: 18px;
      --text-xl: 22px;
      --text-2xl: 32px;
      --text-metric: 28px;
      --text-metric-sm: 24px;
      --leading-tight: 1.3;
      --leading-normal: 1.6;
      --leading-relaxed: 1.65;
      --report-summary-width: 360px;
      --report-text-col-width: 360px;
      --button-pad-y: 10px;
      --button-pad-x: 14px;
      --input-pad-y: 10px;
      --input-pad-x: 12px;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: var(--font-ui);
      font-size: var(--text-md);
      font-weight: 450;
      line-height: var(--leading-normal);
      color: var(--ink);
      overflow: hidden;
      text-rendering: optimizeLegibility;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
      background:
        radial-gradient(circle at top left, rgba(159,61,42,0.12), transparent 32%),
        radial-gradient(circle at top right, rgba(45,106,79,0.10), transparent 28%),
        linear-gradient(180deg, #f8f3ec 0%, var(--bg) 100%);
    }
    h2, h3 {
      margin: 0;
      font-family: var(--font-ui);
      line-height: var(--leading-tight);
      color: var(--ink);
    }
    main {
      height: 100vh;
      padding: 28px 32px 40px;
      display: flex;
      gap: 24px;
      align-items: flex-start;
      position: relative;
    }
    .summary-shell {
      width: var(--report-summary-width);
      flex: 0 0 var(--report-summary-width);
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
      font-size: var(--text-xs);
      font-weight: 500;
      letter-spacing: 0.08em;
      color: var(--muted);
      text-transform: none;
    }
    .value {
      font-size: var(--text-metric);
      font-weight: 650;
      line-height: 1.1;
      margin-top: 10px;
    }
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
      font-size: var(--text-lg);
      font-weight: 600;
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
      font-size: var(--text-xl);
      font-weight: 650;
    }
    .summary-kicker {
      font-size: var(--text-xs);
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
      font-size: var(--text-sm);
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
      font-size: var(--text-metric-sm);
      margin-top: 8px;
    }
    .summary-section {
      display: grid;
      gap: 10px;
    }
    .summary-section h3 {
      font-size: var(--text-lg);
      font-weight: 600;
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
      font-size: var(--text-lg);
      font-weight: 600;
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
      font-size: var(--text-xs);
      color: var(--muted);
      margin-bottom: 6px;
    }
    .summary-skip-item strong {
      display: block;
      font-size: var(--text-metric-sm);
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
      padding: var(--input-pad-y) var(--input-pad-x);
      border-radius: 12px;
      border: 1px solid var(--line);
      background: #fff;
      font: inherit;
    }
    select {
      appearance: none;
      -webkit-appearance: none;
      -moz-appearance: none;
      padding-right: calc(var(--input-pad-x) + 34px);
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 14 14' fill='none'%3E%3Cpath d='M3.25 5.5 7 9.25l3.75-3.75' stroke='%23555b65' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
      background-repeat: no-repeat;
      background-position: right 14px center;
      background-size: 14px 14px;
    }
    select::-ms-expand {
      display: none;
    }
    select option,
    select optgroup {
      padding: 8px 12px;
      min-height: 34px;
      line-height: 1.8;
    }
    button {
      padding: var(--button-pad-y) var(--button-pad-x);
      border-radius: 12px;
      border: none;
      font: inherit;
      font-weight: 500;
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
      font-size: var(--text-sm);
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
      font-size: var(--text-sm);
    }
    .table-wrap {
      flex: 1 1 auto;
      min-height: 0;
      overflow: auto;
      border-radius: 18px;
    }
    .findings-table {
      width: 100%;
      min-width: 1540px;
      border-collapse: collapse;
      table-layout: fixed;
      font-size: var(--text-md);
    }
    .findings-table col.col-sequence { width: 84px; }
    .findings-table col.col-project { width: 90px; }
    .findings-table col.col-location { width: 270px; }
    .findings-table col.col-text { width: var(--report-text-col-width); }
    .findings-table col.col-category { width: 150px; }
    .findings-table col.col-action { width: 140px; }
    .findings-table col.col-operation { width: 160px; }
    .sequence-cell {
      white-space: nowrap;
      color: var(--muted);
      font-variant-numeric: tabular-nums;
    }
    .position-cell {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      width: 100%;
      min-width: 0;
    }
    .path-text {
      flex: 0 1 auto;
      max-width: calc(100% - 42px);
      font-family: var(--font-mono);
      font-size: var(--text-sm);
      overflow-wrap: anywhere;
      word-break: normal;
      line-height: 1.5;
      min-width: 0;
      text-align: center;
    }
    .copy-btn {
      width: 32px;
      height: 32px;
      margin-left: 0;
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
      font-size: var(--text-sm);
      box-shadow: 0 12px 30px rgba(31, 35, 40, 0.18);
      z-index: 20;
    }
    .copy-toast.is-error {
      background: rgba(157, 47, 47, 0.94);
    }
    th, td {
      text-align: center;
      padding: 10px 8px;
      border-bottom: 1px solid #eadfd3;
      vertical-align: middle;
    }
    th {
      color: var(--muted);
      font-size: var(--text-xs);
      font-weight: 500;
      text-transform: none;
      letter-spacing: 0.06em;
    }
    .findings-table thead th {
      position: sticky;
      top: 0;
      z-index: 1;
      background: var(--panel);
    }
    .sort-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      width: 100%;
      padding: 0;
      border: none;
      background: transparent;
      color: inherit;
      font: inherit;
      letter-spacing: inherit;
    }
    .sort-btn:hover:not(:disabled) {
      transform: none;
      opacity: 1;
      color: var(--ink);
    }
    .sort-btn.is-active {
      color: var(--ink);
    }
    .sort-indicator {
      min-width: 1.2em;
      color: var(--accent);
      font-size: var(--text-xs);
      text-align: center;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: fit-content;
      max-width: 100%;
      align-self: flex-start;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: var(--text-xs);
      font-weight: 500;
      background: var(--accent-soft);
      white-space: nowrap;
    }
    .pill.fix { background: rgba(157,47,47,0.12); color: var(--danger); }
    .pill.resolved { background: rgba(45,106,79,0.18); color: var(--ok); }
    .pill.keep { background: rgba(45,106,79,0.12); color: var(--ok); }
    .project-cell,
    .category-cell {
      white-space: nowrap;
      word-break: keep-all;
    }
    .sequence-cell,
    .project-cell,
    .location-cell,
    .category-cell,
    .action-cell,
    .operation-cell {
      vertical-align: middle;
    }
    .text-cell {
      line-height: 1.65;
      overflow-wrap: anywhere;
      text-align: center;
    }
    .text-cell {
      font-family: var(--font-mono);
      font-size: var(--text-xs);
    }
    .action-cell {
      white-space: normal;
    }
    .operation-cell {
      white-space: nowrap;
    }
    .action-stack {
      display: flex;
      flex-wrap: wrap;
      gap: 8px 10px;
      align-items: center;
      justify-content: center;
    }
    .action-stack > .pill {
      order: 0;
    }
    .operation-placeholder {
      color: var(--muted);
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
      font-size: var(--text-xl);
      font-weight: 650;
    }
    .skip-dialog-meta {
      display: flex;
      gap: 16px;
      flex-wrap: wrap;
      color: var(--muted);
      font-size: var(--text-sm);
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
      font-size: var(--text-xs);
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
      font-size: var(--text-md);
    }
    .skip-table th {
      position: sticky;
      top: 0;
      background: var(--panel);
      z-index: 1;
    }
    .skip-file-path {
      font-family: var(--font-mono);
      font-size: var(--text-sm);
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
      font-size: var(--text-xs);
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
      font-size: var(--text-xs);
      margin-top: 12px;
    }
    .empty-row {
      text-align: center;
      color: var(--muted);
      padding: 24px 8px;
    }
    @media (min-width: 1920px) {
      :root {
        --muted: #4d535d;
        --text-xs: 13px;
        --text-sm: 14px;
        --text-md: 16px;
        --text-lg: 20px;
        --text-xl: 24px;
        --text-2xl: 36px;
        --text-metric: 32px;
        --text-metric-sm: 28px;
        --report-summary-width: 420px;
        --report-text-col-width: 420px;
        --button-pad-y: 12px;
        --button-pad-x: 16px;
        --input-pad-y: 12px;
        --input-pad-x: 14px;
      }
    }
    @media (min-width: 2560px) {
      :root {
        --muted: #434952;
        --text-xs: 14px;
        --text-sm: 15px;
        --text-md: 17px;
        --text-lg: 20px;
        --text-xl: 24px;
        --text-2xl: 36px;
        --text-metric: 34px;
        --text-metric-sm: 30px;
        --report-summary-width: 480px;
        --report-text-col-width: 480px;
        --button-pad-y: 13px;
        --button-pad-x: 18px;
        --input-pad-y: 13px;
        --input-pad-x: 16px;
      }
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
        <input id="keywordFilter" placeholder="按文本、文件路径或分类搜索">
        <button id="exportBtn" class="export-btn">导出全部结果到 Excel</button>
      </div>
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
          <col class="col-sequence">
          <col class="col-project">
          <col class="col-location">
          <col class="col-text">
          <col class="col-category">
          <col class="col-action">
          <col class="col-operation">
          </colgroup>
          <thead>
            <tr>
              <th>行号</th>
              <th>项目</th>
              <th>
                <button class="sort-btn" type="button" data-sort-key="location" aria-pressed="false">
                  <span>文件路径</span>
                  <span class="sort-indicator" aria-hidden="true">↕</span>
                </button>
              </th>
              <th>
                <button class="sort-btn" type="button" data-sort-key="text" aria-pressed="true">
                  <span>文本</span>
                  <span class="sort-indicator" aria-hidden="true">↑</span>
                </button>
              </th>
              <th>分类</th>
              <th>动作</th>
              <th>操作</th>
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
  <div class="copy-toast" id="copyToast" hidden></div>
  <script>
    const payload = __PAYLOAD__;
    const DISPLAY_MAP = __DISPLAY_MAP__;
    const PAGE_SIZES = __PAGE_SIZES__;
    const CATEGORY_DISPLAY_PRIORITY = __CATEGORY_DISPLAY_PRIORITY__;
    const CLIENT_CONFIG = __CLIENT_CONFIG__;
    const FIX_REQUIRED_CATEGORY = "FIX_REQUIRED_MERGED";
    let summary = payload.summary;
    let findings = normalizeFindings(payload.findings);
    const numberFormatter = new Intl.NumberFormat("zh-CN");
    const state = {
      currentPage: 1,
      pageSize: 10,
      skipReasonFilter: "",
      sort: {
        key: "text",
        direction: "asc",
      },
      filters: {
        project: "",
        action: "fix",
        category: FIX_REQUIRED_CATEGORY,
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
    const sortButtons = Array.from(document.querySelectorAll(".sort-btn[data-sort-key]"));
    const resultCount = document.getElementById("resultCount");
    const pageSizeSelect = document.getElementById("pageSizeSelect");
    const pageInput = document.getElementById("pageInput");
    const pageInfo = document.getElementById("pageInfo");
    const prevPageBtn = document.getElementById("prevPageBtn");
    const nextPageBtn = document.getElementById("nextPageBtn");
    const goPageBtn = document.getElementById("goPageBtn");
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

    function categoryPriority(value) {
      const key = String(value || "");
      const index = CATEGORY_DISPLAY_PRIORITY.indexOf(key);
      return index >= 0 ? index : CATEGORY_DISPLAY_PRIORITY.length + 100;
    }

    function compareDisplayValue(group, left, right) {
      if (group === "category") {
        const priorityGap = categoryPriority(left) - categoryPriority(right);
        if (priorityGap !== 0) {
          return priorityGap;
        }
      }
      return labelFor(group, left).localeCompare(labelFor(group, right), "zh-CN");
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
    }

    function escapeAttr(value) {
      return escapeHtml(value).replace(/"/g, "&quot;");
    }

    function baseName(path) {
      const normalized = String(path || "").replace(/\\\\/g, "/");
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

    function normalizeSequence(item, index) {
      const sequence = Number.parseInt(item && item.sequence, 10);
      return Number.isFinite(sequence) && sequence > 0 ? sequence : index + 1;
    }

    function normalizeFindings(items) {
      return Array.isArray(items)
        ? items.map((item, index) => Object.assign({}, item || {}, { sequence: normalizeSequence(item, index) }))
        : [];
    }

    function effectiveCategory(item) {
      if (item && (item.action === "fix" || item.action === "resolved")) {
        return FIX_REQUIRED_CATEGORY;
      }
      return item.category || "";
    }

    function effectiveCategoryLabel(item) {
      return labelFor("category", effectiveCategory(item));
    }

    function effectiveCategoryCounts() {
      const counts = {};
      findings.forEach(item => {
        const key = effectiveCategory(item);
        if (!key) {
          return;
        }
        counts[key] = (counts[key] || 0) + 1;
      });
      return counts;
    }

    function setOptions(select, values, label, group, selectedValue) {
      const unique = [...new Set(values.filter(value => value !== undefined && value !== null && value !== ""))]
        .sort((left, right) => compareDisplayValue(group, left, right));
      const resolved = selectedValue && unique.indexOf(selectedValue) === -1 ? "" : (selectedValue || "");
      select.innerHTML = [`<option value="">全部${label}</option>`].concat(
        unique.map(value => `<option value="${escapeAttr(value)}">${escapeHtml(labelFor(group, value))}</option>`)
      ).join("");
      select.value = resolved;
      return resolved;
    }

    function setSingleOption(select, value, group) {
      select.innerHTML = `<option value="${escapeAttr(value)}">${escapeHtml(labelFor(group, value))}</option>`;
      select.value = value;
      return value;
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
      if (key === "category") return effectiveCategory(item);
      if (key === "lang") return item.lang;
      return "";
    }

    function matchesFilters(item, excludedKey = "") {
      const keyword = keywordFilter.value.trim().toLowerCase();
      if (excludedKey !== "project" && state.filters.project && item.project !== state.filters.project) return false;
      if (excludedKey !== "action" && state.filters.action) {
        if (state.filters.action === "fix" && item.action !== "fix" && item.action !== "resolved") return false;
        if (state.filters.action === "keep" && item.action !== "keep") return false;
      }
      if (excludedKey !== "category" && state.filters.category && effectiveCategory(item) !== state.filters.category) return false;
      if (excludedKey !== "lang" && state.filters.lang && item.lang !== state.filters.lang) return false;
      if (keyword) {
        const target = `${item.path} ${item.text} ${item.snippet || ""} ${effectiveCategoryLabel(item)} ${labelFor("action", item.action)}`.toLowerCase();
        if (!target.includes(keyword)) return false;
      }
      return true;
    }

    function filteredFindings() {
      return findings
        .filter(item => matchesFilters(item))
        .slice()
        .sort(compareFindings);
    }

    function sequenceValue(item) {
      return Number.parseInt(item && item.sequence, 10) || 0;
    }

    function compareSequence(left, right) {
      const sequenceGap = sequenceValue(left) - sequenceValue(right);
      if (sequenceGap !== 0) {
        return sequenceGap;
      }
      return String((left && left.id) || "").localeCompare(String((right && right.id) || ""), "zh-CN");
    }

    function compareLocation(left, right) {
      const pathCompare = displayPath(left).localeCompare(displayPath(right), "zh-CN");
      if (pathCompare !== 0) {
        return pathCompare;
      }
      const lineCompare = toFiniteNumber(left && left.line, 0) - toFiniteNumber(right && right.line, 0);
      if (lineCompare !== 0) {
        return lineCompare;
      }
      const columnCompare = toFiniteNumber(left && left.column, 0) - toFiniteNumber(right && right.column, 0);
      if (columnCompare !== 0) {
        return columnCompare;
      }
      const projectCompare = String((left && left.project) || "").localeCompare(
        String((right && right.project) || ""),
        "zh-CN"
      );
      if (projectCompare !== 0) {
        return projectCompare;
      }
      return compareSequence(left, right);
    }

    function compareText(left, right) {
      const textCompare = displaySnippet(left).localeCompare(displaySnippet(right), "zh-CN");
      if (textCompare !== 0) {
        return textCompare;
      }
      return compareLocation(left, right);
    }

    function compareFindings(left, right) {
      const comparator = state.sort.key === "location" ? compareLocation : compareText;
      const result = comparator(left, right);
      if (result !== 0) {
        return state.sort.direction === "desc" ? -result : result;
      }
      return compareSequence(left, right);
    }

    function renderSortButtons() {
      sortButtons.forEach(button => {
        const isActive = button.dataset.sortKey === state.sort.key;
        const indicator = button.querySelector(".sort-indicator");
        button.classList.toggle("is-active", isActive);
        button.setAttribute("aria-pressed", isActive ? "true" : "false");
        if (indicator) {
          indicator.textContent = isActive ? (state.sort.direction === "asc" ? "↑" : "↓") : "↕";
        }
      });
    }

    function toggleSort(sortKey) {
      if (!sortKey) {
        return;
      }
      if (state.sort.key === sortKey) {
        state.sort.direction = state.sort.direction === "asc" ? "desc" : "asc";
      } else {
        state.sort.key = sortKey;
        state.sort.direction = "asc";
      }
      state.currentPage = 1;
      renderRows();
      scrollResultsToTop();
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
        { key: "lang", node: langFilter, label: "语言", group: "language" },
      ];
      renderActionFilterOptions();
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
        const resolvedCategory = renderCategoryFilterOptions();
        if (resolvedCategory !== state.filters.category) {
          state.filters.category = resolvedCategory;
          changed = true;
        }
        attempts += 1;
      } while (changed && attempts < 6);
    }

    function renderActionFilterOptions() {
      const options = [
        { value: "fix", label: "需要整改" },
        { value: "keep", label: "无需整改" },
      ];
      const resolved = options.some(option => option.value === state.filters.action) ? state.filters.action : "fix";
      actionFilter.innerHTML = options.map(option => `<option value="${option.value}" ${option.value === resolved ? "selected" : ""}>${option.label}</option>`).join("");
      state.filters.action = resolved;
    }

    function renderCategoryFilterOptions() {
      if (state.filters.action === "fix") {
        return setSingleOption(categoryFilter, FIX_REQUIRED_CATEGORY, "category");
      }
      const selectedValue = state.filters.category === FIX_REQUIRED_CATEGORY ? "" : state.filters.category;
      return setOptions(categoryFilter, availableValues("category"), "分类", "category", selectedValue);
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
      return `
        <div class="action-stack">
          <span class="pill ${item.action}">${escapeHtml(labelFor("action", item.action))}</span>
        </div>
      `;
    }

    function operationMarkup() {
      return '<span class="operation-placeholder">-</span>';
    }

    function renderRows() {
      const current = filteredFindings();
      const page = paginateFindings(current);
      renderSortButtons();

      if (current.length === 0) {
        resultCount.textContent = `当前筛选 0 条，共 ${formatNumber(findings.length)} 条`;
        rows.innerHTML = `<tr><td colspan="7" class="empty-row">当前筛选条件下没有命中记录</td></tr>`;
      } else {
        resultCount.textContent =
          `当前筛选 ${formatNumber(current.length)} 条，共 ${formatNumber(findings.length)} 条；本页显示第 ${formatNumber(page.startIndex + 1)} - ${formatNumber(page.endIndex)} 条`;
        rows.innerHTML = page.items.map((item, index) => `
          <tr>
            <td class="sequence-cell">${formatNumber(page.startIndex + index + 1)}</td>
            <td class="project-cell">${escapeHtml(item.project)}</td>
            <td class="location-cell">${positionMarkup(item)}</td>
            <td class="text-cell">${escapeHtml(displaySnippet(item) || "-")}</td>
            <td class="category-cell">${escapeHtml(effectiveCategoryLabel(item))}</td>
            <td class="action-cell">${actionMarkup(item)}</td>
            <td class="operation-cell">${operationMarkup(item)}</td>
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
      const headers = ["行号", "项目", "文件路径", "文本", "分类", "动作"];
      const rows = current.map((item, index) => [
        index + 1,
        item.project || "",
        `${item.path || ""}:${item.line ?? ""}`,
        displaySnippet(item),
        effectiveCategoryLabel(item),
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
      return `"${text.replace(/"/g, '""')}"`;
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
      categoryList.innerHTML = Object.entries(effectiveCategoryCounts())
        .sort((a, b) => (b[1] - a[1]) || compareDisplayValue("category", a[0], b[0]))
        .map(([name, count]) => `<li><span>${escapeHtml(labelFor("category", name))}</span><strong>${formatNumber(count)}</strong></li>`)
        .join("");
    }

    setPageSizeOptions();

    [
      ["project", projectFilter],
      ["category", categoryFilter],
      ["lang", langFilter],
    ].forEach(([key, node]) => {
      node.addEventListener("change", () => {
        state.filters[key] = node.value;
        resetAndRender();
      });
    });
    actionFilter.addEventListener("change", () => {
      state.filters.action = actionFilter.value;
      state.filters.category = state.filters.action === "fix" ? FIX_REQUIRED_CATEGORY : "";
      resetAndRender();
    });
    sortButtons.forEach(button => {
      button.addEventListener("click", () => {
        toggleSort(button.dataset.sortKey || "");
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
    });

    renderSummary();
    renderFilterOptions();
    renderRows();
  </script>
</body>
</html>"""

    return (
        template.replace("__DISPLAY_MAP__", display_maps, 1)
        .replace("__CATEGORY_DISPLAY_PRIORITY__", category_display_priority, 1)
        .replace("__PAGE_SIZES__", page_sizes, 1)
        .replace("__CLIENT_CONFIG__", client_config_payload, 1)
        .replace("__PAYLOAD__", payload, 1)
    )
