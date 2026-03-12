import json

from zh_audit.report import DISPLAY_MAPS
from zh_audit.report_embed import render_report_component_bundle


def render_app_shell(bootstrap_payload, client_config):
    payload = json.dumps(bootstrap_payload, ensure_ascii=False)
    display_maps = json.dumps(DISPLAY_MAPS, ensure_ascii=False)
    config_payload = json.dumps(client_config, ensure_ascii=False)
    report_bundle = render_report_component_bundle()
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
      min-width: 0;
    }
    .tab-bar {
      display: inline-flex;
      justify-self: center;
      align-self: center;
      position: sticky;
      top: 16px;
      z-index: 30;
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
      min-width: 0;
    }
    .page.is-active {
      display: grid;
    }
    .home-workspace {
      width: min(920px, 100%);
      margin: 0 auto;
      display: grid;
      gap: 20px;
    }
    .settings-workspace {
      width: min(920px, 100%);
      margin: 0 auto;
      display: grid;
      gap: 20px;
    }
    .results-tab-shell {
      display: grid;
      gap: 20px;
      min-width: 0;
      min-height: 0;
      height: calc(100vh - 124px);
      overflow: hidden;
    }
    .results-report-host {
      min-width: 0;
      min-height: 0;
      height: 100%;
      overflow: hidden;
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
      min-width: 0;
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
    .root-input,
    .field-input,
    .field-textarea,
    .filter-input,
    .filter-select {
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
    .small-btn,
    .primary-btn,
    .secondary-btn,
    .danger-btn {
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
    .primary-btn.is-loading {
      opacity: 0.92;
      box-shadow: 0 12px 24px rgba(159,61,42,0.22);
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
    .checkbox-row {
      display: flex;
      align-items: center;
      gap: 10px;
      color: var(--muted);
      font-size: 14px;
    }
    .checkbox-row input {
      width: auto;
      margin: 0;
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
    .translation-layout {
      display: grid;
      gap: 20px;
      grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
      align-items: start;
    }
    .translation-column {
      display: grid;
      gap: 20px;
      min-width: 0;
    }
    .translation-stats {
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
    .translation-stat {
      padding: 14px 16px;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: var(--soft-bg);
    }
    .translation-stat .muted {
      display: block;
      margin-bottom: 8px;
    }
    .translation-stat strong {
      font-size: 24px;
      line-height: 1.2;
    }
    .translation-grid {
      display: grid;
      gap: 14px;
    }
    .translation-grid.two {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .translation-list {
      display: grid;
      gap: 10px;
      max-height: 300px;
      overflow: auto;
      padding-right: 4px;
    }
    .translation-log-item {
      padding: 12px 14px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: rgba(255,255,255,0.78);
      display: grid;
      gap: 6px;
    }
    .translation-log-head {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
    }
    .translation-log-key {
      font-family: "SFMono-Regular", "Menlo", monospace;
      font-size: 13px;
      overflow-wrap: anywhere;
    }
    .translation-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .translation-tag {
      display: inline-flex;
      align-items: center;
      padding: 4px 10px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.82);
      color: var(--muted);
      font-size: 12px;
    }
    .translation-item-stack {
      display: grid;
      gap: 6px;
      min-width: 0;
    }
    .translation-item-stack strong,
    .translation-item-stack code {
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    .translation-item-stack code {
      font-family: "SFMono-Regular", "Menlo", monospace;
      font-size: 12px;
    }
    .translation-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }
    .translation-inline-input {
      flex: 1 1 220px;
      min-width: 180px;
    }
    .translation-table-wrap {
      overflow: auto;
      border-top: 1px solid var(--line);
      max-height: 420px;
    }
    .translation-empty {
      padding: 18px;
      border-radius: 14px;
      border: 1px dashed var(--line);
      background: rgba(255,255,255,0.54);
      color: var(--muted);
    }
    .hidden {
      display: none !important;
    }
    @media (max-width: 1100px) {
      .annotated-filters {
        grid-template-columns: 1fr;
      }
      .shell {
        padding-left: 20px;
        padding-right: 20px;
      }
      .results-tab-shell {
        height: auto;
        overflow: visible;
      }
      .results-report-host {
        height: auto;
        overflow: visible;
      }
      .translation-layout,
      .translation-grid.two,
      .translation-stats {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <div class="tab-bar" id="tabBar">
      <button class="tab-btn is-active" type="button" data-tab="home">首页</button>
      <button class="tab-btn" type="button" data-tab="results">扫描结果</button>
      <button class="tab-btn" type="button" data-tab="annotations">标注管理</button>
      <button class="tab-btn" type="button" data-tab="translation">码值校译</button>
      <button class="tab-btn" type="button" data-tab="settings">模型配置</button>
    </div>

    <section class="page is-active" id="homePage">
      <div class="home-workspace">
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
        </div>

        <div class="panel card">
          <div class="card-head">
            <div>
              <div class="muted">Progress</div>
              <h2 class="card-title">状态与进度</h2>
            </div>
            <span id="scanStatusPill" class="pill keep">空闲</span>
          </div>
          <div id="homeStatus" class="status-banner">等待扫描</div>
          <div class="progress-box">
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
          <div class="btn-row">
            <button id="viewResultsBtn" class="secondary-btn" type="button" disabled>查看扫描结果</button>
          </div>
        </div>
      </div>
    </section>

    <section class="page" id="resultsPage">
      <div class="results-tab-shell">
        <div id="resultsPageEmpty" class="panel card empty-state">
          当前还没有扫描结果，请先到首页配置扫描目录并点击“开始扫描”。
        </div>
        <div id="resultsReportHost" class="results-report-host hidden"></div>
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

    <section class="page" id="translationPage">
      <div class="translation-layout">
        <div class="translation-column">
          <div class="panel card">
            <div class="card-head">
              <div>
                <div class="muted">Translation</div>
                <h2 class="card-title">码值校译</h2>
              </div>
              <span id="translationStatusPill" class="pill keep">空闲</span>
            </div>
            <label>
              <input id="translationSourceInput" class="field-input" type="text" placeholder="请填写中文国际化文件绝对路径...">
            </label>
            <label>
              <input id="translationTargetInput" class="field-input" type="text" placeholder="请填写英文国际化文件绝对路径...">
            </label>
            <label class="checkbox-row">
              <input id="translationAutoAccept" type="checkbox">
              <span>自动接受后续建议</span>
            </label>
            <div class="btn-row">
              <button id="translationStartBtn" class="primary-btn" type="button">开始校译</button>
              <button id="translationStopBtn" class="secondary-btn" type="button">停止任务</button>
            </div>
            <div id="translationStatusBanner" class="status-banner">等待校译</div>
            <div class="translation-grid two">
              <div class="readonly-output">术语词典：<span id="terminologyPathText"></span></div>
              <div class="readonly-output">已加载术语：<span id="terminologyCountText">0</span></div>
            </div>
          </div>

          <div class="panel card">
            <div class="card-head">
              <div>
                <div class="muted">Live Feed</div>
                <h2 class="card-title">实时流水</h2>
              </div>
            </div>
            <div id="translationEvents" class="translation-list"></div>
          </div>
        </div>

        <div class="translation-column">
          <div class="panel card">
            <div class="card-head">
              <div>
                <div class="muted">Progress</div>
                <h2 class="card-title">任务进度</h2>
              </div>
            </div>
            <div class="translation-stats">
              <div class="translation-stat"><span class="muted">总条数</span><strong id="translationTotalCount">0</strong></div>
              <div class="translation-stat"><span class="muted">已处理</span><strong id="translationProcessedCount">0</strong></div>
              <div class="translation-stat"><span class="muted">待审批</span><strong id="translationPendingCount">0</strong></div>
              <div class="translation-stat"><span class="muted">已接收</span><strong id="translationAcceptedCount">0</strong></div>
              <div class="translation-stat"><span class="muted">已追加</span><strong id="translationAppendedCount">0</strong></div>
              <div class="translation-stat"><span class="muted">已跳过</span><strong id="translationSkippedCount">0</strong></div>
            </div>
            <div class="progress-box">
              <div class="progress-bar"><span id="translationProgressBarInner"></span></div>
              <div class="progress-meta">
                <div class="progress-meta-item">
                  <span class="progress-meta-label">当前 Key：</span>
                  <span id="translationCurrentKey" class="progress-meta-value">-</span>
                </div>
                <div class="progress-meta-item">
                  <span class="progress-meta-label">当前中文：</span>
                  <span id="translationCurrentSource" class="progress-meta-value">-</span>
                </div>
                <div class="progress-meta-item">
                  <span class="progress-meta-label">当前状态：</span>
                  <span id="translationCurrentStatus" class="progress-meta-value">-</span>
                </div>
                <div class="progress-meta-item">
                  <span class="progress-meta-label">备份文件：</span>
                  <span id="translationBackupPath" class="progress-meta-value">-</span>
                </div>
              </div>
            </div>
          </div>

          <div class="panel card">
            <div class="card-head">
              <div>
                <div class="muted">Review Queue</div>
                <h2 class="card-title">待审批条目</h2>
              </div>
            </div>
            <div id="translationPendingEmpty" class="translation-empty">当前没有待审批条目。</div>
            <div id="translationPendingList" class="translation-list hidden"></div>
          </div>

          <div class="panel card">
            <div class="card-head">
              <div>
                <div class="muted">Recent</div>
                <h2 class="card-title">最近完成</h2>
              </div>
            </div>
            <div id="translationRecentEmpty" class="translation-empty">当前还没有已完成条目。</div>
            <div id="translationRecentList" class="translation-list hidden"></div>
          </div>
        </div>
      </div>
    </section>

    <section class="page" id="settingsPage">
      <div class="settings-workspace">
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
          <div id="settingsStatusBanner" class="status-banner">保存模型配置时会先做一次连通性测试。</div>
        </div>
      </div>
    </section>
  </div>

  <script>
__REPORT_COMPONENT_BUNDLE__
  </script>
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
      translation: BOOTSTRAP.translation || defaultTranslationPayload(),
      translationPromptDrafts: {},
    };
    state.draftConfig = cloneConfig(state.config);

    const tabBar = document.getElementById("tabBar");
    const homePage = document.getElementById("homePage");
    const resultsPage = document.getElementById("resultsPage");
    const annotationsPage = document.getElementById("annotationsPage");
    const translationPage = document.getElementById("translationPage");
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
    const viewResultsBtn = document.getElementById("viewResultsBtn");
    const resultsPageEmpty = document.getElementById("resultsPageEmpty");
    const resultsReportHost = document.getElementById("resultsReportHost");
    const annotationKeyword = document.getElementById("annotationKeyword");
    const annotationProject = document.getElementById("annotationProject");
    const annotationCategory = document.getElementById("annotationCategory");
    const annotationRows = document.getElementById("annotationRows");
    const translationStatusPill = document.getElementById("translationStatusPill");
    const translationSourceInput = document.getElementById("translationSourceInput");
    const translationTargetInput = document.getElementById("translationTargetInput");
    const translationAutoAccept = document.getElementById("translationAutoAccept");
    const translationStartBtn = document.getElementById("translationStartBtn");
    const translationStopBtn = document.getElementById("translationStopBtn");
    const translationStatusBanner = document.getElementById("translationStatusBanner");
    const terminologyPathText = document.getElementById("terminologyPathText");
    const terminologyCountText = document.getElementById("terminologyCountText");
    const translationEvents = document.getElementById("translationEvents");
    const translationTotalCount = document.getElementById("translationTotalCount");
    const translationProcessedCount = document.getElementById("translationProcessedCount");
    const translationPendingCount = document.getElementById("translationPendingCount");
    const translationAcceptedCount = document.getElementById("translationAcceptedCount");
    const translationAppendedCount = document.getElementById("translationAppendedCount");
    const translationSkippedCount = document.getElementById("translationSkippedCount");
    const translationProgressBarInner = document.getElementById("translationProgressBarInner");
    const translationCurrentKey = document.getElementById("translationCurrentKey");
    const translationCurrentSource = document.getElementById("translationCurrentSource");
    const translationCurrentStatus = document.getElementById("translationCurrentStatus");
    const translationBackupPath = document.getElementById("translationBackupPath");
    const translationPendingEmpty = document.getElementById("translationPendingEmpty");
    const translationPendingList = document.getElementById("translationPendingList");
    const translationRecentEmpty = document.getElementById("translationRecentEmpty");
    const translationRecentList = document.getElementById("translationRecentList");
    const providerValue = document.getElementById("providerValue");
    const baseUrlInput = document.getElementById("baseUrlInput");
    const apiKeyInput = document.getElementById("apiKeyInput");
    const modelNameInput = document.getElementById("modelNameInput");
    const maxTokensInput = document.getElementById("maxTokensInput");
    const saveModelConfigBtn = document.getElementById("saveModelConfigBtn");
    const settingsStatusBanner = document.getElementById("settingsStatusBanner");
    let scanTimer = null;
    let translationTimer = null;
    let reportController = null;

    function defaultTranslationPayload() {
      return {
        config: {
          source_path: "",
          target_path: "",
          auto_accept: false,
        },
        status: {
          status: "idle",
          message: "等待校译",
          error: "",
          started_at: "",
          finished_at: "",
          backup_path: "",
          current: { key: "", source_text: "", status: "" },
          counts: {
            total: 0,
            processed: 0,
            skipped: 0,
            pending: 0,
            accepted: 0,
            appended: 0,
            failed: 0,
            rejected: 0,
            regenerated: 0,
            glossary_applied: 0,
          },
        },
        pending_items: [],
        recent_items: [],
        events: [],
        terminology: {
          path: "",
          count: 0,
          error: "",
        },
      };
    }

    function cloneConfig(config) {
      return JSON.parse(JSON.stringify(config || { scan_roots: [], scan_policy: {}, model_config: DEFAULT_MODEL_CONFIG, out_dir: "" }));
    }

    function parseInteger(value, fallback, minValue) {
      const parsed = Number.parseInt(value, 10);
      if (Number.isNaN(parsed)) {
        return fallback;
      }
      return Math.max(minValue, parsed);
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
      state.translation = data.translation || state.translation;
      renderAll();
    }

    function renderTabs() {
      const buttons = tabBar.querySelectorAll(".tab-btn");
      buttons.forEach(button => {
        button.classList.toggle("is-active", button.dataset.tab === state.activeTab);
      });
      homePage.classList.toggle("is-active", state.activeTab === "home");
      resultsPage.classList.toggle("is-active", state.activeTab === "results");
      annotationsPage.classList.toggle("is-active", state.activeTab === "annotations");
      translationPage.classList.toggle("is-active", state.activeTab === "translation");
      settingsPage.classList.toggle("is-active", state.activeTab === "settings");
    }

    function renderRoots() {
      const roots = state.draftConfig.scan_roots.length ? state.draftConfig.scan_roots : [""];
      rootsList.innerHTML = roots.map((root, index) => `
        <div class="root-row">
          <input class="root-input" data-index="${index}" value="${escapeAttr(root)}" placeholder="请填写待扫描项目目录绝对路径...">
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
      viewResultsBtn.disabled = !state.hasResults;
    }

    function renderResultsPage() {
      viewResultsBtn.disabled = !state.hasResults;
      if (!state.hasResults) {
        resultsPageEmpty.classList.remove("hidden");
        resultsReportHost.classList.add("hidden");
        return;
      }
      resultsPageEmpty.classList.add("hidden");
      resultsReportHost.classList.remove("hidden");
      const controllerConfig = {
        mode: "serve",
        annotation_api_path: CLIENT_CONFIG.annotation_api_path,
        annotation_remove_api_path: CLIENT_CONFIG.annotation_remove_api_path,
        readonly_message: "",
        annotation_path: state.config.out_dir || "",
      };
      const payload = {
        summary: state.summary || {},
        findings: state.findings || [],
      };
      if (!reportController) {
        reportController = window.ZhAuditReport.mount(resultsReportHost, payload, controllerConfig, {
          shadow: true,
          embedded: true,
        });
      } else {
        reportController.update(payload, controllerConfig, {
          shadow: true,
          embedded: true,
        });
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

    function renderTranslation() {
      const translation = state.translation || defaultTranslationPayload();
      const config = translation.config || {};
      const status = translation.status || {};
      const counts = status.counts || {};
      const terminology = translation.terminology || {};
      const total = Number(counts.total || 0);
      const processed = Number(counts.processed || 0);
      const percent = total > 0 ? Math.min(100, Math.round((processed / total) * 100)) : 0;

      translationSourceInput.value = config.source_path || "";
      translationTargetInput.value = config.target_path || "";
      translationAutoAccept.checked = !!config.auto_accept;
      translationStatusBanner.textContent = terminology.error
        ? terminology.error
        : (status.error ? `${status.message || "校译失败"}：${status.error}` : (status.message || "等待校译"));
      translationStatusBanner.classList.toggle("is-error", Boolean(status.error || terminology.error));
      translationStatusPill.textContent =
        status.status === "running" ? "运行中" :
        status.status === "done" ? "完成" :
        status.status === "failed" ? "失败" :
        status.status === "stopped" ? "已停止" : "空闲";
      translationStatusPill.className = `pill ${status.status === "running" ? "fix" : "keep"}`;
      translationStartBtn.disabled = status.status === "running" || Boolean(terminology.error);
      translationStopBtn.disabled = status.status !== "running";
      translationSourceInput.disabled = status.status === "running";
      translationTargetInput.disabled = status.status === "running";
      terminologyPathText.textContent = terminology.path || "-";
      terminologyCountText.textContent = String(terminology.count || 0);
      translationTotalCount.textContent = String(total);
      translationProcessedCount.textContent = String(processed);
      translationPendingCount.textContent = String(counts.pending || 0);
      translationAcceptedCount.textContent = String(counts.accepted || 0);
      translationAppendedCount.textContent = String(counts.appended || 0);
      translationSkippedCount.textContent = String(counts.skipped || 0);
      translationProgressBarInner.style.width = `${percent}%`;
      translationCurrentKey.textContent = (status.current || {}).key || "-";
      translationCurrentSource.textContent = (status.current || {}).source_text || "-";
      translationCurrentStatus.textContent = (status.current || {}).status || "-";
      translationBackupPath.textContent = status.backup_path || "-";

      const events = Array.isArray(translation.events) ? translation.events : [];
      if (!events.length) {
        translationEvents.innerHTML = '<div class="translation-empty">当前还没有处理记录。</div>';
      } else {
        translationEvents.innerHTML = events.map(item => `
          <div class="translation-log-item">
            <div class="translation-log-head">
              <strong>${escapeHtml(item.label || "-")}</strong>
              <span class="muted">${escapeHtml(item.at || "")}</span>
            </div>
            <div class="translation-log-key">${escapeHtml(item.key || "-")}</div>
            <div class="muted">${escapeHtml(item.source_text || "-")}</div>
            ${item.target_text ? `<div><code>${escapeHtml(item.target_text)}</code></div>` : ""}
          </div>
        `).join("");
      }

      const pendingItems = Array.isArray(translation.pending_items) ? translation.pending_items : [];
      translationPendingEmpty.classList.toggle("hidden", pendingItems.length > 0);
      translationPendingList.classList.toggle("hidden", pendingItems.length === 0);
      translationPendingList.innerHTML = pendingItems.map(item => `
        <div class="translation-log-item">
          <div class="translation-item-stack">
            <strong>${escapeHtml(item.key || "-")}</strong>
            <div><span class="muted">中文：</span>${escapeHtml(item.source_text || "-")}</div>
            <div><span class="muted">当前英文：</span><code>${escapeHtml(item.target_text || "(空)")}</code></div>
            <div><span class="muted">候选英文：</span><code>${escapeHtml(item.candidate_text || "-")}</code></div>
            <div><span class="muted">判定理由：</span>${escapeHtml(item.reason || "-")}</div>
            <div class="translation-tags">
              ${(item.locked_terms || []).map(term => `<span class="translation-tag">${escapeHtml(`${term.source} => ${term.target}`)}</span>`).join("")}
            </div>
          </div>
          <div class="translation-actions">
            <button class="primary-btn" type="button" data-action="translation-accept" data-id="${escapeAttr(item.id)}">接收</button>
            <input class="field-input translation-inline-input" data-prompt-id="${escapeAttr(item.id)}" value="${escapeAttr(state.translationPromptDrafts[item.id] || "")}" placeholder="可选：输入额外 prompt 后重生成">
            <button class="secondary-btn" type="button" data-action="translation-regenerate" data-id="${escapeAttr(item.id)}">重生成</button>
            <button class="danger-btn" type="button" data-action="translation-reject" data-id="${escapeAttr(item.id)}">忽略</button>
          </div>
        </div>
      `).join("");

      const recentItems = Array.isArray(translation.recent_items) ? translation.recent_items : [];
      translationRecentEmpty.classList.toggle("hidden", recentItems.length > 0);
      translationRecentList.classList.toggle("hidden", recentItems.length === 0);
      translationRecentList.innerHTML = recentItems.map(item => `
        <div class="translation-log-item">
          <div class="translation-log-head">
            <strong>${escapeHtml(item.status || "-")}</strong>
            <span class="muted">${escapeHtml(item.updated_at || "")}</span>
          </div>
          <div class="translation-item-stack">
            <strong>${escapeHtml(item.key || "-")}</strong>
            <div><span class="muted">中文：</span>${escapeHtml(item.source_text || "-")}</div>
            <div><span class="muted">英文：</span><code>${escapeHtml(item.target_text || item.candidate_text || "-")}</code></div>
            <div><span class="muted">说明：</span>${escapeHtml(item.reason || item.verdict || "-")}</div>
          </div>
        </div>
      `).join("");
    }

    function renderAll() {
      renderTabs();
      renderRoots();
      renderStatus();
      renderResultsPage();
      renderAnnotations();
      renderTranslation();
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
      settingsStatusBanner.textContent = "正在测试模型连通性并保存配置...";
      settingsStatusBanner.classList.remove("is-error");
      saveModelConfigBtn.disabled = true;
      saveModelConfigBtn.classList.add("is-loading");
      saveModelConfigBtn.textContent = "测试并保存中...";
      const data = await requestJson(CLIENT_CONFIG.config_api_path, payload);
      applyBootstrap(data);
      settingsStatusBanner.textContent = "模型配置已保存，连通性测试通过。";
      settingsStatusBanner.classList.remove("is-error");
      saveModelConfigBtn.textContent = "保存模型配置";
      saveModelConfigBtn.classList.remove("is-loading");
      saveModelConfigBtn.disabled = false;
    }

    function buildTranslationPayload() {
      return {
        source_path: translationSourceInput.value.trim(),
        target_path: translationTargetInput.value.trim(),
        auto_accept: translationAutoAccept.checked,
      };
    }

    async function saveTranslationConfig() {
      const data = await requestJson(CLIENT_CONFIG.config_api_path, {
        translation_config: buildTranslationPayload(),
      });
      applyBootstrap(data, true);
    }

    async function startTranslation() {
      const data = await requestJson(CLIENT_CONFIG.translation_start_api_path, buildTranslationPayload());
      state.translation = data;
      renderTranslation();
      startTranslationPolling();
    }

    async function stopTranslation() {
      const data = await requestJson(CLIENT_CONFIG.translation_stop_api_path, {});
      state.translation = data;
      renderTranslation();
    }

    async function acceptTranslation(itemId) {
      const data = await requestJson(CLIENT_CONFIG.translation_accept_api_path, { item_id: itemId });
      delete state.translationPromptDrafts[itemId];
      state.translation = data;
      renderTranslation();
    }

    async function regenerateTranslation(itemId, prompt) {
      const data = await requestJson(CLIENT_CONFIG.translation_regenerate_api_path, {
        item_id: itemId,
        prompt: prompt,
      });
      state.translation = data;
      renderTranslation();
    }

    async function rejectTranslation(itemId) {
      const data = await requestJson(CLIENT_CONFIG.translation_reject_api_path, { item_id: itemId });
      delete state.translationPromptDrafts[itemId];
      state.translation = data;
      renderTranslation();
    }

    async function removeAnnotation(findingId) {
      const data = await requestJson(CLIENT_CONFIG.annotation_remove_api_path, { finding_id: findingId });
      applyBootstrap(data, true);
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

    function startTranslationPolling() {
      stopTranslationPolling();
      translationTimer = window.setInterval(async () => {
        try {
          const data = await requestJson(CLIENT_CONFIG.translation_status_api_path, null, "GET");
          state.translation = data;
          renderTranslation();
          if (((data.status || {}).status || "") !== "running") {
            stopTranslationPolling();
          }
        } catch (error) {
          stopTranslationPolling();
          translationStatusBanner.textContent = error.message || "获取校译状态失败";
          translationStatusBanner.classList.add("is-error");
        }
      }, 1000);
    }

    function stopTranslationPolling() {
      if (translationTimer !== null) {
        window.clearInterval(translationTimer);
        translationTimer = null;
      }
    }

    tabBar.addEventListener("click", async event => {
      const target = event.target instanceof Element ? event.target.closest(".tab-btn") : null;
      if (!target) return;
      const nextTab = target.dataset.tab || "home";
      state.activeTab = nextTab;
      renderTabs();
      if (nextTab === "annotations" || nextTab === "translation") {
        try {
          await refreshBootstrap(true);
        } catch (error) {
          if (nextTab === "translation") {
            translationStatusBanner.textContent = error.message || "刷新码值校译状态失败";
            translationStatusBanner.classList.add("is-error");
          } else {
            homeStatus.textContent = error.message || "刷新标注数据失败";
            homeStatus.classList.add("is-error");
          }
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

    viewResultsBtn.addEventListener("click", () => {
      if (!state.hasResults) return;
      state.activeTab = "results";
      renderTabs();
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
        settingsStatusBanner.textContent = error.message || "保存模型配置失败";
        settingsStatusBanner.classList.add("is-error");
      } finally {
        saveModelConfigBtn.textContent = "保存模型配置";
        saveModelConfigBtn.classList.remove("is-loading");
        saveModelConfigBtn.disabled = false;
      }
    });

    translationStartBtn.addEventListener("click", async () => {
      try {
        await startTranslation();
      } catch (error) {
        translationStatusBanner.textContent = error.message || "启动码值校译失败";
        translationStatusBanner.classList.add("is-error");
      }
    });

    translationStopBtn.addEventListener("click", async () => {
      try {
        await stopTranslation();
      } catch (error) {
        translationStatusBanner.textContent = error.message || "停止码值校译失败";
        translationStatusBanner.classList.add("is-error");
      }
    });

    translationAutoAccept.addEventListener("change", async () => {
      try {
        await saveTranslationConfig();
      } catch (error) {
        translationStatusBanner.textContent = error.message || "保存自动接收配置失败";
        translationStatusBanner.classList.add("is-error");
      }
    });

    translationSourceInput.addEventListener("change", async () => {
      try {
        await saveTranslationConfig();
      } catch (error) {
        translationStatusBanner.textContent = error.message || "保存中文文件路径失败";
        translationStatusBanner.classList.add("is-error");
      }
    });

    translationTargetInput.addEventListener("change", async () => {
      try {
        await saveTranslationConfig();
      } catch (error) {
        translationStatusBanner.textContent = error.message || "保存英文文件路径失败";
        translationStatusBanner.classList.add("is-error");
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

    translationPendingList.addEventListener("click", async event => {
      const target = event.target instanceof Element ? event.target.closest("[data-action]") : null;
      if (!target) return;
      const itemId = target.dataset.id || "";
      try {
        if (target.dataset.action === "translation-accept") {
          await acceptTranslation(itemId);
          return;
        }
        if (target.dataset.action === "translation-regenerate") {
          const promptInput = translationPendingList.querySelector(`[data-prompt-id="${itemId}"]`);
          const prompt = promptInput ? promptInput.value : "";
          await regenerateTranslation(itemId, prompt);
          return;
        }
        if (target.dataset.action === "translation-reject") {
          await rejectTranslation(itemId);
        }
      } catch (error) {
        translationStatusBanner.textContent = error.message || "处理审批条目失败";
        translationStatusBanner.classList.add("is-error");
      }
    });

    translationPendingList.addEventListener("input", event => {
      const target = event.target instanceof Element ? event.target.closest("[data-prompt-id]") : null;
      if (!target) return;
      state.translationPromptDrafts[target.dataset.promptId || ""] = target.value;
    });

    resultsReportHost.addEventListener("zh-audit-report-updated", event => {
      if (!event.detail) return;
      state.summary = event.detail.summary || state.summary;
      state.findings = Array.isArray(event.detail.findings) ? event.detail.findings : state.findings;
      state.hasResults = state.findings.length > 0;
      state.resultsRevision += 1;
      renderResultsPage();
      renderAnnotations();
      renderStatus();
    });

    renderAll();
    if (state.scanStatus.status === "running") {
      startPolling();
    }
    if (((state.translation || {}).status || {}).status === "running") {
      startTranslationPolling();
    }
  </script>
</body>
</html>"""
    return (
        template.replace("__REPORT_COMPONENT_BUNDLE__", report_bundle)
        .replace("__BOOTSTRAP__", payload)
        .replace("__DISPLAY_MAP__", display_maps)
        .replace("__CLIENT_CONFIG__", config_payload)
    )
