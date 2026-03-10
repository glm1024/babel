from __future__ import annotations

import json


DISPLAY_MAPS = {
    "category": {
        "USER_VISIBLE_COPY": "用户可见文案",
        "ERROR_VALIDATION_MESSAGE": "错误与校验提示",
        "LOG_AUDIT_DEBUG": "日志审计与调试",
        "COMMENT_DOCUMENTATION": "注释与文档",
        "TEST_SAMPLE_FIXTURE": "测试与样例",
        "CONFIG_METADATA": "配置与元数据",
        "PROTOCOL_OR_PERSISTED_LITERAL": "协议或持久化字面量",
        "UNKNOWN": "未知待确认",
    },
    "action": {
        "fix": "需要整改",
        "review": "需要复核",
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
    },
    "reason": {
        "No strong rule matched.": "没有命中更强的规则，需要人工确认。",
        "Comment or documentation context.": "当前命中位于注释或文档上下文。",
        "Test/sample path context.": "当前命中位于测试或样例路径上下文。",
        "Logging API context.": "当前命中位于日志接口上下文。",
        "Error/exception context.": "当前命中位于异常或错误处理上下文。",
        "Error semantics in string literal.": "当前命中带有明显错误或校验语义。",
        "Configuration or metadata file.": "当前命中位于配置或元数据文件中。",
        "Markup or front-end text context.": "当前命中位于模板或前端资源上下文。",
        "Looks like protocol or persisted value.": "当前命中看起来像协议值或持久化字面量。",
        "String literal with Chinese text.": "当前命中是包含中文的字符串字面量。",
        "SQL or documentation asset.": "当前命中位于 SQL 或文档资产中。",
    },
}

PAGE_SIZES = [20, 50, 100, 200]


def render_report(summary: dict, findings: list[dict]) -> str:
    payload = json.dumps({"summary": summary, "findings": findings}, ensure_ascii=False)
    display_maps = json.dumps(DISPLAY_MAPS, ensure_ascii=False)
    page_sizes = json.dumps(PAGE_SIZES, ensure_ascii=False)

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
      background:
        radial-gradient(circle at top left, rgba(159,61,42,0.12), transparent 32%),
        radial-gradient(circle at top right, rgba(45,106,79,0.10), transparent 28%),
        linear-gradient(180deg, #f8f3ec 0%, var(--bg) 100%);
    }
    h2, h3 { margin: 0; }
    main {
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
    }
    .detail-shell {
      flex: 1 1 auto;
      min-width: 0;
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
      overflow-x: auto;
      border-radius: 18px;
    }
    .findings-table {
      width: 100%;
      min-width: 1160px;
      border-collapse: collapse;
      table-layout: fixed;
      font-size: 14px;
    }
    .findings-table col.col-project { width: 90px; }
    .findings-table col.col-location { width: 270px; }
    .findings-table col.col-category { width: 150px; }
    .findings-table col.col-action { width: 120px; }
    .findings-table col.col-reason { width: 300px; }
    .position-cell {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      min-width: 0;
    }
    .path-text {
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
    .pill {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 12px;
      background: var(--accent-soft);
    }
    .pill.fix { background: rgba(157,47,47,0.12); color: var(--danger); }
    .pill.review { background: rgba(179,107,0,0.12); color: var(--warn); }
    .pill.keep { background: rgba(45,106,79,0.12); color: var(--ok); }
    .pill.high-risk { background: rgba(157,47,47,0.15); color: var(--danger); margin-left: 8px; }
    .project-cell,
    .category-cell,
    .action-cell {
      white-space: nowrap;
      word-break: keep-all;
    }
    .text-cell strong,
    .reason-cell {
      display: block;
      line-height: 1.65;
      overflow-wrap: anywhere;
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
      main {
        padding-left: 18px;
        padding-right: 18px;
      }
      main {
        display: grid;
      }
      .summary-shell {
        position: static;
        width: 100%;
        flex-basis: auto;
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
        <select id="langFilter"></select>
        <select id="categoryFilter"></select>
        <select id="actionFilter"></select>
        <input id="keywordFilter" placeholder="按文本、路径或原因搜索">
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
            <col class="col-project">
            <col class="col-location">
            <col class="col-text">
            <col class="col-category">
            <col class="col-action">
            <col class="col-reason">
          </colgroup>
          <thead>
            <tr>
              <th>项目</th>
              <th>位置</th>
              <th>文本</th>
              <th>分类</th>
              <th>动作</th>
              <th>说明</th>
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
    const summary = payload.summary;
    const findings = payload.findings;
    const numberFormatter = new Intl.NumberFormat("zh-CN");
    const skippedFiles = (summary.files || []).filter(item => item.skip_reason);
    const state = {
      currentPage: 1,
      pageSize: 20,
      skipReasonFilter: "",
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
      return parts[parts.length - 1] || normalized;
    }

    function displayPath(item) {
      return item.relative_path || item.path || "";
    }

    function skipDetail(item) {
      return item.skip_detail || "";
    }

    function setOptions(select, values, label, group) {
      const unique = [...new Set(values.filter(value => value !== undefined && value !== null && value !== ""))]
        .sort((left, right) => labelFor(group, left).localeCompare(labelFor(group, right), "zh-CN"));
      select.innerHTML = [`<option value="">全部${label}</option>`].concat(
        unique.map(value => `<option value="${escapeAttr(value)}">${escapeHtml(labelFor(group, value))}</option>`)
      ).join("");
    }

    function setPageSizeOptions() {
      pageSizeSelect.innerHTML = PAGE_SIZES
        .map(value => `<option value="${value}" ${value === state.pageSize ? "selected" : ""}>${value} 条</option>`)
        .join("");
    }

    function filteredFindings() {
      const keyword = keywordFilter.value.trim().toLowerCase();
      return findings.filter(item => {
        if (projectFilter.value && item.project !== projectFilter.value) return false;
        if (langFilter.value && item.lang !== langFilter.value) return false;
        if (categoryFilter.value && item.category !== categoryFilter.value) return false;
        if (actionFilter.value && item.action !== actionFilter.value) return false;
        if (keyword) {
          const target = `${item.path} ${item.text} ${item.reason}`.toLowerCase();
          if (!target.includes(keyword)) return false;
        }
        return true;
      });
    }

    function paginateFindings(items) {
      const total = items.length;
      const totalPages = Math.max(1, Math.ceil(total / state.pageSize));
      state.currentPage = Math.min(Math.max(1, state.currentPage), totalPages);
      const startIndex = total === 0 ? 0 : (state.currentPage - 1) * state.pageSize;
      const endIndex = total === 0 ? 0 : Math.min(startIndex + state.pageSize, total);
      return {
        items: items.slice(startIndex, endIndex),
        totalPages,
        startIndex,
        endIndex,
      };
    }

    function sortedSkippedFiles() {
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

    function renderRows() {
      const current = filteredFindings();
      const page = paginateFindings(current);

      if (current.length === 0) {
        resultCount.textContent = `当前筛选 0 条，共 ${formatNumber(findings.length)} 条`;
        rows.innerHTML = `<tr><td colspan="6" class="empty-row">当前筛选条件下没有命中记录</td></tr>`;
      } else {
        resultCount.textContent =
          `当前筛选 ${formatNumber(current.length)} 条，共 ${formatNumber(findings.length)} 条；本页显示第 ${formatNumber(page.startIndex + 1)} - ${formatNumber(page.endIndex)} 条`;
        rows.innerHTML = page.items.map(item => `
          <tr>
            <td class="project-cell">${escapeHtml(item.project)}</td>
            <td class="location-cell">${positionMarkup(item)}</td>
            <td class="text-cell"><strong>${escapeHtml(item.normalized_text || item.text)}</strong></td>
            <td class="category-cell">${escapeHtml(labelFor("category", item.category))}${item.high_risk ? '<span class="pill high-risk">高风险</span>' : ""}</td>
            <td class="action-cell"><span class="pill ${item.action}">${escapeHtml(labelFor("action", item.action))}</span></td>
            <td class="reason-cell">${escapeHtml(labelFor("reason", item.reason) || item.reason || "-")}</td>
          </tr>
        `).join("");
      }

      pageInput.value = String(state.currentPage);
      pageInfo.textContent = `第 ${formatNumber(state.currentPage)} / ${formatNumber(page.totalPages)} 页`;
      prevPageBtn.disabled = state.currentPage <= 1 || current.length === 0;
      nextPageBtn.disabled = state.currentPage >= page.totalPages || current.length === 0;
    }

    function exportCsv() {
      const current = filteredFindings();
      const headers = ["项目", "位置", "文本", "分类", "动作", "说明"];
      const rows = current.map(item => [
        item.project || "",
        `${item.path || ""}:${item.line ?? ""}`,
        item.normalized_text || item.text || "",
        labelFor("category", item.category),
        labelFor("action", item.action),
        labelFor("reason", item.reason) || item.reason || "-",
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
      renderRows();
    }

    function goToPage() {
      const value = Number.parseInt(pageInput.value, 10);
      if (Number.isNaN(value)) {
        state.currentPage = 1;
      } else {
        state.currentPage = value;
      }
      renderRows();
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

    setOptions(projectFilter, findings.map(item => item.project), "项目", "project");
    setOptions(langFilter, findings.map(item => item.lang), "语言", "language");
    setOptions(categoryFilter, findings.map(item => item.category), "分类", "category");
    setOptions(actionFilter, findings.map(item => item.action), "动作", "action");
    setPageSizeOptions();

    [projectFilter, langFilter, categoryFilter, actionFilter].forEach(node => {
      node.addEventListener("change", resetAndRender);
    });
    keywordFilter.addEventListener("input", resetAndRender);
    pageSizeSelect.addEventListener("change", () => {
      state.pageSize = Number.parseInt(pageSizeSelect.value, 10) || 20;
      state.currentPage = 1;
      renderRows();
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
    });
    nextPageBtn.addEventListener("click", () => {
      state.currentPage += 1;
      renderRows();
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
      if (!button) {
        return;
      }
      copyFileName(button.dataset.filename || "", button);
    });

    renderRows();
  </script>
</body>
</html>"""

    return (
        template.replace("__PAYLOAD__", payload)
        .replace("__DISPLAY_MAP__", display_maps)
        .replace("__PAGE_SIZES__", page_sizes)
    )
