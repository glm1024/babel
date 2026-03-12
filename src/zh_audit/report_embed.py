import json

from zh_audit.report import CATEGORY_DISPLAY_PRIORITY, DISPLAY_MAPS, PAGE_SIZES


REPORT_COMPONENT_STYLE = """
:host {
  display: block;
}
* { box-sizing: border-box; }
h2, h3 { margin: 0; }
[data-report-root] {
  display: flex;
  gap: 24px;
  align-items: flex-start;
  min-height: 0;
  padding: 0;
}
.summary-shell {
  width: 360px;
  flex: 0 0 360px;
  position: sticky;
  top: 0;
  max-height: calc(100vh - 120px);
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
  background: var(--panel, #fffdfa);
  border: 1px solid var(--line, #d8cbbd);
  border-radius: 18px;
  padding: 16px 18px;
  box-shadow: 0 10px 30px rgba(64, 47, 30, 0.06);
}
.label {
  font-size: 12px;
  letter-spacing: 0.08em;
  color: var(--muted, #6a6f76);
  text-transform: none;
}
.value { font-size: 28px; margin-top: 10px; }
.panel {
  background: var(--panel, #fffdfa);
  border: 1px solid var(--line, #d8cbbd);
  border-radius: 20px;
  padding: 18px;
}
.detail-shell .panel {
  height: calc(100vh - 164px);
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
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
  color: var(--muted, #6a6f76);
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
  border: 1px solid var(--line, #d8cbbd);
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
  color: var(--muted, #6a6f76);
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
  border: 1px solid var(--line, #d8cbbd);
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
  color: var(--muted, #6a6f76);
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
  border-bottom: 1px dashed var(--line, #d8cbbd);
  padding-bottom: 8px;
}
.filters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
  align-items: center;
}
select, input, textarea, button {
  font: inherit;
}
select, input {
  width: 100%;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid var(--line, #d8cbbd);
  background: #fff;
}
select option,
select optgroup {
  padding: 4px 10px;
  line-height: 1.5;
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
  background: var(--accent, #9f3d2a);
  color: #fff;
}
.secondary-btn {
  background: rgba(255, 255, 255, 0.72);
  color: var(--ink, #1f2328);
  border: 1px solid var(--line, #d8cbbd);
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
  color: var(--muted, #6a6f76);
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
  color: var(--muted, #6a6f76);
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
  min-width: 1540px;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 14px;
}
.findings-table col.col-sequence { width: 84px; }
.findings-table col.col-project { width: 90px; }
.findings-table col.col-location { width: 270px; }
.findings-table col.col-text { width: 360px; }
.findings-table col.col-category { width: 150px; }
.findings-table col.col-action { width: 140px; }
.findings-table col.col-operation { width: 160px; }
.sequence-cell {
  white-space: nowrap;
  color: var(--muted, #6a6f76);
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
  font-family: "SFMono-Regular", "Menlo", monospace;
  font-size: 13px;
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
  border: 1px solid var(--line, #d8cbbd);
  background: #fff;
  color: var(--muted, #6a6f76);
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
  background: var(--accent, #9f3d2a);
  border-color: var(--accent, #9f3d2a);
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
  text-align: center;
  padding: 10px 8px;
  border-bottom: 1px solid #eadfd3;
  vertical-align: middle;
}
th {
  color: var(--muted, #6a6f76);
  font-size: 12px;
  text-transform: none;
  letter-spacing: 0.06em;
}
.findings-table thead th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: var(--panel, #fffdfa);
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
  color: var(--ink, #1f2328);
}
.sort-btn.is-active {
  color: var(--ink, #1f2328);
}
.sort-indicator {
  min-width: 1.2em;
  color: var(--accent, #9f3d2a);
  font-size: 11px;
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
  font-size: 12px;
  background: var(--accent-soft, #ead6c3);
  white-space: nowrap;
}
.pill.fix { background: rgba(157,47,47,0.12); color: var(--danger, #9d2f2f); }
.pill.resolved { background: rgba(45,106,79,0.18); color: var(--ok, #2d6a4f); }
.pill.keep { background: rgba(45,106,79,0.12); color: var(--ok, #2d6a4f); }
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
  font-family: "SFMono-Regular", "Menlo", monospace;
  font-size: 12px;
  text-align: center;
}
.action-cell {
  white-space: normal;
  min-width: 0;
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
  width: 100%;
  min-width: 0;
}
.action-stack > .pill {
  order: 0;
}
.operation-placeholder {
  color: var(--muted, #6a6f76);
}
.row-action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 94px;
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid var(--line, #d8cbbd);
  background: rgba(255, 255, 255, 0.92);
  color: var(--ink, #1f2328);
  font-size: 12px;
  line-height: 1.2;
}
.row-action-btn.resolve {
  border-color: rgba(157, 47, 47, 0.22);
  background: rgba(157, 47, 47, 0.06);
  color: var(--danger, #9d2f2f);
}
.row-action-btn.reopen {
  border-color: rgba(45, 106, 79, 0.22);
  background: rgba(45, 106, 79, 0.08);
  color: var(--ok, #2d6a4f);
}
.row-action-btn:hover:not(:disabled) {
  transform: translateY(-1px);
}
.skip-dialog {
  width: min(980px, calc(100vw - 48px));
  max-width: 980px;
  padding: 0;
  border: none;
  border-radius: 24px;
  background: var(--panel, #fffdfa);
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
  color: var(--muted, #6a6f76);
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
  border: 1px solid var(--line, #d8cbbd);
  background: rgba(255, 255, 255, 0.92);
  color: var(--ink, #1f2328);
}
.skip-chip.is-active {
  background: var(--accent, #9f3d2a);
  border-color: var(--accent, #9f3d2a);
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
  background: var(--panel, #fffdfa);
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
  color: var(--muted, #6a6f76);
  font-size: 12px;
  line-height: 1.55;
  overflow-wrap: anywhere;
}
.skip-nowrap {
  white-space: nowrap;
}
.skip-empty {
  text-align: center;
  color: var(--muted, #6a6f76);
  padding: 28px 12px;
}
.footer {
  color: var(--muted, #6a6f76);
  font-size: 12px;
  margin-top: 12px;
}
.empty-row {
  text-align: center;
  color: var(--muted, #6a6f76);
  padding: 24px 8px;
}
[data-report-root][data-layout="embedded"] {
  display: grid;
  grid-template-columns: minmax(320px, 360px) minmax(0, 1fr);
  gap: 24px;
  align-items: stretch;
  min-height: 0;
  height: 100%;
}
[data-report-root][data-layout="embedded"] .summary-shell {
  position: sticky;
  top: 0;
  width: 100%;
  flex: initial;
  align-self: start;
  max-height: 100%;
  overflow: auto;
}
[data-report-root][data-layout="embedded"] .detail-shell {
  align-self: stretch;
  min-height: 0;
  height: 100%;
}
[data-report-root][data-layout="embedded"] .detail-shell .panel {
  height: 100%;
  min-height: 0;
  overflow: hidden;
}
[data-report-root][data-layout="embedded"] .table-wrap {
  overflow: auto;
  min-height: 0;
}
@media (max-width: 1180px) {
  [data-report-root][data-layout="embedded"] {
    grid-template-columns: 1fr;
    height: auto;
  }
  [data-report-root][data-layout="embedded"] .summary-shell {
    position: static;
    max-height: none;
    overflow: visible;
  }
  [data-report-root][data-layout="embedded"] .detail-shell {
    height: auto;
  }
  [data-report-root][data-layout="embedded"] .detail-shell .panel {
    height: auto;
    overflow: visible;
  }
  [data-report-root][data-layout="embedded"] .table-wrap {
    overflow: visible;
    min-height: auto;
  }
}
@media (max-width: 960px) {
  [data-report-root] {
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
  .table-toolbar {
    flex-direction: column;
    align-items: stretch;
  }
  .pagination {
    justify-content: flex-start;
  }
  .skip-dialog {
    width: calc(100vw - 24px);
  }
}
"""


REPORT_COMPONENT_MARKUP = """
<main id="reportMain" data-report-root data-layout="standalone">
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
        <input id="keywordFilter" placeholder="按文本、路径或分类搜索">
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
          <button id="goPageBtn" class="secondary-btn" type="button">跳转</button>
          <button id="prevPageBtn" class="secondary-btn" type="button">上一页</button>
          <button id="nextPageBtn" class="secondary-btn" type="button">下一页</button>
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
                  <span>位置</span>
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
"""


REPORT_COMPONENT_BUNDLE_TEMPLATE = """
(function () {
  if (window.ZhAuditReport) {
    return;
  }

  const REPORT_STYLE = __REPORT_STYLE__;
  const REPORT_MARKUP = __REPORT_MARKUP__;
  const DISPLAY_MAP = __DISPLAY_MAP__;
  const PAGE_SIZES = __PAGE_SIZES__;
  const CATEGORY_DISPLAY_PRIORITY = __CATEGORY_DISPLAY_PRIORITY__;
  const DEFAULT_CLIENT_CONFIG = __CLIENT_CONFIG__;

  function getById(root, id) {
    if (typeof root.getElementById === "function") {
      return root.getElementById(id);
    }
    return root.querySelector("#" + id);
  }

  function mount(host, payload, clientConfig, options) {
    if (!host) {
      return null;
    }
    const normalizedOptions = Object.assign({ shadow: false, embedded: false }, options || {});
    const root = normalizedOptions.shadow ? (host.shadowRoot || host.attachShadow({ mode: "open" })) : host;
    let controller = host.__zhAuditReportController;
    if (!controller || controller.root !== root) {
      root.innerHTML = "<style>" + REPORT_STYLE + "</style>" + REPORT_MARKUP;
      controller = createController(host, root);
      host.__zhAuditReportController = controller;
    }
    controller.update(payload || {}, clientConfig || {}, normalizedOptions);
    return controller;
  }

  function createController(host, root) {
    let summary = {};
    let findings = [];
    let currentClientConfig = Object.assign({}, DEFAULT_CLIENT_CONFIG);
    let currentOptions = { shadow: false, embedded: false };
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
        category: "",
        lang: "",
      },
    };

    const reportMain = getById(root, "reportMain");
    const openSkipDialogBtn = getById(root, "openSkipDialogBtn");
    const skipDialog = getById(root, "skipDialog");
    const closeSkipDialogBtn = getById(root, "closeSkipDialogBtn");
    const skipReasonChips = getById(root, "skipReasonChips");
    const skipRows = getById(root, "skipRows");
    const projectFilter = getById(root, "projectFilter");
    const langFilter = getById(root, "langFilter");
    const categoryFilter = getById(root, "categoryFilter");
    const actionFilter = getById(root, "actionFilter");
    const keywordFilter = getById(root, "keywordFilter");
    const rows = getById(root, "rows");
    const tableWrap = root.querySelector(".table-wrap");
    const sortButtons = Array.prototype.slice.call(root.querySelectorAll(".sort-btn[data-sort-key]"));
    const resultCount = getById(root, "resultCount");
    const pageSizeSelect = getById(root, "pageSizeSelect");
    const pageInput = getById(root, "pageInput");
    const pageInfo = getById(root, "pageInfo");
    const prevPageBtn = getById(root, "prevPageBtn");
    const nextPageBtn = getById(root, "nextPageBtn");
    const goPageBtn = getById(root, "goPageBtn");
    const copyToast = getById(root, "copyToast");
    const summaryRunId = getById(root, "summaryRunId");
    const summaryProjects = getById(root, "summaryProjects");
    const summarySkippedFiles = getById(root, "summarySkippedFiles");
    const summaryExcludedFiles = getById(root, "summaryExcludedFiles");
    const skipDialogTotal = getById(root, "skipDialogTotal");
    const skipDialogExcluded = getById(root, "skipDialogExcluded");
    const cards = getById(root, "cards");
    const categoryList = getById(root, "categoryList");
    let copyToastTimer;
    let listenersBound = false;

    function toFiniteNumber(value, fallback) {
      const number = Number(value);
      return Number.isFinite(number) ? number : fallback;
    }

    function formatNumber(value) {
      return numberFormatter.format(toFiniteNumber(value, 0));
    }

    function formatPercent(value) {
      return (toFiniteNumber(value, 0) * 100).toFixed(1) + "%";
    }

    function formatBytes(value) {
      const size = toFiniteNumber(value, 0);
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
      return current.toFixed(digits) + " " + units[unitIndex];
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
      return String(value == null ? "" : value)
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
        ? items.map(function (item, index) {
            return Object.assign({}, item || {}, { sequence: normalizeSequence(item, index) });
          })
        : [];
    }

    function effectiveCategory(item) {
      if (item && (item.action === "fix" || item.action === "resolved")) {
        return "FIX_REQUIRED_MERGED";
      }
      return item.category || "";
    }

    function effectiveCategoryLabel(item) {
      return labelFor("category", effectiveCategory(item));
    }

    function effectiveCategoryCounts() {
      const counts = {};
      findings.forEach(function (item) {
        const key = effectiveCategory(item);
        if (!key) {
          return;
        }
        counts[key] = (counts[key] || 0) + 1;
      });
      return counts;
    }

    function setOptions(select, values, label, group, selectedValue) {
      const unique = Array.from(new Set(values.filter(function (value) {
        return value !== undefined && value !== null && value !== "";
      }))).sort(function (left, right) {
        return compareDisplayValue(group, left, right);
      });
      const resolved = selectedValue && unique.indexOf(selectedValue) === -1 ? "" : (selectedValue || "");
      select.innerHTML = ['<option value="">全部' + label + "</option>"].concat(
        unique.map(function (value) {
          return '<option value="' + escapeAttr(value) + '">' + escapeHtml(labelFor(group, value)) + "</option>";
        })
      ).join("");
      select.value = resolved;
      return resolved;
    }

    function setPageSizeOptions() {
      pageSizeSelect.innerHTML = PAGE_SIZES.map(function (value) {
        return '<option value="' + value + '"' + (value === state.pageSize ? " selected" : "") + ">" + value + " 条</option>";
      }).join("");
    }

    function filterValue(item, key) {
      if (key === "project") return item.project;
      if (key === "action") return item.action;
      if (key === "category") return effectiveCategory(item);
      if (key === "lang") return item.lang;
      return "";
    }

    function matchesFilters(item, excludedKey) {
      const keyword = keywordFilter.value.trim().toLowerCase();
      if (excludedKey !== "project" && state.filters.project && item.project !== state.filters.project) return false;
      if (excludedKey !== "action" && state.filters.action) {
        if (state.filters.action === "fix" && item.action !== "fix" && item.action !== "resolved") return false;
        if (state.filters.action === "keep" && item.action !== "keep") return false;
      }
      if (excludedKey !== "category" && state.filters.category && effectiveCategory(item) !== state.filters.category) return false;
      if (excludedKey !== "lang" && state.filters.lang && item.lang !== state.filters.lang) return false;
      if (keyword) {
        const target = [item.path, item.text, item.snippet || "", effectiveCategoryLabel(item), labelFor("action", item.action)]
          .join(" ")
          .toLowerCase();
        if (target.indexOf(keyword) === -1) return false;
      }
      return true;
    }

    function filteredFindings() {
      return findings
        .filter(function (item) {
          return matchesFilters(item, "");
        })
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
      sortButtons.forEach(function (button) {
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
        .filter(function (item) { return matchesFilters(item, filterKey); })
        .map(function (item) { return filterValue(item, filterKey); })
        .filter(function (value) { return value !== undefined && value !== null && value !== ""; });
    }

    function renderFilterOptions() {
      const configs = [
        { key: "project", node: projectFilter, label: "项目", group: "project" },
        { key: "category", node: categoryFilter, label: "分类", group: "category" },
        { key: "lang", node: langFilter, label: "语言", group: "language" }
      ];
      let changed = false;
      let attempts = 0;
      do {
        changed = false;
        configs.forEach(function (config) {
          const resolved = setOptions(config.node, availableValues(config.key), config.label, config.group, state.filters[config.key]);
          if (resolved !== state.filters[config.key]) {
            state.filters[config.key] = resolved;
            changed = true;
          }
        });
        attempts += 1;
      } while (changed && attempts < 6);
      renderActionFilterOptions();
    }

    function renderActionFilterOptions() {
      const options = [
        { value: "fix", label: "需要整改" },
        { value: "keep", label: "无需整改" }
      ];
      const resolved = options.some(function (option) {
        return option.value === state.filters.action;
      })
        ? state.filters.action
        : "fix";
      actionFilter.innerHTML = options.map(function (option) {
        return '<option value="' + option.value + '"' + (option.value === resolved ? " selected" : "") + ">" + option.label + "</option>";
      }).join("");
      state.filters.action = resolved;
    }

    function paginateFindings(items) {
      const total = items.length;
      const totalPages = Math.max(1, Math.ceil(total / state.pageSize));
      state.currentPage = Math.min(Math.max(1, state.currentPage), totalPages);
      const startIndex = total === 0 ? 0 : (state.currentPage - 1) * state.pageSize;
      const endIndex = total === 0 ? 0 : Math.min(startIndex + state.pageSize, total);
      return {
        items: items.slice(startIndex, endIndex),
        totalPages: totalPages,
        startIndex: startIndex,
        endIndex: endIndex
      };
    }

    function sortedSkippedFiles() {
      const skippedFiles = (summary.files || []).filter(function (item) { return item.skip_reason; });
      return skippedFiles.slice().sort(function (left, right) {
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
      return items.filter(function (item) {
        return item.skip_reason === state.skipReasonFilter;
      });
    }

    function renderSkipReasonChips() {
      const skippedFiles = (summary.files || []).filter(function (item) { return item.skip_reason; });
      const reasonEntries = Object.entries(summary.skip_reasons || {}).sort(function (left, right) {
        if (right[1] !== left[1]) {
          return right[1] - left[1];
        }
        return labelFor("skip_reason", left[0]).localeCompare(labelFor("skip_reason", right[0]), "zh-CN");
      });
      const chips = ['<button class="skip-chip ' + (state.skipReasonFilter ? "" : "is-active") + '" type="button" data-reason=""><span>全部</span><strong>' + formatNumber(skippedFiles.length) + "</strong></button>"]
        .concat(reasonEntries.map(function (entry) {
          const reason = entry[0];
          const count = entry[1];
          return '<button class="skip-chip ' + (state.skipReasonFilter === reason ? "is-active" : "") + '" type="button" data-reason="' + escapeAttr(reason) + '"><span>' + escapeHtml(labelFor("skip_reason", reason)) + "</span><strong>" + formatNumber(count) + "</strong></button>";
        }));
      skipReasonChips.innerHTML = chips.join("");
    }

    function renderSkipRows() {
      const items = filteredSkippedFiles();
      if (!items.length) {
        skipRows.innerHTML = '<tr><td colspan="4" class="skip-empty">当前条件下没有跳过文件</td></tr>';
        return;
      }
      skipRows.innerHTML = items.map(function (item) {
        return '<tr><td><div class="skip-file-path">' + escapeHtml(displayPath(item)) + '</div></td><td><div class="skip-reason-main">' + escapeHtml(labelFor("skip_reason", item.skip_reason)) + '</div><div class="skip-reason-detail">' + escapeHtml(skipDetail(item) || "未提供额外说明。") + '</div></td><td class="skip-nowrap">' + escapeHtml(labelFor("language", item.lang) || item.lang || "-") + '</td><td class="skip-nowrap">' + escapeHtml(formatBytes(item.size_bytes)) + "</td></tr>";
      }).join("");
    }

    function openSkipDialog() {
      const skippedFiles = (summary.files || []).filter(function (item) { return item.skip_reason; });
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
      const location = (item.path || "") + ":" + (item.line || "");
      return '<div class="position-cell"><div class="path-text">' + escapeHtml(location) + '</div><button class="copy-btn" type="button" data-filename="' + escapeAttr(fileName) + '" aria-label="' + escapeAttr("复制文件名 " + fileName) + '" title="' + escapeAttr("复制文件名 " + fileName) + '"><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="9" y="9" width="10" height="10" rx="2" stroke="currentColor" stroke-width="1.8"></rect><path d="M15 9V7a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"></path></svg></button></div>';
    }

    function actionMarkup(item) {
      return '<div class="action-stack"><span class="pill ' + item.action + '">' + escapeHtml(labelFor("action", item.action)) + "</span></div>";
    }

    function operationMarkup(item) {
      if (!isInteractiveMode()) {
        return '<span class="operation-placeholder">-</span>';
      }
      if (item.action === "fix" && currentClientConfig.finding_resolve_api_path) {
        return '<button class="row-action-btn resolve" type="button" data-action="resolve-finding" data-id="' + escapeAttr(item.id) + '">标记已整改</button>';
      }
      if (item.action === "resolved" && currentClientConfig.finding_reopen_api_path) {
        return '<button class="row-action-btn reopen" type="button" data-action="reopen-finding" data-id="' + escapeAttr(item.id) + '">重新打开</button>';
      }
      return '<span class="operation-placeholder">-</span>';
    }

    function renderRows() {
      const current = filteredFindings();
      const page = paginateFindings(current);
      renderSortButtons();

      if (current.length === 0) {
        resultCount.textContent = "当前筛选 0 条，共 " + formatNumber(findings.length) + " 条";
        rows.innerHTML = '<tr><td colspan="7" class="empty-row">当前筛选条件下没有命中记录</td></tr>';
      } else {
        resultCount.textContent = "当前筛选 " + formatNumber(current.length) + " 条，共 " + formatNumber(findings.length) + " 条；本页显示第 " + formatNumber(page.startIndex + 1) + " - " + formatNumber(page.endIndex) + " 条";
        rows.innerHTML = page.items.map(function (item, index) {
          return '<tr><td class="sequence-cell">' + formatNumber(page.startIndex + index + 1) + '</td><td class="project-cell">' + escapeHtml(item.project) + '</td><td class="location-cell">' + positionMarkup(item) + '</td><td class="text-cell">' + escapeHtml(displaySnippet(item) || "-") + '</td><td class="category-cell">' + escapeHtml(effectiveCategoryLabel(item)) + '</td><td class="action-cell">' + actionMarkup(item) + '</td><td class="operation-cell">' + operationMarkup(item) + "</td></tr>";
        }).join("");
      }

      pageInput.value = String(state.currentPage);
      pageInfo.textContent = "第 " + formatNumber(state.currentPage) + " / " + formatNumber(page.totalPages) + " 页";
      prevPageBtn.disabled = state.currentPage <= 1 || current.length === 0;
      nextPageBtn.disabled = state.currentPage >= page.totalPages || current.length === 0;
    }

    function scrollResultsToTop() {
      if (tableWrap) {
        tableWrap.scrollTop = 0;
      }
      if (!currentOptions.embedded && typeof window.scrollTo === "function") {
        window.scrollTo(0, 0);
      }
    }

    function csvEscape(value) {
      const text = String(value == null ? "" : value);
      return '"' + text.replace(/"/g, '""') + '"';
    }

    function exportCsv() {
      const current = filteredFindings();
      const headers = ["行号", "项目", "位置", "文本", "分类", "动作"];
      const csvRows = current.map(function (item, index) {
        return [
          index + 1,
          item.project || "",
          (item.path || "") + ":" + (item.line == null ? "" : item.line),
          displaySnippet(item),
          effectiveCategoryLabel(item),
          labelFor("action", item.action)
        ];
      });
      const lines = [headers.map(csvEscape).join(",")].concat(csvRows.map(function (row) {
        return row.map(csvEscape).join(",");
      }));
      const blob = new Blob(["\\ufeff", lines.join("\\n")], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "zh-audit-" + (summary.run_id || "report") + ".csv";
      link.click();
      URL.revokeObjectURL(url);
    }

    function resetAndRender() {
      state.currentPage = 1;
      renderFilterOptions();
      renderRows();
      scrollResultsToTop();
    }

    function goToPage() {
      const value = Number.parseInt(pageInput.value, 10);
      state.currentPage = Number.isNaN(value) ? 1 : value;
      renderRows();
      scrollResultsToTop();
    }

    function showCopyToast(message, isError) {
      copyToast.hidden = false;
      copyToast.textContent = message;
      copyToast.classList.toggle("is-error", !!isError);
      window.clearTimeout(copyToastTimer);
      copyToastTimer = window.setTimeout(function () {
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
        window.setTimeout(function () {
          button.classList.remove("copied");
        }, 1200);
        showCopyToast("已复制文件名：" + fileName, false);
      } catch (error) {
        showCopyToast("复制失败，请手动记录文件名：" + fileName, true);
      }
    }

    function isInteractiveMode() {
      return currentClientConfig.mode === "serve";
    }

    async function requestServerUpdate(path, payload) {
      const response = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload || {})
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "请求失败");
      }
      return data;
    }

    function applyServerUpdate(data) {
      summary = data.summary || summary;
      if (Array.isArray(data.findings)) {
        findings = normalizeFindings(data.findings);
      }
      renderSummary();
      renderFilterOptions();
      renderRows();
      host.dispatchEvent(new CustomEvent("zh-audit-report-updated", {
        detail: {
          summary: summary,
          findings: findings.slice(),
          has_results: !!data.has_results,
          results_revision: data.results_revision
        },
        bubbles: true,
        composed: true
      }));
    }

    async function resolveFinding(findingId) {
      const data = await requestServerUpdate(currentClientConfig.finding_resolve_api_path, {
        finding_id: findingId
      });
      applyServerUpdate(data);
    }

    async function reopenFinding(findingId) {
      const data = await requestServerUpdate(currentClientConfig.finding_reopen_api_path, {
        finding_id: findingId
      });
      applyServerUpdate(data);
    }

    function renderSummary() {
      const skippedFiles = (summary.files || []).filter(function (item) { return item.skip_reason; });
      const cardsData = [
        ["项目数", (summary.scanned_projects || []).length],
        ["已扫描文件", summary.scanned_files],
        ["命中次数", summary.occurrence_count],
        ["未知占比", formatPercent(summary.unknown_rate || 0)]
      ];

      summaryRunId.textContent = summary.run_id || "-";
      summaryProjects.textContent = (summary.scanned_projects || []).join("、") || "-";
      summarySkippedFiles.textContent = formatNumber(summary.skipped_files || 0);
      summaryExcludedFiles.textContent = formatNumber(summary.excluded_files || 0);
      skipDialogTotal.textContent = "已跳过文件 " + formatNumber(summary.skipped_files || 0);
      skipDialogExcluded.textContent = "策略排除 " + formatNumber(summary.excluded_files || 0);

      if (!skippedFiles.length) {
        openSkipDialogBtn.disabled = true;
        openSkipDialogBtn.textContent = "暂无跳过文件";
      } else {
        openSkipDialogBtn.disabled = false;
        openSkipDialogBtn.textContent = "查看跳过详情";
        renderSkipReasonChips();
        renderSkipRows();
      }

      cards.innerHTML = cardsData.map(function (entry) {
        const label = entry[0];
        const value = entry[1];
        const rendered = typeof value === "string" && /%$/.test(value) ? escapeHtml(value) : formatNumber(value);
        return '<div class="card"><div class="label">' + escapeHtml(label) + '</div><div class="value">' + rendered + "</div></div>";
      }).join("");

      categoryList.innerHTML = Object.entries(effectiveCategoryCounts())
        .sort(function (left, right) {
          return (right[1] - left[1]) || compareDisplayValue("category", left[0], right[0]);
        })
        .map(function (entry) {
          return "<li><span>" + escapeHtml(labelFor("category", entry[0])) + "</span><strong>" + formatNumber(entry[1]) + "</strong></li>";
        })
        .join("");
    }

    function bindListeners() {
      if (listenersBound) {
        return;
      }
      listenersBound = true;
      [
        ["project", projectFilter],
        ["category", categoryFilter],
        ["lang", langFilter]
      ].forEach(function (entry) {
        const key = entry[0];
        const node = entry[1];
        node.addEventListener("change", function () {
          state.filters[key] = node.value;
          resetAndRender();
        });
      });
      actionFilter.addEventListener("change", function () {
        state.filters.action = actionFilter.value;
        resetAndRender();
      });
      sortButtons.forEach(function (button) {
        button.addEventListener("click", function () {
          toggleSort(button.dataset.sortKey || "");
        });
      });
      keywordFilter.addEventListener("input", resetAndRender);
      pageSizeSelect.addEventListener("change", function () {
        state.pageSize = Number.parseInt(pageSizeSelect.value, 10) || 10;
        state.currentPage = 1;
        renderRows();
        scrollResultsToTop();
      });
      goPageBtn.addEventListener("click", goToPage);
      pageInput.addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
          goToPage();
        }
      });
      prevPageBtn.addEventListener("click", function () {
        state.currentPage -= 1;
        renderRows();
        scrollResultsToTop();
      });
      nextPageBtn.addEventListener("click", function () {
        state.currentPage += 1;
        renderRows();
        scrollResultsToTop();
      });
      getById(root, "exportBtn").addEventListener("click", exportCsv);
      openSkipDialogBtn.addEventListener("click", openSkipDialog);
      closeSkipDialogBtn.addEventListener("click", closeSkipDialog);
      skipReasonChips.addEventListener("click", function (event) {
        const target = event.target instanceof Element ? event.target : null;
        const chip = target ? target.closest(".skip-chip") : null;
        if (!chip) {
          return;
        }
        state.skipReasonFilter = chip.dataset.reason || "";
        renderSkipReasonChips();
        renderSkipRows();
      });
      skipDialog.addEventListener("click", function (event) {
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
      rows.addEventListener("click", async function (event) {
        const target = event.target instanceof Element ? event.target : null;
        const button = target ? target.closest(".copy-btn") : null;
        if (button) {
          copyFileName(button.dataset.filename || "", button);
          return;
        }
        const actionButton = target ? target.closest(".row-action-btn[data-action]") : null;
        if (!actionButton) {
          return;
        }
        const findingId = actionButton.dataset.id || "";
        actionButton.disabled = true;
        try {
          if (actionButton.dataset.action === "resolve-finding") {
            await resolveFinding(findingId);
            return;
          }
          if (actionButton.dataset.action === "reopen-finding") {
            await reopenFinding(findingId);
          }
        } catch (error) {
          showCopyToast(error.message || "更新整改状态失败", true);
        } finally {
          actionButton.disabled = false;
        }
      });
    }

    function update(payload, clientConfig, options) {
      currentClientConfig = Object.assign({}, DEFAULT_CLIENT_CONFIG, clientConfig || {});
      currentOptions = Object.assign({}, currentOptions, options || {});
      summary = payload.summary || {};
      findings = normalizeFindings(payload.findings);
      reportMain.dataset.layout = currentOptions.embedded ? "embedded" : "standalone";
      setPageSizeOptions();
      renderSummary();
      renderFilterOptions();
      renderRows();
      bindListeners();
    }

    return {
      root: root,
      update: update
    };
  }

  window.ZhAuditReport = {
    mount: mount
  };
})();
"""


def render_report_component_bundle():
    bundle = REPORT_COMPONENT_BUNDLE_TEMPLATE
    bundle = bundle.replace("__REPORT_STYLE__", json.dumps(REPORT_COMPONENT_STYLE, ensure_ascii=False))
    bundle = bundle.replace("__REPORT_MARKUP__", json.dumps(REPORT_COMPONENT_MARKUP, ensure_ascii=False))
    bundle = bundle.replace("__DISPLAY_MAP__", json.dumps(DISPLAY_MAPS, ensure_ascii=False))
    bundle = bundle.replace("__CATEGORY_DISPLAY_PRIORITY__", json.dumps(CATEGORY_DISPLAY_PRIORITY, ensure_ascii=False))
    bundle = bundle.replace("__PAGE_SIZES__", json.dumps(PAGE_SIZES, ensure_ascii=False))
    bundle = bundle.replace(
        "__CLIENT_CONFIG__",
        json.dumps(
            {
                "mode": "serve",
                "finding_resolve_api_path": "",
                "finding_reopen_api_path": "",
            },
            ensure_ascii=False,
        ),
    )
    return bundle
