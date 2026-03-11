import json

from zh_audit.report import DISPLAY_MAPS


def render_app_shell(bootstrap_payload, client_config):
    payload = json.dumps(bootstrap_payload, ensure_ascii=False)
    display_maps = json.dumps(DISPLAY_MAPS, ensure_ascii=False)
    config_payload = json.dumps(client_config, ensure_ascii=False)
    template = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>中文硬编码盘点服务</title>
  <style>
    :root {
      --bg: #f4efe8;
      --panel: #fffdfa;
      --ink: #1f2328;
      --muted: #6a6f76;
      --line: #d8cbbd;
      --accent: #9f3d2a;
      --accent-soft: #ead6c3;
      --danger: #9d2f2f;
      --ok: #2d6a4f;
      --soft-bg: rgba(255,255,255,0.75);
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
    h1, h2, h3, p { margin: 0; }
    button, input, textarea, select {
      font: inherit;
    }
    button {
      transition:
        transform 0.16s ease,
        box-shadow 0.16s ease,
        background-color 0.16s ease,
        border-color 0.16s ease,
        color 0.16s ease,
        opacity 0.16s ease;
    }
    button:not(:disabled) {
      will-change: transform;
    }
    button:focus-visible {
      outline: none;
      box-shadow: 0 0 0 3px rgba(159,61,42,0.18);
    }
    button:disabled {
      opacity: 0.58;
      cursor: not-allowed;
      transform: none;
      box-shadow: none;
    }
    .shell {
      min-height: 100vh;
      padding: 28px 32px 40px;
      display: flex;
      flex-direction: column;
      gap: 28px;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 20px;
      box-shadow: 0 10px 30px rgba(64, 47, 30, 0.06);
    }
    .tab-bar {
      display: inline-flex;
      justify-self: start;
      align-self: start;
      gap: 4px;
      align-items: center;
      min-height: 0;
      padding: 4px;
      background: rgba(255,255,255,0.55);
      border-radius: 14px;
      border: 1px solid var(--line);
      width: auto;
    }
    .tab-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      height: 34px;
      min-height: 34px;
      line-height: 1;
      border: 1px solid transparent;
      background: transparent;
      border-radius: 10px;
      padding: 0 16px;
      color: var(--muted);
      cursor: pointer;
      white-space: nowrap;
      transition: color 0.15s ease, background-color 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
    }
    .tab-btn.is-active {
      background: var(--panel);
      color: var(--ink);
      border-color: var(--line);
      box-shadow: 0 4px 12px rgba(64, 47, 30, 0.08);
    }
    .page {
      display: none;
      width: 100%;
      gap: 20px;
    }
    .page.is-active {
      display: grid;
    }
    .grid {
      display: grid;
      grid-template-columns: minmax(360px, 420px) minmax(0, 1fr);
      gap: 20px;
      align-items: start;
    }
    .grid > * {
      min-width: 0;
    }
    .card {
      padding: 18px;
      display: grid;
      gap: 14px;
      min-width: 0;
    }
    .card-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
    }
    .card-title {
      font-size: 18px;
    }
    .muted {
      color: var(--muted);
    }
    .roots-list {
      display: grid;
      gap: 10px;
      min-width: 0;
    }
    .root-row {
      display: flex;
      gap: 10px;
      align-items: center;
      min-width: 0;
    }
    .root-input, .field-input, .field-textarea, .filter-input, .filter-select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: rgba(255,255,255,0.84);
      padding: 12px 14px;
      color: var(--ink);
    }
    .root-input {
      flex: 1 1 auto;
      min-width: 0;
    }
    .field-textarea {
      min-height: 140px;
      resize: vertical;
    }
    .small-btn, .primary-btn, .secondary-btn, .danger-btn {
      border-radius: 14px;
      padding: 10px 16px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.78);
      cursor: pointer;
    }
    .primary-btn {
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
    }
    .danger-btn {
      color: var(--danger);
    }
    .root-remove-btn {
      flex: 0 0 36px;
      width: 36px;
      height: 36px;
      padding: 0;
      border-radius: 999px;
      border: 1px solid rgba(157,47,47,0.18);
      background: rgba(157,47,47,0.08);
      color: var(--danger);
      font-size: 20px;
      line-height: 1;
    }
    .tab-btn:not(:disabled):hover,
    .small-btn:not(:disabled):hover,
    .secondary-btn:not(:disabled):hover,
    .danger-btn:not(:disabled):hover,
    .root-remove-btn:not(:disabled):hover {
      transform: translateY(-1px);
      box-shadow: 0 10px 20px rgba(64, 47, 30, 0.10);
    }
    .tab-btn:not(:disabled):active,
    .small-btn:not(:disabled):active,
    .secondary-btn:not(:disabled):active,
    .danger-btn:not(:disabled):active,
    .root-remove-btn:not(:disabled):active,
    .primary-btn:not(:disabled):active {
      transform: translateY(0) scale(0.98);
      box-shadow: 0 4px 10px rgba(64, 47, 30, 0.10);
    }
    .tab-btn:not(:disabled):hover {
      background: rgba(255,255,255,0.72);
    }
    .primary-btn:not(:disabled):hover {
      transform: translateY(-1px);
      box-shadow: 0 12px 24px rgba(159,61,42,0.28);
    }
    .danger-btn:not(:disabled):hover,
    .root-remove-btn:not(:disabled):hover {
      box-shadow: 0 10px 22px rgba(157,47,47,0.16);
    }
    .root-remove-btn:not(:disabled):hover {
      background: rgba(157,47,47,0.12);
      border-color: rgba(157,47,47,0.22);
    }
    .btn-row {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      min-width: 0;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 999px;
      padding: 5px 11px;
      font-size: 12px;
      border: 1px solid var(--line);
      white-space: nowrap;
    }
    .pill.fix {
      background: rgba(157,47,47,0.10);
      color: var(--danger);
      border-color: rgba(157,47,47,0.16);
    }
    .pill.keep {
      background: rgba(45,106,79,0.12);
      color: var(--ok);
      border-color: rgba(45,106,79,0.16);
    }
    .progress-box {
      display: grid;
      gap: 10px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: var(--soft-bg);
      min-width: 0;
    }
    .progress-bar {
      height: 12px;
      border-radius: 999px;
      background: rgba(159,61,42,0.10);
      overflow: hidden;
    }
    .progress-bar span {
      display: block;
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, #c15a44, #9f3d2a);
      transition: width 0.2s ease;
    }
    .progress-meta {
      display: grid;
      gap: 8px;
      font-size: 13px;
      color: var(--muted);
      min-width: 0;
    }
    .progress-meta-item {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr);
      gap: 6px;
      align-items: start;
      min-width: 0;
    }
    .progress-meta-label {
      white-space: nowrap;
    }
    .progress-meta-value {
      min-width: 0;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    .results-frame-wrap {
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255,255,255,0.74);
    }
    .results-panel {
      position: relative;
      min-width: 0;
    }
    .card-actions {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }
    .report-action-btn {
      min-width: 92px;
    }
    body.results-fullscreen-active {
      overflow: hidden;
    }
    body.results-fullscreen-active::before {
      content: "";
      position: fixed;
      inset: 0;
      background: rgba(31,35,40,0.16);
      backdrop-filter: blur(2px);
      z-index: 2100;
    }
    .results-panel.is-fullscreen {
      position: fixed;
      inset: 16px;
      z-index: 2200;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      align-content: stretch;
      padding: 20px;
      border-radius: 24px;
      background: rgba(255,253,250,0.98);
      box-shadow: 0 24px 56px rgba(31,35,40,0.18);
    }
    .results-panel.is-fullscreen .results-frame-wrap {
      min-height: 0;
      height: 100%;
      display: flex;
      flex-direction: column;
    }
    .report-frame {
      width: 100%;
      min-height: 980px;
      height: calc(100vh - 180px);
      border: none;
      border-radius: 14px;
      background: #fff;
    }
    .results-panel.is-fullscreen .report-frame {
      min-height: 0;
      height: 100%;
      flex: 1 1 auto;
    }
    .empty-state {
      padding: 34px 28px;
      border: 1px dashed var(--line);
      border-radius: 18px;
      background: rgba(255,255,255,0.60);
      color: var(--muted);
      line-height: 1.7;
    }
    .status-banner {
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.72);
      color: var(--muted);
      min-width: 0;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    .status-banner.is-error {
      color: var(--danger);
      border-color: rgba(157,47,47,0.16);
      background: rgba(157,47,47,0.08);
    }
    .annotated-filters {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }
    .annotated-table-wrap {
      overflow: auto;
      border-top: 1px solid var(--line);
    }
    table {
      width: 100%;
      border-collapse: collapse;
    }
    th, td {
      padding: 16px 14px;
      border-bottom: 1px solid rgba(216,203,189,0.75);
      vertical-align: top;
      text-align: left;
    }
    thead th {
      position: sticky;
      top: 0;
      background: rgba(255,253,250,0.95);
      z-index: 1;
    }
    .annotation-reason {
      color: var(--muted);
      line-height: 1.6;
    }
    .field-grid {
      display: grid;
      gap: 12px;
    }
    .field-label {
      font-size: 13px;
      color: var(--muted);
    }
    .readonly-output {
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.76);
      color: var(--muted);
      word-break: break-all;
    }
    .hidden {
      display: none !important;
    }
    @media (max-width: 1100px) {
      .grid {
        grid-template-columns: 1fr;
      }
      .annotated-filters {
        grid-template-columns: 1fr;
      }
      .report-frame {
        height: 75vh;
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <div class="tab-bar" id="tabBar">
      <button class="tab-btn is-active" type="button" data-tab="home">首页</button>
      <button class="tab-btn" type="button" data-tab="annotations">标注管理</button>
      <button class="tab-btn" type="button" data-tab="settings">模型配置</button>
    </div>

    <section class="page is-active" id="homePage">
      <div class="grid">
        <div class="panel card">
          <div class="card-head">
            <div>
              <div class="muted">Scan Roots</div>
              <h2 class="card-title">扫描目录</h2>
            </div>
          </div>
          <div id="rootsList" class="roots-list"></div>
          <div class="btn-row">
            <button id="addRootBtn" class="secondary-btn" type="button">新增目录</button>
            <button id="saveRootsBtn" class="secondary-btn" type="button">保存目录</button>
            <button id="startScanBtn" class="primary-btn" type="button">开始扫描</button>
          </div>
          <div id="homeStatus" class="status-banner">等待扫描</div>
          <div class="progress-box">
            <div class="card-head">
              <div>
                <div class="muted">Progress</div>
                <h3 class="card-title">扫描进度</h3>
              </div>
              <span id="scanStatusPill" class="pill keep">空闲</span>
            </div>
            <div class="progress-bar"><span id="progressBarInner"></span></div>
            <div class="progress-meta">
              <div id="progressCounts">0 / 0</div>
              <div class="progress-meta-item">
                <span class="progress-meta-label">当前项目：</span>
                <span id="progressCurrentRepo" class="progress-meta-value">-</span>
              </div>
              <div class="progress-meta-item">
                <span class="progress-meta-label">当前文件：</span>
                <span id="progressCurrentPath" class="progress-meta-value">-</span>
              </div>
              <div class="progress-meta-item">
                <span class="progress-meta-label">开始时间：</span>
                <span id="progressStartedAt" class="progress-meta-value">-</span>
              </div>
            </div>
          </div>
        </div>

        <div id="resultsPanel" class="panel card results-panel">
          <div class="card-head">
            <div>
              <div class="muted">Report</div>
              <h2 class="card-title">扫描结果</h2>
            </div>
            <div class="card-actions">
              <button id="resultsFullscreenBtn" class="secondary-btn report-action-btn" type="button" disabled>全屏</button>
              <button id="resultsCloseFullscreenBtn" class="secondary-btn report-action-btn hidden" type="button">关闭全屏</button>
            </div>
          </div>
          <div id="resultsEmpty" class="empty-state">
            暂无当前会话扫描结果。请先配置扫描目录并点击“开始扫描”。服务重启后默认不会自动恢复上一次的结果视图。
          </div>
          <div id="resultsFrameWrap" class="results-frame-wrap hidden">
            <iframe id="reportFrame" class="report-frame" title="扫描结果"></iframe>
          </div>
        </div>
      </div>
    </section>

    <section class="page" id="annotationsPage">
      <div class="panel card">
        <div class="card-head">
          <div>
            <div class="muted">Annotations</div>
            <h2 class="card-title">标注管理</h2>
          </div>
        </div>
        <div class="annotated-filters">
          <input id="annotationKeyword" class="filter-input" placeholder="按文本、路径或理由搜索">
          <select id="annotationProject" class="filter-select"></select>
          <select id="annotationCategory" class="filter-select"></select>
        </div>
        <div class="annotated-table-wrap">
          <table>
            <thead>
              <tr>
                <th>项目</th>
                <th>位置</th>
                <th>文本</th>
                <th>原分类</th>
                <th>标注理由</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody id="annotationRows"></tbody>
          </table>
        </div>
      </div>
    </section>

    <section class="page" id="settingsPage">
      <div class="panel card">
        <div class="card-head">
          <div>
            <div class="muted">Model Config</div>
            <h2 class="card-title">模型配置</h2>
          </div>
        </div>
        <div class="field-grid">
          <div>
            <div class="field-label">供应商</div>
            <div id="providerValue" class="readonly-output"></div>
          </div>
          <label>
            <div class="field-label">Base URL</div>
            <input id="baseUrlInput" class="field-input" type="url" placeholder="http://127.0.0.1:8000/v1">
          </label>
          <div class="muted">支持填写主机根、`/v1` 或完整 `/v1/chat/completions`，保存时会统一归一化为 `/v1`。</div>
          <label>
            <div class="field-label">API Key</div>
            <input id="apiKeyInput" class="field-input" type="password" placeholder="sk-...">
          </label>
          <label>
            <div class="field-label">模型名称</div>
            <input id="modelNameInput" class="field-input" type="text" placeholder="deepseek-v3">
          </label>
          <label>
            <div class="field-label">Max Tokens</div>
            <input id="maxTokensInput" class="field-input" type="number" min="1" placeholder="100">
          </label>
        </div>
        <div class="btn-row">
          <button id="saveModelConfigBtn" class="primary-btn" type="button">保存模型配置</button>
        </div>
      </div>
    </section>
  </div>

  <script>
    const BOOTSTRAP = __BOOTSTRAP__;
    const DISPLAY_MAP = __DISPLAY_MAP__;
    const CLIENT_CONFIG = __CLIENT_CONFIG__;
    const DEFAULT_MODEL_CONFIG = {
      provider: "openai compatible",
      base_url: "",
      api_key: "",
      model: "",
      max_tokens: 100,
    };
    const state = {
      activeTab: "home",
      config: BOOTSTRAP.config || { scan_roots: [], scan_policy: {}, model_config: DEFAULT_MODEL_CONFIG, out_dir: "" },
      draftConfig: null,
      scanStatus: BOOTSTRAP.scan_status || {},
      summary: BOOTSTRAP.summary || {},
      findings: BOOTSTRAP.findings || [],
      hasResults: !!BOOTSTRAP.has_results,
      resultsRevision: Number(BOOTSTRAP.results_revision || 0),
      isResultsFullscreen: false,
    };
    state.draftConfig = cloneConfig(state.config);

    const tabBar = document.getElementById("tabBar");
    const homePage = document.getElementById("homePage");
    const annotationsPage = document.getElementById("annotationsPage");
    const settingsPage = document.getElementById("settingsPage");
    const rootsList = document.getElementById("rootsList");
    const addRootBtn = document.getElementById("addRootBtn");
    const saveRootsBtn = document.getElementById("saveRootsBtn");
    const startScanBtn = document.getElementById("startScanBtn");
    const homeStatus = document.getElementById("homeStatus");
    const progressBarInner = document.getElementById("progressBarInner");
    const progressCounts = document.getElementById("progressCounts");
    const progressCurrentRepo = document.getElementById("progressCurrentRepo");
    const progressCurrentPath = document.getElementById("progressCurrentPath");
    const progressStartedAt = document.getElementById("progressStartedAt");
    const scanStatusPill = document.getElementById("scanStatusPill");
    const resultsPanel = document.getElementById("resultsPanel");
    const resultsEmpty = document.getElementById("resultsEmpty");
    const resultsFrameWrap = document.getElementById("resultsFrameWrap");
    const reportFrame = document.getElementById("reportFrame");
    const resultsFullscreenBtn = document.getElementById("resultsFullscreenBtn");
    const resultsCloseFullscreenBtn = document.getElementById("resultsCloseFullscreenBtn");
    const annotationKeyword = document.getElementById("annotationKeyword");
    const annotationProject = document.getElementById("annotationProject");
    const annotationCategory = document.getElementById("annotationCategory");
    const annotationRows = document.getElementById("annotationRows");
    const providerValue = document.getElementById("providerValue");
    const baseUrlInput = document.getElementById("baseUrlInput");
    const apiKeyInput = document.getElementById("apiKeyInput");
    const modelNameInput = document.getElementById("modelNameInput");
    const maxTokensInput = document.getElementById("maxTokensInput");
    const saveModelConfigBtn = document.getElementById("saveModelConfigBtn");
    let scanTimer = null;

    function cloneConfig(config) {
      return JSON.parse(JSON.stringify(config || { scan_roots: [], scan_policy: {}, model_config: DEFAULT_MODEL_CONFIG, out_dir: "" }));
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

    function displaySnippet(item) {
      return item.snippet || item.normalized_text || item.text || "";
    }

    function buildScanPayload() {
      return {
        scan_roots: state.draftConfig.scan_roots.filter(item => String(item || "").trim()).map(item => String(item).trim()),
      };
    }

    function buildModelConfigPayload() {
      return {
        model_config: {
          base_url: baseUrlInput.value,
          api_key: apiKeyInput.value,
          model: modelNameInput.value,
          max_tokens: Number.parseInt(maxTokensInput.value, 10) || DEFAULT_MODEL_CONFIG.max_tokens,
        },
      };
    }

    function applyBootstrap(data, keepDraft = false) {
      state.config = data.config || state.config;
      if (!keepDraft) {
        state.draftConfig = cloneConfig(state.config);
      }
      state.scanStatus = data.scan_status || state.scanStatus;
      state.summary = data.summary || {};
      state.findings = data.findings || [];
      state.hasResults = !!data.has_results;
      state.resultsRevision = Number(data.results_revision || 0);
      renderAll();
    }

    function renderTabs() {
      const buttons = tabBar.querySelectorAll(".tab-btn");
      buttons.forEach(button => {
        button.classList.toggle("is-active", button.dataset.tab === state.activeTab);
      });
      homePage.classList.toggle("is-active", state.activeTab === "home");
      annotationsPage.classList.toggle("is-active", state.activeTab === "annotations");
      settingsPage.classList.toggle("is-active", state.activeTab === "settings");
    }

    function renderRoots() {
      const roots = state.draftConfig.scan_roots.length ? state.draftConfig.scan_roots : [""];
      rootsList.innerHTML = roots.map((root, index) => `
        <div class="root-row">
          <input class="root-input" data-index="${index}" value="${escapeAttr(root)}" placeholder="/absolute/path/to/repo">
          <button class="root-remove-btn" type="button" data-action="remove-root" data-index="${index}" aria-label="删除目录" title="删除目录">×</button>
        </div>
      `).join("");
    }

    function renderStatus() {
      const status = state.scanStatus || {};
      const total = Number(status.total || 0);
      const processed = Number(status.processed || 0);
      const percent = total > 0 ? Math.min(100, Math.round((processed / total) * 100)) : 0;
      progressBarInner.style.width = `${percent}%`;
      progressCounts.textContent = `${processed} / ${total}`;
      progressCurrentRepo.textContent = status.current_repo || "-";
      progressCurrentPath.textContent = status.current_path || "-";
      progressStartedAt.textContent = status.started_at || "-";
      homeStatus.textContent = status.error ? `${status.message || "扫描失败"}：${status.error}` : (status.message || "等待扫描");
      homeStatus.classList.toggle("is-error", Boolean(status.error));
      scanStatusPill.textContent = status.status === "running" ? "运行中" : status.status === "done" ? "完成" : status.status === "failed" ? "失败" : "空闲";
      scanStatusPill.className = `pill ${status.status === "running" ? "fix" : "keep"}`;
      startScanBtn.disabled = status.status === "running";
    }

    function setResultsFullscreen(enabled) {
      const nextValue = Boolean(enabled) && state.hasResults;
      state.isResultsFullscreen = nextValue;
      document.body.classList.toggle("results-fullscreen-active", nextValue);
      resultsPanel.classList.toggle("is-fullscreen", nextValue);
      resultsFullscreenBtn.classList.toggle("hidden", nextValue);
      resultsCloseFullscreenBtn.classList.toggle("hidden", !nextValue);
    }

    function renderResults() {
      resultsFullscreenBtn.disabled = !state.hasResults;
      if (!state.hasResults) {
        setResultsFullscreen(false);
        resultsEmpty.classList.remove("hidden");
        resultsFrameWrap.classList.add("hidden");
        return;
      }
      resultsEmpty.classList.add("hidden");
      resultsFrameWrap.classList.remove("hidden");
      setResultsFullscreen(state.isResultsFullscreen);
      const nextSrc = `${CLIENT_CONFIG.embedded_report_path}?rev=${state.resultsRevision}`;
      if (reportFrame.dataset.src !== nextSrc) {
        reportFrame.src = nextSrc;
        reportFrame.dataset.src = nextSrc;
      }
    }

    function annotatedFindings() {
      const keyword = annotationKeyword.value.trim().toLowerCase();
      const selectedProject = annotationProject.value;
      const selectedCategory = annotationCategory.value;
      return state.findings.filter(item => {
        if (!item.annotated) return false;
        if (selectedProject && item.project !== selectedProject) return false;
        if (selectedCategory && item.original_category !== selectedCategory) return false;
        if (keyword) {
          const target = `${item.project} ${item.path} ${item.text} ${item.annotation_reason || ""} ${labelFor("category", item.original_category)}`.toLowerCase();
          if (!target.includes(keyword)) return false;
        }
        return true;
      });
    }

    function setOptions(select, values, emptyLabel, formatter) {
      const unique = [...new Set(values.filter(Boolean))];
      unique.sort((left, right) => formatter(left).localeCompare(formatter(right), "zh-CN"));
      const current = select.value;
      select.innerHTML = [`<option value="">${emptyLabel}</option>`].concat(
        unique.map(value => `<option value="${escapeAttr(value)}">${escapeHtml(formatter(value))}</option>`)
      ).join("");
      if (unique.indexOf(current) !== -1) {
        select.value = current;
      }
    }

    function renderAnnotations() {
      setOptions(annotationProject, state.findings.filter(item => item.annotated).map(item => item.project), "全部项目", value => value);
      setOptions(annotationCategory, state.findings.filter(item => item.annotated).map(item => item.original_category), "全部原分类", value => labelFor("category", value));
      const items = annotatedFindings();
      if (!items.length) {
        annotationRows.innerHTML = '<tr><td colspan="6" class="muted">当前没有已标注项</td></tr>';
        return;
      }
      annotationRows.innerHTML = items.map(item => `
        <tr>
          <td>${escapeHtml(item.project || "-")}</td>
          <td>${escapeHtml(`${item.path || ""}:${item.line || ""}`)}</td>
          <td>${escapeHtml(displaySnippet(item) || "-")}</td>
          <td>${escapeHtml(labelFor("category", item.original_category) || "-")}</td>
          <td class="annotation-reason">${escapeHtml(item.annotation_reason || "无需修改")}</td>
          <td><button class="danger-btn" type="button" data-action="remove-annotation" data-id="${escapeAttr(item.id)}">撤销标注</button></td>
        </tr>
      `).join("");
    }

    function renderSettings() {
      const modelConfig = state.draftConfig.model_config || DEFAULT_MODEL_CONFIG;
      providerValue.textContent = modelConfig.provider || DEFAULT_MODEL_CONFIG.provider;
      baseUrlInput.value = modelConfig.base_url || "";
      apiKeyInput.value = modelConfig.api_key || "";
      modelNameInput.value = modelConfig.model || "";
      maxTokensInput.value = modelConfig.max_tokens || DEFAULT_MODEL_CONFIG.max_tokens;
    }

    function renderAll() {
      renderTabs();
      renderRoots();
      renderStatus();
      renderResults();
      renderAnnotations();
      renderSettings();
    }

    async function requestJson(path, payload, method = "POST") {
      const options = { method };
      if (method !== "GET") {
        options.headers = { "Content-Type": "application/json" };
        options.body = JSON.stringify(payload || {});
      }
      const response = await fetch(path, options);
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "请求失败");
      }
      return data;
    }

    async function refreshBootstrap(keepDraft = false) {
      const data = await requestJson(CLIENT_CONFIG.bootstrap_api_path, null, "GET");
      applyBootstrap(data, keepDraft);
    }

    async function saveRoots() {
      syncRootsFromInputs();
      const payload = buildScanPayload();
      const data = await requestJson(CLIENT_CONFIG.config_api_path, payload);
      applyBootstrap(data);
      homeStatus.textContent = "目录已保存";
      homeStatus.classList.remove("is-error");
    }

    async function startScan() {
      syncRootsFromInputs();
      const payload = buildScanPayload();
      const data = await requestJson(CLIENT_CONFIG.scan_start_api_path, payload);
      state.scanStatus = data;
      renderStatus();
      startPolling();
    }

    async function saveModelConfig() {
      syncModelConfigFromInputs();
      const payload = buildModelConfigPayload();
      const data = await requestJson(CLIENT_CONFIG.config_api_path, payload);
      applyBootstrap(data);
      homeStatus.textContent = "模型配置已保存";
      homeStatus.classList.remove("is-error");
    }

    async function removeAnnotation(findingId) {
      const data = await requestJson(CLIENT_CONFIG.annotation_remove_api_path, { finding_id: findingId });
      applyBootstrap(data);
    }

    function syncRootsFromInputs() {
      const inputs = rootsList.querySelectorAll(".root-input");
      state.draftConfig.scan_roots = Array.from(inputs).map(input => input.value);
    }

    function syncModelConfigFromInputs() {
      state.draftConfig.model_config = buildModelConfigPayload().model_config;
    }

    function startPolling() {
      stopPolling();
      scanTimer = window.setInterval(async () => {
        try {
          const status = await requestJson(CLIENT_CONFIG.scan_status_api_path, null, "GET");
          state.scanStatus = status;
          renderStatus();
          if (status.status === "done" || status.status === "failed") {
            stopPolling();
            await refreshBootstrap(true);
          }
        } catch (error) {
          stopPolling();
          homeStatus.textContent = error.message || "获取扫描状态失败";
          homeStatus.classList.add("is-error");
        }
      }, 1000);
    }

    function stopPolling() {
      if (scanTimer !== null) {
        window.clearInterval(scanTimer);
        scanTimer = null;
      }
    }

    tabBar.addEventListener("click", async event => {
      const target = event.target instanceof Element ? event.target.closest(".tab-btn") : null;
      if (!target) return;
      const nextTab = target.dataset.tab || "home";
      if (state.isResultsFullscreen && nextTab !== "home") {
        setResultsFullscreen(false);
      }
      state.activeTab = nextTab;
      renderTabs();
      if (nextTab === "annotations") {
        try {
          await refreshBootstrap(true);
        } catch (error) {
          homeStatus.textContent = error.message || "刷新标注数据失败";
          homeStatus.classList.add("is-error");
        }
      }
    });

    rootsList.addEventListener("input", event => {
      const target = event.target instanceof Element ? event.target.closest(".root-input") : null;
      if (!target) return;
      const index = Number.parseInt(target.dataset.index, 10);
      state.draftConfig.scan_roots[index] = target.value;
    });

    rootsList.addEventListener("click", event => {
      const target = event.target instanceof Element ? event.target.closest("[data-action='remove-root']") : null;
      if (!target) return;
      const index = Number.parseInt(target.dataset.index, 10);
      state.draftConfig.scan_roots.splice(index, 1);
      renderRoots();
    });

    addRootBtn.addEventListener("click", () => {
      state.draftConfig.scan_roots.push("");
      renderRoots();
    });

    saveRootsBtn.addEventListener("click", async () => {
      try {
        await saveRoots();
      } catch (error) {
        homeStatus.textContent = error.message || "保存目录失败";
        homeStatus.classList.add("is-error");
      }
    });

    saveModelConfigBtn.addEventListener("click", async () => {
      try {
        await saveModelConfig();
      } catch (error) {
        homeStatus.textContent = error.message || "保存模型配置失败";
        homeStatus.classList.add("is-error");
      }
    });

    startScanBtn.addEventListener("click", async () => {
      try {
        await startScan();
      } catch (error) {
        homeStatus.textContent = error.message || "启动扫描失败";
        homeStatus.classList.add("is-error");
      }
    });

    resultsFullscreenBtn.addEventListener("click", () => {
      if (!state.hasResults) return;
      setResultsFullscreen(true);
    });

    resultsCloseFullscreenBtn.addEventListener("click", () => {
      setResultsFullscreen(false);
    });

    annotationKeyword.addEventListener("input", renderAnnotations);
    annotationProject.addEventListener("change", renderAnnotations);
    annotationCategory.addEventListener("change", renderAnnotations);
    annotationRows.addEventListener("click", async event => {
      const target = event.target instanceof Element ? event.target.closest("[data-action='remove-annotation']") : null;
      if (!target) return;
      try {
        await removeAnnotation(target.dataset.id || "");
      } catch (error) {
        homeStatus.textContent = error.message || "撤销标注失败";
        homeStatus.classList.add("is-error");
      }
    });

    window.addEventListener("message", async event => {
      if (!event.data || event.data.type !== "zh-audit-updated") {
        return;
      }
      try {
        await refreshBootstrap(true);
      } catch (error) {
        homeStatus.textContent = error.message || "刷新结果失败";
        homeStatus.classList.add("is-error");
      }
    });

    window.addEventListener("keydown", event => {
      if (event.key === "Escape" && state.isResultsFullscreen) {
        setResultsFullscreen(false);
      }
    });

    renderAll();
    if (state.scanStatus.status === "running") {
      startPolling();
    }
  </script>
</body>
</html>"""
    return (
        template.replace("__BOOTSTRAP__", payload)
        .replace("__DISPLAY_MAP__", display_maps)
        .replace("__CLIENT_CONFIG__", config_payload)
    )
