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
    html {
      min-height: 100%;
      overflow-y: scroll;
      scrollbar-gutter: stable;
    }
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
      min-height: 100vh;
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
    @keyframes zh-audit-spin {
      from { transform: rotate(0deg); }
      to { transform: rotate(360deg); }
    }
    @keyframes zh-audit-pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.58; }
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
      z-index: 120;
      gap: 4px;
      align-items: center;
      min-height: 0;
      padding: 4px;
      background: rgba(255,255,255,0.55);
      border-radius: 14px;
      border: 1px solid var(--line);
      width: auto;
      pointer-events: auto;
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
      position: relative;
      z-index: 1;
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
    .custom-keep-workspace {
      width: min(1180px, 100%);
      margin: 0 auto;
      display: grid;
      gap: 20px;
    }
    .custom-keep-grid {
      display: grid;
      gap: 20px;
      grid-template-columns: minmax(300px, 360px) minmax(0, 1fr);
      align-items: start;
    }
    .custom-keep-list {
      display: grid;
      gap: 12px;
      align-content: start;
    }
    .custom-keep-category-item {
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: rgba(255,255,255,0.72);
      display: grid;
      gap: 12px;
    }
    .custom-keep-category-item.is-active {
      border-color: rgba(159,61,42,0.32);
      box-shadow: 0 10px 24px rgba(159,61,42,0.10);
      background: rgba(255,250,245,0.92);
    }
    .custom-keep-category-meta {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      flex-wrap: wrap;
    }
    .custom-keep-category-actions,
    .custom-keep-rule-actions {
      display: flex;
      gap: 8px;
      align-items: center;
    }
    .custom-keep-category-actions {
      gap: 6px;
      flex-wrap: nowrap;
      margin-left: auto;
    }
    .custom-keep-category-actions .secondary-btn,
    .custom-keep-category-actions .danger-btn {
      padding: 8px 12px;
    }
    .custom-keep-rule-actions {
      flex-wrap: wrap;
    }
    .custom-keep-help {
      line-height: 1.65;
    }
    .custom-keep-rules-shell {
      display: grid;
      gap: 14px;
      align-content: start;
    }
    .custom-keep-rule-list {
      display: grid;
      gap: 12px;
      align-content: start;
    }
    .custom-keep-rule-card {
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: rgba(255,255,255,0.76);
      display: grid;
      gap: 12px;
    }
    .custom-keep-rule-grid {
      display: grid;
      gap: 12px;
      grid-template-columns: minmax(180px, 220px) minmax(0, 1fr);
      align-items: start;
    }
    .custom-keep-rule-card .field-textarea {
      min-height: 108px;
    }
    .custom-keep-empty {
      padding: 18px;
      border-radius: 16px;
      border: 1px dashed var(--line);
      background: rgba(255,255,255,0.58);
      color: var(--muted);
      line-height: 1.7;
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
    .clearable-input {
      position: relative;
      display: flex;
      align-items: center;
      min-width: 0;
    }
    .clearable-input .field-input {
      padding-right: 48px;
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
    .secondary-btn.is-loading,
    .danger-btn.is-loading {
      opacity: 0.92;
      box-shadow: 0 10px 20px rgba(64, 47, 30, 0.12);
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
    .field-clear-btn {
      position: absolute;
      right: 10px;
      top: 50%;
      transform: translateY(-50%);
      width: 28px;
      height: 28px;
      padding: 0;
      border-radius: 999px;
      border: 1px solid rgba(157,47,47,0.18);
      background: rgba(157,47,47,0.08);
      color: var(--danger);
      font-size: 18px;
      line-height: 1;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }
    .tab-btn:not(:disabled):hover,
    .small-btn:not(:disabled):hover,
    .secondary-btn:not(:disabled):hover,
    .danger-btn:not(:disabled):hover,
    .root-remove-btn:not(:disabled):hover,
    .field-clear-btn:not(:disabled):hover {
      transform: translateY(-1px);
      box-shadow: 0 10px 20px rgba(64, 47, 30, 0.10);
    }
    .tab-btn:not(:disabled):active,
    .small-btn:not(:disabled):active,
    .secondary-btn:not(:disabled):active,
    .danger-btn:not(:disabled):active,
    .root-remove-btn:not(:disabled):active,
    .field-clear-btn:not(:disabled):active,
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
    .pill.is-loading::before {
      content: "";
      width: 10px;
      height: 10px;
      margin-right: 6px;
      border-radius: 999px;
      border: 2px solid currentColor;
      border-right-color: transparent;
      animation: zh-audit-spin 0.8s linear infinite;
      flex: 0 0 auto;
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
    .progress-meta-value.is-loading {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--accent);
    }
    .progress-meta-value.is-loading::before {
      content: "";
      width: 12px;
      height: 12px;
      border-radius: 999px;
      border: 2px solid rgba(159,61,42,0.36);
      border-top-color: var(--accent);
      animation: zh-audit-spin 0.8s linear infinite;
      flex: 0 0 auto;
      margin-top: 1px;
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
    .status-banner.is-loading {
      color: var(--accent);
      border-color: rgba(159,61,42,0.16);
      background: rgba(159,61,42,0.08);
      animation: zh-audit-pulse 1.2s ease-in-out infinite;
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
    .translation-page-shell {
      display: grid;
      gap: 20px;
      min-width: 0;
      min-height: 0;
      height: calc(100vh - 124px);
      overflow: hidden;
      grid-template-rows: auto minmax(0, 1fr);
    }
    .translation-top-grid,
    .translation-bottom-grid {
      display: grid;
      gap: 20px;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      min-width: 0;
    }
    .translation-top-grid {
      align-items: stretch;
    }
    .translation-bottom-grid {
      min-height: 0;
      align-items: stretch;
    }
    .translation-top-grid > .panel,
    .translation-bottom-grid > .panel {
      min-height: 0;
      height: 100%;
    }
    .translation-top-card {
      padding: 14px 16px;
      gap: 10px;
      align-content: start;
    }
    .translation-top-card .card-head {
      gap: 10px;
    }
    .translation-top-card .card-title {
      font-size: 17px;
    }
    .translation-top-card .muted {
      font-size: 12px;
    }
    .translation-top-card .field-input {
      padding: 9px 12px;
      border-radius: 12px;
    }
    .translation-top-card .clearable-input .field-input {
      padding-right: 42px;
    }
    .translation-top-card .field-clear-btn {
      width: 24px;
      height: 24px;
      right: 9px;
      font-size: 16px;
    }
    .translation-top-card .checkbox-row {
      font-size: 13px;
      gap: 8px;
    }
    .translation-top-card .field-label {
      font-size: 12px;
      margin-bottom: 4px;
    }
    .translation-top-card .btn-row {
      gap: 8px;
    }
    .translation-top-card .primary-btn,
    .translation-top-card .secondary-btn {
      padding: 8px 14px;
      border-radius: 12px;
    }
    .translation-control-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
      min-width: 0;
    }
    .translation-control-row .checkbox-row {
      flex: 1 1 auto;
      min-width: 180px;
    }
    .translation-control-row .btn-row {
      flex: 0 0 auto;
      flex-wrap: nowrap;
    }
    .translation-status-inline {
      padding: 8px 12px;
      border-radius: 12px;
      line-height: 1.2;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      cursor: help;
    }
    .translation-compact-field-grid {
      display: grid;
      gap: 10px;
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }
    .translation-inline-output {
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
      flex-wrap: wrap;
    }
    .translation-inline-output .readonly-output {
      flex: 1 1 auto;
      min-width: 0;
      padding: 8px 12px;
      border-radius: 12px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .translation-inline-output .btn-row {
      flex: 0 0 auto;
      flex-wrap: nowrap;
    }
    .translation-details {
      border: 1px solid var(--line);
      border-radius: 12px;
      background: rgba(255,255,255,0.68);
      overflow: hidden;
    }
    .translation-details summary {
      cursor: pointer;
      padding: 8px 12px;
      color: var(--muted);
      font-size: 12px;
      list-style: none;
    }
    .translation-details summary::-webkit-details-marker {
      display: none;
    }
    .translation-details-content {
      display: grid;
      gap: 8px;
      padding: 0 12px 12px;
      min-width: 0;
    }
    .translation-details-content .readonly-output {
      padding: 8px 12px;
      border-radius: 12px;
      font-size: 12px;
    }
    .translation-stat-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px 10px;
      align-items: center;
      min-width: 0;
    }
    .translation-stat-chip {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: var(--soft-bg);
      color: var(--muted);
      font-size: 12px;
      line-height: 1;
      white-space: nowrap;
    }
    .translation-stat-chip strong {
      color: var(--ink);
      font-size: 13px;
      line-height: 1;
    }
    .translation-top-card .progress-box {
      gap: 8px;
      padding: 10px 12px;
      border-radius: 14px;
    }
    .translation-top-card .progress-bar {
      height: 8px;
    }
    .translation-top-card .progress-meta {
      gap: 6px;
      font-size: 12px;
    }
    .translation-top-card .progress-meta-item {
      gap: 4px;
    }
    .translation-fill-card {
      min-height: 0;
      grid-template-rows: auto minmax(0, 1fr);
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
      min-height: 0;
      overflow: auto;
      padding-right: 4px;
      align-content: start;
    }
    .translation-panel-body {
      min-height: 0;
      overflow: hidden;
    }
    .translation-panel-body > .translation-empty,
    .translation-panel-body > .translation-list {
      height: 100%;
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
      font-size: 14px;
      line-height: 1.55;
    }
    .translation-validation-note {
      font-size: 12px;
      color: var(--muted);
      line-height: 1.5;
    }
    .translation-validation-note.is-error {
      color: var(--danger);
    }
    .translation-validation-note.is-progress {
      color: var(--accent);
    }
    .translation-call-budget {
      font-size: 12px;
      color: var(--muted);
    }
    .translation-log-item.is-busy {
      border-color: rgba(159,61,42,0.26);
      background: rgba(255,249,243,0.9);
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
      display: flex;
      align-items: center;
    }
    .hidden {
      display: none !important;
    }
    @media (max-width: 1500px) {
      .translation-compact-field-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }
    @media (max-width: 1100px) {
      .shell {
        padding-left: 20px;
        padding-right: 20px;
      }
      .custom-keep-grid,
      .results-tab-shell {
        height: auto;
        overflow: visible;
      }
      .custom-keep-grid,
      .results-report-host {
        height: auto;
        overflow: visible;
      }
      .custom-keep-grid {
        grid-template-columns: 1fr;
      }
      .translation-page-shell {
        height: auto;
        overflow: visible;
      }
      .translation-top-grid,
      .translation-bottom-grid,
      .custom-keep-rule-grid,
      .translation-grid.two,
      .translation-compact-field-grid {
        grid-template-columns: 1fr;
      }
      .translation-control-row .btn-row {
        flex-wrap: wrap;
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <div class="tab-bar" id="tabBar">
      <button class="tab-btn is-active" type="button" data-tab="home">首页</button>
      <button class="tab-btn" type="button" data-tab="results">扫描结果</button>
      <button class="tab-btn" type="button" data-tab="customKeep">免改规则</button>
      <button class="tab-btn" type="button" data-tab="translation">国际化文件</button>
      <button class="tab-btn" type="button" data-tab="sqlTranslation">数据库数据</button>
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

    <section class="page" id="customKeepPage">
      <div class="custom-keep-workspace">
        <div class="panel card">
          <div class="card-head">
            <div>
              <div class="muted">Keep Rules</div>
              <h2 class="card-title">免改规则配置</h2>
            </div>
          </div>
          <div class="custom-keep-help muted">
            免改规则用于在“无需整改”下新增自定义子分类，系统会将匹配规则的条目归入对应子分类。保存后仅对后续重新扫描生效，不会回溯改写当前已有结果。
          </div>
        </div>

        <div class="custom-keep-grid">
          <div class="panel card">
            <div class="card-head">
              <div>
                <div class="muted">Rule Groups</div>
                <h2 class="card-title">规则分组</h2>
              </div>
              <button id="addCustomKeepCategoryBtn" class="secondary-btn" type="button">新增分组</button>
            </div>
            <div id="customKeepCategoryList" class="custom-keep-list"></div>
          </div>

          <div class="panel card">
            <div class="card-head">
              <div>
                <div class="muted">Rules</div>
                <h2 id="customKeepEditorTitle" class="card-title">规则编辑</h2>
              </div>
              <button id="addCustomKeepRuleBtn" class="secondary-btn" type="button">新增规则</button>
            </div>
            <div id="customKeepEmpty" class="custom-keep-empty">当前还没有规则分组，请先新增分组，再为该分组配置规则。</div>
            <div id="customKeepRulesHost" class="custom-keep-rules-shell hidden">
              <div id="customKeepRuleList" class="custom-keep-rule-list"></div>
            </div>
            <div class="btn-row">
              <button id="saveCustomKeepRulesBtn" class="primary-btn" type="button">保存规则</button>
            </div>
            <div id="customKeepStatusBanner" class="status-banner hidden"></div>
          </div>
        </div>
      </div>
    </section>

    <section class="page" id="translationPage">
      <div class="translation-page-shell">
        <div class="translation-top-grid">
          <div class="panel card translation-top-card">
            <div class="card-head">
              <div>
                <div class="muted">I18N Files</div>
                <h2 class="card-title">国际化文件中英文校对和翻译</h2>
              </div>
              <span id="translationStatusPill" class="pill keep">空闲</span>
            </div>
            <label>
              <div class="clearable-input">
                <input id="translationSourceInput" class="field-input" type="text" placeholder="请填写中文国际化文件绝对路径...">
                <button id="translationSourceClearBtn" class="field-clear-btn hidden" type="button" aria-label="清空中文文件路径" title="清空中文文件路径">×</button>
              </div>
            </label>
            <label>
              <div class="clearable-input">
                <input id="translationTargetInput" class="field-input" type="text" placeholder="请填写英文国际化文件绝对路径...">
                <button id="translationTargetClearBtn" class="field-clear-btn hidden" type="button" aria-label="清空英文文件路径" title="清空英文文件路径">×</button>
              </div>
            </label>
            <div class="translation-control-row">
              <label class="checkbox-row">
                <input id="translationAutoAccept" type="checkbox">
                <span>跳过手动审批，自动接受后续全部 AI 翻译</span>
              </label>
              <div class="btn-row">
                <button id="translationStartBtn" class="primary-btn" type="button">开始校译</button>
                <button id="translationResumeBtn" class="secondary-btn" type="button">继续任务</button>
                <button id="translationStopBtn" class="secondary-btn" type="button">停止任务</button>
              </div>
            </div>
            <div id="translationStatusBanner" class="status-banner translation-status-inline" title="等待校译">等待校译</div>
          </div>

          <div class="panel card translation-top-card">
            <div class="card-head">
              <div>
                <div class="muted">Progress</div>
                <h2 class="card-title">任务进度</h2>
              </div>
            </div>
            <div class="translation-stat-row">
              <span class="translation-stat-chip">总 <strong id="translationTotalCount">0</strong></span>
              <span class="translation-stat-chip">已处理 <strong id="translationProcessedCount">0</strong></span>
              <span class="translation-stat-chip">待审批 <strong id="translationPendingCount">0</strong></span>
              <span class="translation-stat-chip">已接受 <strong id="translationAcceptedCount">0</strong></span>
              <span class="translation-stat-chip">已追加 <strong id="translationAppendedCount">0</strong></span>
              <span class="translation-stat-chip">已跳过 <strong id="translationSkippedCount">0</strong></span>
            </div>
            <div class="progress-box">
              <div class="progress-bar"><span id="translationProgressBarInner"></span></div>
              <div class="progress-meta">
                <div class="progress-meta-item">
                  <span class="progress-meta-label">当前 Key：</span>
                  <span id="translationCurrentKey" class="progress-meta-value">-</span>
                </div>
                <div class="progress-meta-item">
                  <span class="progress-meta-label">当前状态：</span>
                  <span id="translationCurrentStatus" class="progress-meta-value">-</span>
                </div>
                <div class="progress-meta-item">
                  <span class="progress-meta-label">当前中文：</span>
                  <span id="translationCurrentSource" class="progress-meta-value">-</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="translation-bottom-grid">
          <div class="panel card translation-fill-card">
            <div class="card-head">
              <div>
                <div class="muted">Processing Log</div>
                <h2 class="card-title">处理记录</h2>
              </div>
            </div>
            <div id="translationEvents" class="translation-list"></div>
          </div>

          <div class="panel card translation-fill-card">
            <div class="card-head">
              <div>
                <div class="muted">Review Queue</div>
                <h2 class="card-title">待审批条目</h2>
              </div>
            </div>
            <div class="translation-panel-body">
              <div id="translationPendingEmpty" class="translation-empty">当前没有待审批条目。</div>
              <div id="translationPendingList" class="translation-list hidden"></div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="page" id="sqlTranslationPage">
      <div class="translation-page-shell">
        <div class="translation-top-grid">
          <div class="panel card translation-top-card">
            <div class="card-head">
              <div>
                <div class="muted">Database Data</div>
                <h2 class="card-title">数据库数据中英文校对和翻译</h2>
              </div>
              <span id="sqlTranslationStatusPill" class="pill keep">空闲</span>
            </div>
            <label>
              <div class="clearable-input">
                <input id="sqlTranslationDirectoryInput" class="field-input" type="text" placeholder="请输入数据库脚本目录绝对路径" aria-label="数据库脚本目录绝对路径">
                <button id="sqlTranslationDirectoryClearBtn" class="field-clear-btn hidden" type="button" aria-label="清空数据库脚本目录" title="清空数据库脚本目录">×</button>
              </div>
            </label>
            <div class="translation-compact-field-grid">
              <label>
                <input id="sqlTranslationTableInput" class="field-input" type="text" placeholder="请输入目标表名" aria-label="目标表名">
              </label>
              <label>
                <input id="sqlTranslationPrimaryKeyInput" class="field-input" type="text" placeholder="请输入主键字段名，默认 id" aria-label="主键字段名">
              </label>
              <label>
                <input id="sqlTranslationSourceFieldInput" class="field-input" type="text" placeholder="请输入中文文案字段名" aria-label="中文文案字段名">
              </label>
              <label>
                <input id="sqlTranslationTargetFieldInput" class="field-input" type="text" placeholder="请输入英文文案字段名" aria-label="英文文案字段名">
              </label>
            </div>
            <div class="translation-control-row">
              <div class="btn-row">
                <button id="sqlTranslationStartBtn" class="primary-btn" type="button">开始校译</button>
                <button id="sqlTranslationResumeBtn" class="secondary-btn" type="button">继续任务</button>
                <button id="sqlTranslationStopBtn" class="secondary-btn" type="button">停止任务</button>
              </div>
            </div>
            <div id="sqlTranslationStatusBanner" class="status-banner translation-status-inline" title="等待校译">等待校译</div>
            <div id="sqlTranslationOutputRow" class="translation-inline-output hidden">
              <div class="readonly-output">输出文件：<span id="sqlTranslationOutputPathText">-</span></div>
              <div class="btn-row">
                <button id="sqlTranslationCopyPathBtn" class="secondary-btn" type="button">复制路径</button>
              </div>
            </div>
          </div>

          <div class="panel card translation-top-card">
            <div class="card-head">
              <div>
                <div class="muted">Progress</div>
                <h2 class="card-title">任务进度</h2>
              </div>
            </div>
            <div class="translation-stat-row">
              <span class="translation-stat-chip">总 <strong id="sqlTranslationTotalCount">0</strong></span>
              <span class="translation-stat-chip">已处理 <strong id="sqlTranslationProcessedCount">0</strong></span>
              <span class="translation-stat-chip">待审批 <strong id="sqlTranslationPendingCount">0</strong></span>
              <span class="translation-stat-chip">已接受 <strong id="sqlTranslationAcceptedCount">0</strong></span>
              <span class="translation-stat-chip">已追加 <strong id="sqlTranslationAppendedCount">0</strong></span>
              <span class="translation-stat-chip">已跳过 <strong id="sqlTranslationSkippedCount">0</strong></span>
            </div>
            <div class="progress-box">
              <div class="progress-bar"><span id="sqlTranslationProgressBarInner"></span></div>
              <div class="progress-meta">
                <div class="progress-meta-item">
                  <span class="progress-meta-label">当前主键：</span>
                  <span id="sqlTranslationCurrentPrimaryKey" class="progress-meta-value">-</span>
                </div>
                <div class="progress-meta-item">
                  <span class="progress-meta-label">当前状态：</span>
                  <span id="sqlTranslationCurrentStatus" class="progress-meta-value">-</span>
                </div>
                <div class="progress-meta-item">
                  <span class="progress-meta-label">当前中文：</span>
                  <span id="sqlTranslationCurrentSource" class="progress-meta-value">-</span>
                </div>
              </div>
              <details class="translation-details">
                <summary>更多进度</summary>
                <div class="translation-details-content">
                  <div class="readonly-output">当前文件：<span id="sqlTranslationCurrentFile">-</span></div>
                </div>
              </details>
            </div>
          </div>
        </div>

        <div class="translation-bottom-grid">
          <div class="panel card translation-fill-card">
            <div class="card-head">
              <div>
                <div class="muted">Processing Log</div>
                <h2 class="card-title">处理记录</h2>
              </div>
            </div>
            <div id="sqlTranslationEvents" class="translation-list"></div>
          </div>

          <div class="panel card translation-fill-card">
            <div class="card-head">
              <div>
                <div class="muted">Review Queue</div>
                <h2 class="card-title">待审批条目</h2>
              </div>
            </div>
            <div class="translation-panel-body">
              <div id="sqlTranslationPendingEmpty" class="translation-empty">当前没有待审批条目。</div>
              <div id="sqlTranslationPendingList" class="translation-list hidden"></div>
            </div>
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
    const TAB_IDS = ["home", "results", "customKeep", "translation", "sqlTranslation", "settings"];

    function normalizeTabId(value) {
      const candidate = String(value || "").trim();
      return TAB_IDS.includes(candidate) ? candidate : "home";
    }

    function getTabFromLocation() {
      const hash = String(window.location.hash || "").replace(/^#/, "");
      return hash ? normalizeTabId(hash) : "home";
    }

    function updateLocationForTab(tabId) {
      const nextTab = normalizeTabId(tabId);
      const nextHash = nextTab === "home" ? "" : `#${nextTab}`;
      const nextUrl = `${window.location.pathname}${window.location.search}${nextHash}`;
      window.history.replaceState(null, "", nextUrl);
    }

    const state = {
      activeTab: getTabFromLocation(),
      config: BOOTSTRAP.config || { scan_roots: [], scan_policy: {}, model_config: DEFAULT_MODEL_CONFIG, custom_keep_categories: [], out_dir: "" },
      draftConfig: null,
      scanStatus: BOOTSTRAP.scan_status || {},
      summary: BOOTSTRAP.summary || {},
      findings: BOOTSTRAP.findings || [],
      hasResults: !!BOOTSTRAP.has_results,
      resultsRevision: Number(BOOTSTRAP.results_revision || 0),
      translation: BOOTSTRAP.translation || defaultTranslationPayload(),
      sqlTranslation: BOOTSTRAP.sql_translation || defaultSqlTranslationPayload(),
      translationPromptDrafts: {},
      sqlTranslationPromptDrafts: {},
      translationItemOps: {},
      sqlTranslationItemOps: {},
      customKeepSelectedIndex: 0,
      customKeepDirty: false,
      customKeepStatus: defaultCustomKeepStatus(),
    };
    state.draftConfig = cloneConfig(state.config);

    const tabBar = document.getElementById("tabBar");
    const homePage = document.getElementById("homePage");
    const resultsPage = document.getElementById("resultsPage");
    const customKeepPage = document.getElementById("customKeepPage");
    const translationPage = document.getElementById("translationPage");
    const sqlTranslationPage = document.getElementById("sqlTranslationPage");
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
    const customKeepCategoryList = document.getElementById("customKeepCategoryList");
    const addCustomKeepCategoryBtn = document.getElementById("addCustomKeepCategoryBtn");
    const customKeepEditorTitle = document.getElementById("customKeepEditorTitle");
    const customKeepEmpty = document.getElementById("customKeepEmpty");
    const customKeepRulesHost = document.getElementById("customKeepRulesHost");
    const customKeepRuleList = document.getElementById("customKeepRuleList");
    const addCustomKeepRuleBtn = document.getElementById("addCustomKeepRuleBtn");
    const saveCustomKeepRulesBtn = document.getElementById("saveCustomKeepRulesBtn");
    const customKeepStatusBanner = document.getElementById("customKeepStatusBanner");
    const translationStatusPill = document.getElementById("translationStatusPill");
    const translationSourceInput = document.getElementById("translationSourceInput");
    const translationSourceClearBtn = document.getElementById("translationSourceClearBtn");
    const translationTargetInput = document.getElementById("translationTargetInput");
    const translationTargetClearBtn = document.getElementById("translationTargetClearBtn");
    const translationAutoAccept = document.getElementById("translationAutoAccept");
    const translationStartBtn = document.getElementById("translationStartBtn");
    const translationResumeBtn = document.getElementById("translationResumeBtn");
    const translationStopBtn = document.getElementById("translationStopBtn");
    const translationStatusBanner = document.getElementById("translationStatusBanner");
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
    const translationPendingEmpty = document.getElementById("translationPendingEmpty");
    const translationPendingList = document.getElementById("translationPendingList");
    const sqlTranslationStatusPill = document.getElementById("sqlTranslationStatusPill");
    const sqlTranslationDirectoryInput = document.getElementById("sqlTranslationDirectoryInput");
    const sqlTranslationDirectoryClearBtn = document.getElementById("sqlTranslationDirectoryClearBtn");
    const sqlTranslationTableInput = document.getElementById("sqlTranslationTableInput");
    const sqlTranslationPrimaryKeyInput = document.getElementById("sqlTranslationPrimaryKeyInput");
    const sqlTranslationSourceFieldInput = document.getElementById("sqlTranslationSourceFieldInput");
    const sqlTranslationTargetFieldInput = document.getElementById("sqlTranslationTargetFieldInput");
    const sqlTranslationStartBtn = document.getElementById("sqlTranslationStartBtn");
    const sqlTranslationResumeBtn = document.getElementById("sqlTranslationResumeBtn");
    const sqlTranslationStopBtn = document.getElementById("sqlTranslationStopBtn");
    const sqlTranslationCopyPathBtn = document.getElementById("sqlTranslationCopyPathBtn");
    const sqlTranslationStatusBanner = document.getElementById("sqlTranslationStatusBanner");
    const sqlTranslationOutputRow = document.getElementById("sqlTranslationOutputRow");
    const sqlTranslationOutputPathText = document.getElementById("sqlTranslationOutputPathText");
    const sqlTranslationEvents = document.getElementById("sqlTranslationEvents");
    const sqlTranslationTotalCount = document.getElementById("sqlTranslationTotalCount");
    const sqlTranslationProcessedCount = document.getElementById("sqlTranslationProcessedCount");
    const sqlTranslationPendingCount = document.getElementById("sqlTranslationPendingCount");
    const sqlTranslationAcceptedCount = document.getElementById("sqlTranslationAcceptedCount");
    const sqlTranslationAppendedCount = document.getElementById("sqlTranslationAppendedCount");
    const sqlTranslationSkippedCount = document.getElementById("sqlTranslationSkippedCount");
    const sqlTranslationProgressBarInner = document.getElementById("sqlTranslationProgressBarInner");
    const sqlTranslationCurrentFile = document.getElementById("sqlTranslationCurrentFile");
    const sqlTranslationCurrentPrimaryKey = document.getElementById("sqlTranslationCurrentPrimaryKey");
    const sqlTranslationCurrentSource = document.getElementById("sqlTranslationCurrentSource");
    const sqlTranslationCurrentStatus = document.getElementById("sqlTranslationCurrentStatus");
    const sqlTranslationPendingEmpty = document.getElementById("sqlTranslationPendingEmpty");
    const sqlTranslationPendingList = document.getElementById("sqlTranslationPendingList");
    const providerValue = document.getElementById("providerValue");
    const baseUrlInput = document.getElementById("baseUrlInput");
    const apiKeyInput = document.getElementById("apiKeyInput");
    const modelNameInput = document.getElementById("modelNameInput");
    const maxTokensInput = document.getElementById("maxTokensInput");
    const saveModelConfigBtn = document.getElementById("saveModelConfigBtn");
    const settingsStatusBanner = document.getElementById("settingsStatusBanner");
    let scanTimer = null;
    let translationTimer = null;
    let sqlTranslationTimer = null;
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

    function defaultSqlTranslationPayload() {
      return {
        config: {
          directory_path: "",
          table_name: "",
          primary_key_field: "id",
          source_field: "",
          target_field: "",
        },
        status: {
          status: "idle",
          message: "等待校译",
          error: "",
          started_at: "",
          finished_at: "",
          output_path: "",
          current: { file_path: "", primary_key_value: "", source_text: "", status: "" },
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

    function defaultCustomKeepStatus() {
      return {
        text: "",
        isError: false,
      };
    }

    function defaultCustomKeepRule() {
      return {
        type: "keyword",
        pattern: "",
      };
    }

    function defaultCustomKeepCategory(name) {
      return {
        name: name || "",
        enabled: true,
        rules: [defaultCustomKeepRule()],
      };
    }

    function cloneConfig(config) {
      return JSON.parse(JSON.stringify(config || {
        scan_roots: [],
        scan_policy: {},
        model_config: DEFAULT_MODEL_CONFIG,
        custom_keep_categories: [],
        out_dir: "",
      }));
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

    function generateCustomKeepCategoryName() {
      const categories = Array.isArray(state.draftConfig.custom_keep_categories)
        ? state.draftConfig.custom_keep_categories
        : [];
      const names = new Set(categories.map(item => String((item && item.name) || "")));
      let index = categories.length + 1;
      let candidate = `规则分组 ${index}`;
      while (names.has(candidate)) {
        index += 1;
        candidate = `规则分组 ${index}`;
      }
      return candidate;
    }

    function setCustomKeepStatus(text, options = {}) {
      state.customKeepStatus = {
        text: String(text || ""),
        isError: Boolean(options.isError),
      };
    }

    function markCustomKeepDirty() {
      state.customKeepDirty = true;
      setCustomKeepStatus("", { isError: false });
    }

    function ensureCustomKeepSelectedIndex() {
      const categories = Array.isArray(state.draftConfig.custom_keep_categories)
        ? state.draftConfig.custom_keep_categories
        : [];
      if (!categories.length) {
        state.customKeepSelectedIndex = 0;
        return -1;
      }
      if (state.customKeepSelectedIndex < 0) {
        state.customKeepSelectedIndex = 0;
      }
      if (state.customKeepSelectedIndex >= categories.length) {
        state.customKeepSelectedIndex = categories.length - 1;
      }
      return state.customKeepSelectedIndex;
    }

    function buildCustomKeepPayload() {
      const categories = Array.isArray(state.draftConfig.custom_keep_categories)
        ? state.draftConfig.custom_keep_categories
        : [];
      return {
        custom_keep_categories: categories.map(category => ({
          name: String((category && category.name) || "").trim(),
          enabled: !!(category && category.enabled),
          rules: (Array.isArray(category && category.rules) ? category.rules : []).map(rule => ({
            type: String((rule && rule.type) || "keyword").trim().toLowerCase() || "keyword",
            pattern: String((rule && rule.pattern) || "").trim(),
          })),
        })),
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
      state.sqlTranslation = data.sql_translation || state.sqlTranslation;
      if (!keepDraft) {
        state.customKeepDirty = false;
        setCustomKeepStatus(defaultCustomKeepStatus().text);
      }
      ensureCustomKeepSelectedIndex();
      renderAll();
    }

    function pruneItemOps(itemOps, items) {
      const activeIds = new Set((Array.isArray(items) ? items : []).map(item => item.id));
      Object.keys(itemOps || {}).forEach(itemId => {
        if (!activeIds.has(itemId)) {
          delete itemOps[itemId];
        }
      });
    }

    function setItemOp(itemOps, itemId, action, message) {
      itemOps[itemId] = {
        action: String(action || ""),
        message: String(message || ""),
      };
    }

    function clearItemOp(itemOps, itemId) {
      delete itemOps[itemId];
    }

    function renderTabs() {
      const buttons = tabBar.querySelectorAll(".tab-btn");
      buttons.forEach(button => {
        button.classList.toggle("is-active", button.dataset.tab === state.activeTab);
      });
      homePage.classList.toggle("is-active", state.activeTab === "home");
      resultsPage.classList.toggle("is-active", state.activeTab === "results");
      customKeepPage.classList.toggle("is-active", state.activeTab === "customKeep");
      translationPage.classList.toggle("is-active", state.activeTab === "translation");
      sqlTranslationPage.classList.toggle("is-active", state.activeTab === "sqlTranslation");
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
        finding_resolve_api_path: CLIENT_CONFIG.finding_resolve_api_path,
        finding_reopen_api_path: CLIENT_CONFIG.finding_reopen_api_path,
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

    function renderCustomKeep() {
      const categories = Array.isArray(state.draftConfig.custom_keep_categories)
        ? state.draftConfig.custom_keep_categories
        : [];
      const selectedIndex = ensureCustomKeepSelectedIndex();
      const selectedCategory = selectedIndex >= 0 ? categories[selectedIndex] : null;

      if (!categories.length) {
        customKeepCategoryList.innerHTML = '<div class="custom-keep-empty">暂无规则分组，点击右上角“新增分组”开始配置。</div>';
      } else {
        customKeepCategoryList.innerHTML = categories.map((category, index) => `
          <div class="custom-keep-category-item${index === selectedIndex ? " is-active" : ""}">
            <div class="custom-keep-category-meta">
              <span class="pill ${category.enabled ? "keep" : "fix"}">${category.enabled ? "已启用" : "已停用"}</span>
              <div class="custom-keep-category-actions">
                <button class="secondary-btn" type="button" data-action="select-custom-keep-category" data-index="${index}">编辑</button>
                <button class="secondary-btn" type="button" data-action="move-custom-keep-category-up" data-index="${index}" ${index === 0 ? "disabled" : ""}>上移</button>
                <button class="secondary-btn" type="button" data-action="move-custom-keep-category-down" data-index="${index}" ${index === categories.length - 1 ? "disabled" : ""}>下移</button>
                <button class="danger-btn" type="button" data-action="remove-custom-keep-category" data-index="${index}" aria-label="删除分类" title="删除分类">×</button>
              </div>
            </div>
            <label>
              <div class="field-label">分类名称</div>
              <input class="field-input" type="text" data-custom-keep-field="name" data-index="${index}" value="${escapeAttr(category.name || "")}" placeholder="例如：历史兼容文案">
            </label>
            <label class="checkbox-row">
              <input type="checkbox" data-custom-keep-field="enabled" data-index="${index}" ${category.enabled ? "checked" : ""}>
              <span>启用该分类</span>
            </label>
          </div>
        `).join("");
      }

      customKeepEditorTitle.textContent = selectedCategory ? `${selectedCategory.name || "未命名分类"} 的规则` : "规则编辑";
      customKeepEmpty.classList.toggle("hidden", Boolean(selectedCategory));
      customKeepRulesHost.classList.toggle("hidden", !selectedCategory);
      addCustomKeepRuleBtn.disabled = !selectedCategory;
      saveCustomKeepRulesBtn.disabled = !categories.length;

      if (!selectedCategory) {
        customKeepRuleList.innerHTML = "";
      } else {
        const rules = Array.isArray(selectedCategory.rules) ? selectedCategory.rules : [];
        customKeepRuleList.innerHTML = rules.map((rule, ruleIndex) => `
          <div class="custom-keep-rule-card">
            <div class="custom-keep-category-meta">
              <div>
                <div class="field-label">规则 ${ruleIndex + 1}</div>
                <div class="muted">默认匹配命中文本和代码片段。</div>
              </div>
              <div class="custom-keep-rule-actions">
                <button class="secondary-btn" type="button" data-action="move-custom-keep-rule-up" data-index="${ruleIndex}" ${ruleIndex === 0 ? "disabled" : ""}>上移</button>
                <button class="secondary-btn" type="button" data-action="move-custom-keep-rule-down" data-index="${ruleIndex}" ${ruleIndex === rules.length - 1 ? "disabled" : ""}>下移</button>
                <button class="danger-btn" type="button" data-action="remove-custom-keep-rule" data-index="${ruleIndex}" aria-label="删除规则" title="删除规则">×</button>
              </div>
            </div>
            <div class="custom-keep-rule-grid">
              <label>
                <div class="field-label">规则类型</div>
                <select class="filter-select" data-custom-keep-rule-field="type" data-index="${ruleIndex}">
                  <option value="keyword" ${rule.type === "keyword" ? "selected" : ""}>关键字</option>
                  <option value="regex" ${rule.type === "regex" ? "selected" : ""}>正则</option>
                </select>
              </label>
              <label>
                <div class="field-label">${rule.type === "regex" ? "正则表达式" : "关键字"}</div>
                <input class="field-input" type="text" data-custom-keep-rule-field="pattern" data-index="${ruleIndex}" value="${escapeAttr(rule.pattern || "")}" placeholder="${escapeAttr(rule.type === "regex" ? "例如：^系统(繁忙|超时)$" : "例如：系统繁忙")}">
              </label>
            </div>
          </div>
        `).join("");
      }

      const showCustomKeepStatus = Boolean(state.customKeepStatus.isError);
      customKeepStatusBanner.classList.toggle("hidden", !showCustomKeepStatus);
      setStatusBannerState(customKeepStatusBanner, state.customKeepStatus.text, {
        isError: state.customKeepStatus.isError,
        isLoading: false,
      });
    }

    function renderSettings() {
      const modelConfig = state.draftConfig.model_config || DEFAULT_MODEL_CONFIG;
      providerValue.textContent = modelConfig.provider || DEFAULT_MODEL_CONFIG.provider;
      baseUrlInput.value = modelConfig.base_url || "";
      apiKeyInput.value = modelConfig.api_key || "";
      modelNameInput.value = modelConfig.model || "";
      maxTokensInput.value = modelConfig.max_tokens || DEFAULT_MODEL_CONFIG.max_tokens;
    }

    function syncClearableInput(input, button) {
      if (!input || !button) {
        return;
      }
      const visible = !input.disabled && String(input.value || "").length > 0;
      button.classList.toggle("hidden", !visible);
      button.disabled = !visible;
    }

    function syncPathClearButtons() {
      syncClearableInput(translationSourceInput, translationSourceClearBtn);
      syncClearableInput(translationTargetInput, translationTargetClearBtn);
      syncClearableInput(sqlTranslationDirectoryInput, sqlTranslationDirectoryClearBtn);
    }

    function setStatusBannerState(element, text, options = {}) {
      if (!element) {
        return;
      }
      const value = String(text || "");
      element.textContent = value;
      element.title = value;
      if (Object.prototype.hasOwnProperty.call(options, "isError")) {
        element.classList.toggle("is-error", Boolean(options.isError));
      }
      if (Object.prototype.hasOwnProperty.call(options, "isLoading")) {
        element.classList.toggle("is-loading", Boolean(options.isLoading));
      }
    }

    async function clearFieldValue(input, button, saveHandler, showError, previousValue) {
      input.value = "";
      syncClearableInput(input, button);
      input.focus();
      try {
        await saveHandler();
      } catch (error) {
        input.value = previousValue;
        syncClearableInput(input, button);
        showError(error);
      }
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
      const translationIsLoading = status.status === "running" && !Boolean(status.error || terminology.error);

      translationSourceInput.value = config.source_path || "";
      translationTargetInput.value = config.target_path || "";
      translationAutoAccept.checked = !!config.auto_accept;
      setStatusBannerState(
        translationStatusBanner,
        terminology.error ? terminology.error : translationBannerText(status),
        {
          isError: Boolean(status.error || terminology.error),
          isLoading: translationIsLoading,
        },
      );
      translationStatusPill.textContent =
        status.status === "running" ? "运行中" :
        status.status === "done" ? "完成" :
        status.status === "interrupted" ? "中断" :
        status.status === "failed" ? "失败" :
        status.status === "stopped" ? "已停止" : "空闲";
      translationStatusPill.className = `pill ${status.status === "running" ? "fix" : "keep"}${translationIsLoading ? " is-loading" : ""}`;
      translationStartBtn.disabled = status.status === "running" || Boolean(terminology.error);
      translationResumeBtn.disabled = !status.resume_available || Boolean(terminology.error);
      translationStopBtn.disabled = status.status !== "running";
      translationSourceInput.disabled = status.status === "running";
      translationTargetInput.disabled = status.status === "running";
      syncPathClearButtons();
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
      translationCurrentStatus.classList.toggle("is-loading", translationIsLoading && Boolean((status.current || {}).status));
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
      pruneItemOps(state.translationItemOps, pendingItems);
      translationPendingEmpty.classList.toggle("hidden", pendingItems.length > 0);
      translationPendingList.classList.toggle("hidden", pendingItems.length === 0);
      translationPendingList.innerHTML = pendingItems.map(item => {
        const itemOp = state.translationItemOps[item.id] || null;
        const isBusy = Boolean(itemOp);
        const acceptTitle = isBusy
          ? (itemOp.message || "正在处理当前条目")
          : (item.validation_message || "校验未通过，请重新生成");
        return `
        <div class="translation-log-item${isBusy ? " is-busy" : ""}">
          <div class="translation-item-stack">
            <strong>${escapeHtml(item.key || "-")}</strong>
            <div><span class="muted">中文：</span>${escapeHtml(item.source_text || "-")}</div>
            <div><span class="muted">当前英文：</span><code>${escapeHtml(item.target_text || "(空)")}</code></div>
            <div><span class="muted">候选英文：</span><code>${escapeHtml(item.candidate_text || "-")}</code></div>
            ${item.validation_message ? `<div class="translation-validation-note ${item.validation_state === "failed" ? "is-error" : ""}">${escapeHtml(item.validation_message)}</div>` : ""}
            ${itemOp ? `<div class="translation-validation-note is-progress">${escapeHtml(itemOp.message || "正在处理当前条目...")}</div>` : ""}
            <div class="translation-call-budget">重试轮次：${escapeHtml(String(item.generation_attempts_used || 0))}/${escapeHtml(String(5))}</div>
            <div class="translation-tags">
              ${(item.locked_terms || []).map(term => `<span class="translation-tag">${escapeHtml(`${term.source} => ${term.target}`)}</span>`).join("")}
            </div>
          </div>
          <div class="translation-actions">
            <button class="primary-btn${itemOp && itemOp.action === "accept" ? " is-loading" : ""}" type="button" data-action="translation-accept" data-id="${escapeAttr(item.id)}" ${isBusy || item.can_accept === false ? `disabled title="${escapeAttr(acceptTitle)}"` : ""}>${escapeHtml(itemOp && itemOp.action === "accept" ? "接受中..." : "接受")}</button>
            <input class="field-input translation-inline-input" data-prompt-id="${escapeAttr(item.id)}" value="${escapeAttr(state.translationPromptDrafts[item.id] || "")}" placeholder="可选：输入额外 prompt 后重新生成" ${isBusy ? "disabled" : ""}>
            <button class="secondary-btn${itemOp && itemOp.action === "regenerate" ? " is-loading" : ""}" type="button" data-action="translation-regenerate" data-id="${escapeAttr(item.id)}" ${isBusy ? `disabled title="${escapeAttr(itemOp.message || "正在处理当前条目")}"` : ""}>${escapeHtml(itemOp && itemOp.action === "regenerate" ? "重新生成中..." : "重新生成")}</button>
            <button class="danger-btn${itemOp && itemOp.action === "reject" ? " is-loading" : ""}" type="button" data-action="translation-reject" data-id="${escapeAttr(item.id)}" ${isBusy ? `disabled title="${escapeAttr(itemOp.message || "正在处理当前条目")}"` : ""}>${escapeHtml(itemOp && itemOp.action === "reject" ? "忽略中..." : "忽略")}</button>
          </div>
        </div>
      `;
      }).join("");

    }

    function translationBannerText(status) {
      if (status.resume_message) {
        return status.error ? `${status.resume_message}；原因：${status.error}` : status.resume_message;
      }
      return status.error ? `${status.message || "校译失败"}：${status.error}` : (status.message || "等待校译");
    }

    function sqlTranslationBannerText(status, terminology) {
      if (terminology.error) {
        return terminology.error;
      }
      if (status.resume_message) {
        return status.error ? `${status.resume_message}；原因：${status.error}` : status.resume_message;
      }
      if (status.status === "running" && status.output_path) {
        return `已创建输出文件：${status.output_path}，后续每接受 1 条会立即写入`;
      }
      if (status.status === "done" && status.output_path) {
        return `校译完成，SQL 文件已生成：${status.output_path}`;
      }
      return status.error ? `${status.message || "校译失败"}：${status.error}` : (status.message || "等待校译");
    }

    function renderSqlTranslation() {
      const sqlTranslation = state.sqlTranslation || defaultSqlTranslationPayload();
      const config = sqlTranslation.config || {};
      const status = sqlTranslation.status || {};
      const counts = status.counts || {};
      const terminology = sqlTranslation.terminology || {};
      const total = Number(counts.total || 0);
      const processed = Number(counts.processed || 0);
      const percent = total > 0 ? Math.min(100, Math.round((processed / total) * 100)) : 0;
      const sqlTranslationIsLoading = status.status === "running" && !Boolean(status.error || terminology.error);

      sqlTranslationDirectoryInput.value = config.directory_path || "";
      sqlTranslationTableInput.value = config.table_name || "";
      sqlTranslationPrimaryKeyInput.value = config.primary_key_field || "";
      sqlTranslationSourceFieldInput.value = config.source_field || "";
      sqlTranslationTargetFieldInput.value = config.target_field || "";
      setStatusBannerState(
        sqlTranslationStatusBanner,
        sqlTranslationBannerText(status, terminology),
        {
          isError: Boolean(status.error || terminology.error),
          isLoading: sqlTranslationIsLoading,
        },
      );
      sqlTranslationStatusPill.textContent =
        status.status === "running" ? "运行中" :
        status.status === "done" ? "完成" :
        status.status === "interrupted" ? "中断" :
        status.status === "failed" ? "失败" :
        status.status === "stopped" ? "已停止" : "空闲";
      sqlTranslationStatusPill.className = `pill ${status.status === "running" ? "fix" : "keep"}${sqlTranslationIsLoading ? " is-loading" : ""}`;
      sqlTranslationStartBtn.disabled = status.status === "running" || Boolean(terminology.error);
      sqlTranslationResumeBtn.disabled = !status.resume_available || Boolean(terminology.error);
      sqlTranslationStopBtn.disabled = status.status !== "running";
      sqlTranslationDirectoryInput.disabled = status.status === "running";
      sqlTranslationTableInput.disabled = status.status === "running";
      sqlTranslationPrimaryKeyInput.disabled = status.status === "running";
      sqlTranslationSourceFieldInput.disabled = status.status === "running";
      sqlTranslationTargetFieldInput.disabled = status.status === "running";
      sqlTranslationCopyPathBtn.disabled = !status.output_path;
      syncPathClearButtons();
      sqlTranslationOutputPathText.textContent = status.output_path || "-";
      sqlTranslationOutputPathText.title = status.output_path || "";
      sqlTranslationOutputRow.classList.toggle("hidden", !status.output_path);
      sqlTranslationTotalCount.textContent = String(total);
      sqlTranslationProcessedCount.textContent = String(processed);
      sqlTranslationPendingCount.textContent = String(counts.pending || 0);
      sqlTranslationAcceptedCount.textContent = String(counts.accepted || 0);
      sqlTranslationAppendedCount.textContent = String(counts.appended || 0);
      sqlTranslationSkippedCount.textContent = String(counts.skipped || 0);
      sqlTranslationProgressBarInner.style.width = `${percent}%`;
      sqlTranslationCurrentFile.textContent = (status.current || {}).file_path || "-";
      sqlTranslationCurrentPrimaryKey.textContent = (status.current || {}).primary_key_value || "-";
      sqlTranslationCurrentSource.textContent = (status.current || {}).source_text || "-";
      sqlTranslationCurrentStatus.textContent = (status.current || {}).status || "-";
      sqlTranslationCurrentStatus.classList.toggle("is-loading", sqlTranslationIsLoading && Boolean((status.current || {}).status));
      sqlTranslationCurrentFile.title = (status.current || {}).file_path || "";

      const events = Array.isArray(sqlTranslation.events) ? sqlTranslation.events : [];
      if (!events.length) {
        sqlTranslationEvents.innerHTML = '<div class="translation-empty">当前还没有处理记录。</div>';
      } else {
        sqlTranslationEvents.innerHTML = events.map(item => `
          <div class="translation-log-item">
            <div class="translation-log-head">
              <strong>${escapeHtml(item.label || "-")}</strong>
              <span class="muted">${escapeHtml(item.at || "")}</span>
            </div>
            <div class="translation-log-key">${escapeHtml(`${item.source_path || "-"}:${item.line || "-"}`)}</div>
            <div class="muted">主键：${escapeHtml(item.primary_key_value || "-")}</div>
            <div class="muted">${escapeHtml(item.source_text || "-")}</div>
            ${item.target_text ? `<div><code>${escapeHtml(item.target_text)}</code></div>` : ""}
          </div>
        `).join("");
      }

      const pendingItems = Array.isArray(sqlTranslation.pending_items) ? sqlTranslation.pending_items : [];
      pruneItemOps(state.sqlTranslationItemOps, pendingItems);
      sqlTranslationPendingEmpty.classList.toggle("hidden", pendingItems.length > 0);
      sqlTranslationPendingList.classList.toggle("hidden", pendingItems.length === 0);
      sqlTranslationPendingList.innerHTML = pendingItems.map(item => {
        const itemOp = state.sqlTranslationItemOps[item.id] || null;
        const isBusy = Boolean(itemOp);
        const acceptTitle = isBusy
          ? (itemOp.message || "正在处理当前条目")
          : (item.validation_message || "校验未通过，请重新生成");
        return `
        <div class="translation-log-item${isBusy ? " is-busy" : ""}">
          <div class="translation-item-stack">
            <strong>${escapeHtml(`${item.source_path || "-"}:${item.line || "-"}`)}</strong>
            <div><span class="muted">主键：</span>${escapeHtml(item.primary_key_value || "-")}</div>
            <div><span class="muted">中文：</span>${escapeHtml(item.source_text || "-")}</div>
            <div><span class="muted">当前英文：</span><code>${escapeHtml(item.target_text || "(空)")}</code></div>
            <div><span class="muted">候选英文：</span><code>${escapeHtml(item.candidate_text || "-")}</code></div>
            ${item.validation_message ? `<div class="translation-validation-note ${item.validation_state === "failed" ? "is-error" : ""}">${escapeHtml(item.validation_message)}</div>` : ""}
            ${itemOp ? `<div class="translation-validation-note is-progress">${escapeHtml(itemOp.message || "正在处理当前条目...")}</div>` : ""}
            <div class="translation-call-budget">重试轮次：${escapeHtml(String(item.generation_attempts_used || 0))}/${escapeHtml(String(5))}</div>
            <div class="translation-tags">
              ${(item.locked_terms || []).map(term => `<span class="translation-tag">${escapeHtml(`${term.source} => ${term.target}`)}</span>`).join("")}
            </div>
          </div>
          <div class="translation-actions">
            <button class="primary-btn${itemOp && itemOp.action === "accept" ? " is-loading" : ""}" type="button" data-action="sql-translation-accept" data-id="${escapeAttr(item.id)}" ${isBusy || item.can_accept === false ? `disabled title="${escapeAttr(acceptTitle)}"` : ""}>${escapeHtml(itemOp && itemOp.action === "accept" ? "接受中..." : "接受")}</button>
            <input class="field-input translation-inline-input" data-sql-prompt-id="${escapeAttr(item.id)}" value="${escapeAttr(state.sqlTranslationPromptDrafts[item.id] || "")}" placeholder="可选：输入额外 prompt 后重新生成" ${isBusy ? "disabled" : ""}>
            <button class="secondary-btn${itemOp && itemOp.action === "regenerate" ? " is-loading" : ""}" type="button" data-action="sql-translation-regenerate" data-id="${escapeAttr(item.id)}" ${isBusy ? `disabled title="${escapeAttr(itemOp.message || "正在处理当前条目")}"` : ""}>${escapeHtml(itemOp && itemOp.action === "regenerate" ? "重新生成中..." : "重新生成")}</button>
            <button class="danger-btn${itemOp && itemOp.action === "reject" ? " is-loading" : ""}" type="button" data-action="sql-translation-reject" data-id="${escapeAttr(item.id)}" ${isBusy ? `disabled title="${escapeAttr(itemOp.message || "正在处理当前条目")}"` : ""}>${escapeHtml(itemOp && itemOp.action === "reject" ? "忽略中..." : "忽略")}</button>
          </div>
        </div>
      `;
      }).join("");

    }

    async function copyText(value) {
      const text = String(value || "");
      if (!text) {
        return false;
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
        return true;
      }
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.setAttribute("readonly", "readonly");
      textarea.style.position = "absolute";
      textarea.style.left = "-9999px";
      document.body.appendChild(textarea);
      textarea.select();
      const copied = document.execCommand("copy");
      document.body.removeChild(textarea);
      return copied;
    }

    function renderAll() {
      renderTabs();
      renderRoots();
      renderStatus();
      renderResultsPage();
      renderCustomKeep();
      renderTranslation();
      renderSqlTranslation();
      renderSettings();
    }

    function formatRequestError(error) {
      const message = String((error && error.message) || "").trim();
      if (message === "Failed to fetch") {
        return "无法连接本地服务，请确认服务仍在运行，然后刷新页面重试。";
      }
      return message || "请求失败";
    }

    async function requestJson(path, payload, method = "POST") {
      const options = { method };
      if (method !== "GET") {
        options.headers = { "Content-Type": "application/json" };
        options.body = JSON.stringify(payload || {});
      }
      let response;
      try {
        response = await fetch(path, options);
      } catch (error) {
        throw new Error(formatRequestError(error));
      }
      let data = {};
      try {
        data = await response.json();
      } catch (error) {
        throw new Error(response.ok ? "服务返回了无法解析的响应，请刷新页面后重试。" : "服务返回了异常响应，请稍后重试。");
      }
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

    async function saveCustomKeepRules() {
      const payload = buildCustomKeepPayload();
      saveCustomKeepRulesBtn.disabled = true;
      saveCustomKeepRulesBtn.classList.add("is-loading");
      saveCustomKeepRulesBtn.textContent = "保存中...";
      try {
        const data = await requestJson(CLIENT_CONFIG.config_api_path, payload);
        applyBootstrap(data);
        state.customKeepDirty = false;
        setCustomKeepStatus("", { isError: false });
        renderCustomKeep();
      } finally {
        saveCustomKeepRulesBtn.textContent = "保存规则";
        saveCustomKeepRulesBtn.classList.remove("is-loading");
        saveCustomKeepRulesBtn.disabled = !(state.draftConfig.custom_keep_categories || []).length;
      }
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

    async function resumeTranslation() {
      const data = await requestJson(CLIENT_CONFIG.translation_resume_api_path, {});
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

    function buildSqlTranslationPayload() {
      return {
        directory_path: sqlTranslationDirectoryInput.value.trim(),
        table_name: sqlTranslationTableInput.value.trim(),
        primary_key_field: sqlTranslationPrimaryKeyInput.value.trim() || "id",
        source_field: sqlTranslationSourceFieldInput.value.trim(),
        target_field: sqlTranslationTargetFieldInput.value.trim(),
      };
    }

    async function saveSqlTranslationConfig() {
      const data = await requestJson(CLIENT_CONFIG.config_api_path, {
        sql_translation_config: buildSqlTranslationPayload(),
      });
      applyBootstrap(data, true);
    }

    async function startSqlTranslation() {
      const data = await requestJson(CLIENT_CONFIG.sql_translation_start_api_path, buildSqlTranslationPayload());
      state.sqlTranslation = data;
      renderSqlTranslation();
      startSqlTranslationPolling();
    }

    async function resumeSqlTranslation() {
      const data = await requestJson(CLIENT_CONFIG.sql_translation_resume_api_path, {});
      state.sqlTranslation = data;
      renderSqlTranslation();
      startSqlTranslationPolling();
    }

    async function stopSqlTranslation() {
      const data = await requestJson(CLIENT_CONFIG.sql_translation_stop_api_path, {});
      state.sqlTranslation = data;
      renderSqlTranslation();
    }

    async function acceptSqlTranslation(itemId) {
      const data = await requestJson(CLIENT_CONFIG.sql_translation_accept_api_path, { item_id: itemId });
      delete state.sqlTranslationPromptDrafts[itemId];
      state.sqlTranslation = data;
      renderSqlTranslation();
    }

    async function regenerateSqlTranslation(itemId, prompt) {
      const data = await requestJson(CLIENT_CONFIG.sql_translation_regenerate_api_path, {
        item_id: itemId,
        prompt: prompt,
      });
      state.sqlTranslation = data;
      renderSqlTranslation();
    }

    async function rejectSqlTranslation(itemId) {
      const data = await requestJson(CLIENT_CONFIG.sql_translation_reject_api_path, { item_id: itemId });
      delete state.sqlTranslationPromptDrafts[itemId];
      state.sqlTranslation = data;
      renderSqlTranslation();
    }

    async function runTranslationItemAction(itemId, action, runner) {
      const messages = {
        accept: "正在接受当前条目，完成后会自动刷新。",
        regenerate: "正在重新生成当前条目，完成后会自动刷新。",
        reject: "正在忽略当前条目，完成后会自动刷新。",
      };
      setItemOp(state.translationItemOps, itemId, action, messages[action] || "正在处理当前条目，完成后会自动刷新。");
      renderTranslation();
      try {
        await runner();
      } finally {
        clearItemOp(state.translationItemOps, itemId);
        renderTranslation();
      }
    }

    async function runSqlTranslationItemAction(itemId, action, runner) {
      const messages = {
        accept: "正在接受当前条目，完成后会自动刷新。",
        regenerate: "正在重新生成当前条目，完成后会自动刷新。",
        reject: "正在忽略当前条目，完成后会自动刷新。",
      };
      setItemOp(state.sqlTranslationItemOps, itemId, action, messages[action] || "正在处理当前条目，完成后会自动刷新。");
      renderSqlTranslation();
      try {
        await runner();
      } finally {
        clearItemOp(state.sqlTranslationItemOps, itemId);
        renderSqlTranslation();
      }
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
          setStatusBannerState(translationStatusBanner, error.message || "获取校译状态失败", {
            isError: true,
            isLoading: false,
          });
        }
      }, 1000);
    }

    function stopTranslationPolling() {
      if (translationTimer !== null) {
        window.clearInterval(translationTimer);
        translationTimer = null;
      }
    }

    function startSqlTranslationPolling() {
      stopSqlTranslationPolling();
      sqlTranslationTimer = window.setInterval(async () => {
        try {
          const data = await requestJson(CLIENT_CONFIG.sql_translation_status_api_path, null, "GET");
          state.sqlTranslation = data;
          renderSqlTranslation();
          if (((data.status || {}).status || "") !== "running") {
            stopSqlTranslationPolling();
          }
        } catch (error) {
          stopSqlTranslationPolling();
          setStatusBannerState(sqlTranslationStatusBanner, error.message || "获取数据库数据状态失败", {
            isError: true,
            isLoading: false,
          });
        }
      }, 1000);
    }

    function stopSqlTranslationPolling() {
      if (sqlTranslationTimer !== null) {
        window.clearInterval(sqlTranslationTimer);
        sqlTranslationTimer = null;
      }
    }

    async function switchTab(nextTab, options = {}) {
      const resolvedTab = normalizeTabId(nextTab);
      state.activeTab = resolvedTab;
      if (!options.skipLocationUpdate) {
        updateLocationForTab(resolvedTab);
      }
      renderTabs();
      if (resolvedTab === "translation" || resolvedTab === "sqlTranslation") {
        try {
          await refreshBootstrap(true);
        } catch (error) {
          if (resolvedTab === "translation") {
            setStatusBannerState(translationStatusBanner, error.message || "刷新国际化文件状态失败", {
              isError: true,
              isLoading: false,
            });
          } else if (resolvedTab === "sqlTranslation") {
            setStatusBannerState(sqlTranslationStatusBanner, error.message || "刷新数据库数据状态失败", {
              isError: true,
              isLoading: false,
            });
          }
        }
      }
    }

    tabBar.querySelectorAll(".tab-btn").forEach(button => {
      button.addEventListener("click", async () => {
        await switchTab(button.dataset.tab || "home");
      });
    });

    window.addEventListener("hashchange", async () => {
      const nextTab = getTabFromLocation();
      if (nextTab === state.activeTab) {
        return;
      }
      await switchTab(nextTab, { skipLocationUpdate: true });
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

    addCustomKeepCategoryBtn.addEventListener("click", () => {
      if (!Array.isArray(state.draftConfig.custom_keep_categories)) {
        state.draftConfig.custom_keep_categories = [];
      }
      state.draftConfig.custom_keep_categories.push(defaultCustomKeepCategory(generateCustomKeepCategoryName()));
      state.customKeepSelectedIndex = state.draftConfig.custom_keep_categories.length - 1;
      markCustomKeepDirty();
      renderCustomKeep();
    });

    addCustomKeepRuleBtn.addEventListener("click", () => {
      const selectedIndex = ensureCustomKeepSelectedIndex();
      if (selectedIndex < 0) {
        return;
      }
      const category = state.draftConfig.custom_keep_categories[selectedIndex];
      if (!Array.isArray(category.rules)) {
        category.rules = [];
      }
      category.rules.push(defaultCustomKeepRule());
      markCustomKeepDirty();
      renderCustomKeep();
    });

    customKeepCategoryList.addEventListener("input", event => {
      const target = event.target instanceof Element ? event.target.closest("[data-custom-keep-field='name']") : null;
      if (!target) return;
      const index = Number.parseInt(target.dataset.index, 10);
      const category = (state.draftConfig.custom_keep_categories || [])[index];
      if (!category) return;
      category.name = target.value;
      markCustomKeepDirty();
    });

    customKeepCategoryList.addEventListener("change", event => {
      const target = event.target instanceof Element ? event.target.closest("[data-custom-keep-field='enabled']") : null;
      if (!target) return;
      const index = Number.parseInt(target.dataset.index, 10);
      const category = (state.draftConfig.custom_keep_categories || [])[index];
      if (!category) return;
      category.enabled = !!target.checked;
      markCustomKeepDirty();
      renderCustomKeep();
    });

    customKeepCategoryList.addEventListener("click", async event => {
      const target = event.target instanceof Element ? event.target.closest("[data-action]") : null;
      if (!target) return;
      const index = Number.parseInt(target.dataset.index, 10);
      const categories = state.draftConfig.custom_keep_categories || [];
      if (Number.isNaN(index) || !categories[index]) return;
      if (target.dataset.action === "select-custom-keep-category") {
        state.customKeepSelectedIndex = index;
        renderCustomKeep();
        return;
      }
      if (target.dataset.action === "move-custom-keep-category-up" && index > 0) {
        const current = categories[index];
        categories[index] = categories[index - 1];
        categories[index - 1] = current;
        state.customKeepSelectedIndex = index - 1;
        markCustomKeepDirty();
        renderCustomKeep();
        return;
      }
      if (target.dataset.action === "move-custom-keep-category-down" && index < categories.length - 1) {
        const current = categories[index];
        categories[index] = categories[index + 1];
        categories[index + 1] = current;
        state.customKeepSelectedIndex = index + 1;
        markCustomKeepDirty();
        renderCustomKeep();
        return;
      }
      if (target.dataset.action === "remove-custom-keep-category") {
        const previousCategories = JSON.parse(JSON.stringify(categories));
        const previousSelectedIndex = state.customKeepSelectedIndex;
        categories.splice(index, 1);
        if (state.customKeepSelectedIndex >= categories.length) {
          state.customKeepSelectedIndex = Math.max(0, categories.length - 1);
        }
        markCustomKeepDirty();
        renderCustomKeep();
        try {
          await saveCustomKeepRules();
        } catch (error) {
          state.draftConfig.custom_keep_categories = previousCategories;
          if (previousCategories.length) {
            state.customKeepSelectedIndex = Math.max(
              0,
              Math.min(previousSelectedIndex, previousCategories.length - 1),
            );
          } else {
            state.customKeepSelectedIndex = 0;
          }
          setCustomKeepStatus(error.message || "删除分组失败", { isError: true });
          renderCustomKeep();
        }
      }
    });

    customKeepRuleList.addEventListener("input", event => {
      const target = event.target instanceof Element ? event.target.closest("[data-custom-keep-rule-field]") : null;
      if (!target) return;
      const selectedIndex = ensureCustomKeepSelectedIndex();
      if (selectedIndex < 0) return;
      const category = state.draftConfig.custom_keep_categories[selectedIndex];
      const ruleIndex = Number.parseInt(target.dataset.index, 10);
      const rule = (category.rules || [])[ruleIndex];
      if (!rule) return;
      if (target.dataset.customKeepRuleField === "pattern") {
        rule.pattern = target.value;
        markCustomKeepDirty();
        return;
      }
    });

    customKeepRuleList.addEventListener("change", event => {
      const target = event.target instanceof Element ? event.target.closest("[data-custom-keep-rule-field='type']") : null;
      if (!target) return;
      const selectedIndex = ensureCustomKeepSelectedIndex();
      if (selectedIndex < 0) return;
      const category = state.draftConfig.custom_keep_categories[selectedIndex];
      const ruleIndex = Number.parseInt(target.dataset.index, 10);
      const rule = (category.rules || [])[ruleIndex];
      if (!rule) return;
      rule.type = target.value || "keyword";
      markCustomKeepDirty();
      renderCustomKeep();
    });

    customKeepRuleList.addEventListener("click", event => {
      const target = event.target instanceof Element ? event.target.closest("[data-action]") : null;
      if (!target) return;
      const selectedIndex = ensureCustomKeepSelectedIndex();
      if (selectedIndex < 0) return;
      const category = state.draftConfig.custom_keep_categories[selectedIndex];
      const rules = Array.isArray(category.rules) ? category.rules : [];
      const ruleIndex = Number.parseInt(target.dataset.index, 10);
      if (Number.isNaN(ruleIndex) || !rules[ruleIndex]) return;
      if (target.dataset.action === "move-custom-keep-rule-up" && ruleIndex > 0) {
        const current = rules[ruleIndex];
        rules[ruleIndex] = rules[ruleIndex - 1];
        rules[ruleIndex - 1] = current;
        markCustomKeepDirty();
        renderCustomKeep();
        return;
      }
      if (target.dataset.action === "move-custom-keep-rule-down" && ruleIndex < rules.length - 1) {
        const current = rules[ruleIndex];
        rules[ruleIndex] = rules[ruleIndex + 1];
        rules[ruleIndex + 1] = current;
        markCustomKeepDirty();
        renderCustomKeep();
        return;
      }
      if (target.dataset.action === "remove-custom-keep-rule") {
        rules.splice(ruleIndex, 1);
        markCustomKeepDirty();
        renderCustomKeep();
      }
    });

    viewResultsBtn.addEventListener("click", () => {
      if (!state.hasResults) return;
      switchTab("results");
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

    saveCustomKeepRulesBtn.addEventListener("click", async () => {
      try {
        await saveCustomKeepRules();
      } catch (error) {
        setCustomKeepStatus(error.message || "保存免改规则失败", { isError: true });
        renderCustomKeep();
      }
    });

    translationStartBtn.addEventListener("click", async () => {
      try {
        await startTranslation();
      } catch (error) {
        setStatusBannerState(translationStatusBanner, error.message || "启动国际化文件任务失败", {
          isError: true,
          isLoading: false,
        });
      }
    });

    translationResumeBtn.addEventListener("click", async () => {
      try {
        await resumeTranslation();
      } catch (error) {
        setStatusBannerState(translationStatusBanner, error.message || "继续国际化文件任务失败", {
          isError: true,
          isLoading: false,
        });
      }
    });

    translationStopBtn.addEventListener("click", async () => {
      try {
        await stopTranslation();
      } catch (error) {
        setStatusBannerState(translationStatusBanner, error.message || "停止国际化文件任务失败", {
          isError: true,
          isLoading: false,
        });
      }
    });

    translationAutoAccept.addEventListener("change", async () => {
      try {
        await saveTranslationConfig();
      } catch (error) {
        setStatusBannerState(translationStatusBanner, error.message || "保存自动接受配置失败", {
          isError: true,
          isLoading: false,
        });
      }
    });

    translationSourceInput.addEventListener("change", async () => {
      try {
        await saveTranslationConfig();
      } catch (error) {
        setStatusBannerState(translationStatusBanner, error.message || "保存中文文件路径失败", {
          isError: true,
          isLoading: false,
        });
      }
    });
    translationSourceInput.addEventListener("input", () => {
      syncClearableInput(translationSourceInput, translationSourceClearBtn);
    });

    translationTargetInput.addEventListener("change", async () => {
      try {
        await saveTranslationConfig();
      } catch (error) {
        setStatusBannerState(translationStatusBanner, error.message || "保存英文文件路径失败", {
          isError: true,
          isLoading: false,
        });
      }
    });
    translationTargetInput.addEventListener("input", () => {
      syncClearableInput(translationTargetInput, translationTargetClearBtn);
    });

    translationSourceClearBtn.addEventListener("click", async () => {
      const previousValue = translationSourceInput.value;
      await clearFieldValue(
        translationSourceInput,
        translationSourceClearBtn,
        saveTranslationConfig,
        error => {
          setStatusBannerState(translationStatusBanner, error.message || "清空中文文件路径失败", {
            isError: true,
            isLoading: false,
          });
        },
        previousValue,
      );
    });

    translationTargetClearBtn.addEventListener("click", async () => {
      const previousValue = translationTargetInput.value;
      await clearFieldValue(
        translationTargetInput,
        translationTargetClearBtn,
        saveTranslationConfig,
        error => {
          setStatusBannerState(translationStatusBanner, error.message || "清空英文文件路径失败", {
            isError: true,
            isLoading: false,
          });
        },
        previousValue,
      );
    });

    [sqlTranslationDirectoryInput, sqlTranslationTableInput, sqlTranslationPrimaryKeyInput, sqlTranslationSourceFieldInput, sqlTranslationTargetFieldInput]
      .forEach(input => {
        input.addEventListener("change", async () => {
          try {
            await saveSqlTranslationConfig();
          } catch (error) {
            setStatusBannerState(sqlTranslationStatusBanner, error.message || "保存数据库数据配置失败", {
              isError: true,
              isLoading: false,
            });
          }
        });
      });
    sqlTranslationDirectoryInput.addEventListener("input", () => {
      syncClearableInput(sqlTranslationDirectoryInput, sqlTranslationDirectoryClearBtn);
    });

    sqlTranslationDirectoryClearBtn.addEventListener("click", async () => {
      const previousValue = sqlTranslationDirectoryInput.value;
      await clearFieldValue(
        sqlTranslationDirectoryInput,
        sqlTranslationDirectoryClearBtn,
        saveSqlTranslationConfig,
        error => {
          setStatusBannerState(sqlTranslationStatusBanner, error.message || "清空数据库脚本目录失败", {
            isError: true,
            isLoading: false,
          });
        },
        previousValue,
      );
    });

    sqlTranslationStartBtn.addEventListener("click", async () => {
      try {
        await startSqlTranslation();
      } catch (error) {
        setStatusBannerState(sqlTranslationStatusBanner, error.message || "启动数据库数据任务失败", {
          isError: true,
          isLoading: false,
        });
      }
    });

    sqlTranslationResumeBtn.addEventListener("click", async () => {
      try {
        await resumeSqlTranslation();
      } catch (error) {
        setStatusBannerState(sqlTranslationStatusBanner, error.message || "继续数据库数据任务失败", {
          isError: true,
          isLoading: false,
        });
      }
    });

    sqlTranslationStopBtn.addEventListener("click", async () => {
      try {
        await stopSqlTranslation();
      } catch (error) {
        setStatusBannerState(sqlTranslationStatusBanner, error.message || "停止数据库数据任务失败", {
          isError: true,
          isLoading: false,
        });
      }
    });

    sqlTranslationCopyPathBtn.addEventListener("click", async () => {
      try {
        const copied = await copyText(sqlTranslationOutputPathText.textContent || "");
        setStatusBannerState(sqlTranslationStatusBanner, copied ? "已复制输出文件路径" : "复制输出文件路径失败", {
          isError: !copied,
          isLoading: false,
        });
      } catch (error) {
        setStatusBannerState(sqlTranslationStatusBanner, error.message || "复制输出文件路径失败", {
          isError: true,
          isLoading: false,
        });
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

    translationPendingList.addEventListener("click", async event => {
      const target = event.target instanceof Element ? event.target.closest("[data-action]") : null;
      if (!target) return;
      const itemId = target.dataset.id || "";
      try {
        if (target.dataset.action === "translation-accept") {
          await runTranslationItemAction(itemId, "accept", () => acceptTranslation(itemId));
          return;
        }
        if (target.dataset.action === "translation-regenerate") {
          const promptInput = translationPendingList.querySelector(`[data-prompt-id="${itemId}"]`);
          const prompt = promptInput ? promptInput.value : "";
          await runTranslationItemAction(itemId, "regenerate", () => regenerateTranslation(itemId, prompt));
          return;
        }
        if (target.dataset.action === "translation-reject") {
          await runTranslationItemAction(itemId, "reject", () => rejectTranslation(itemId));
        }
      } catch (error) {
        setStatusBannerState(translationStatusBanner, error.message || "处理审批条目失败", {
          isError: true,
          isLoading: false,
        });
      }
    });

    translationPendingList.addEventListener("input", event => {
      const target = event.target instanceof Element ? event.target.closest("[data-prompt-id]") : null;
      if (!target) return;
      state.translationPromptDrafts[target.dataset.promptId || ""] = target.value;
    });

    sqlTranslationPendingList.addEventListener("click", async event => {
      const target = event.target instanceof Element ? event.target.closest("[data-action]") : null;
      if (!target) return;
      const itemId = target.dataset.id || "";
      try {
        if (target.dataset.action === "sql-translation-accept") {
          await runSqlTranslationItemAction(itemId, "accept", () => acceptSqlTranslation(itemId));
          return;
        }
        if (target.dataset.action === "sql-translation-regenerate") {
          const promptInput = sqlTranslationPendingList.querySelector(`[data-sql-prompt-id="${itemId}"]`);
          const prompt = promptInput ? promptInput.value : "";
          await runSqlTranslationItemAction(itemId, "regenerate", () => regenerateSqlTranslation(itemId, prompt));
          return;
        }
        if (target.dataset.action === "sql-translation-reject") {
          await runSqlTranslationItemAction(itemId, "reject", () => rejectSqlTranslation(itemId));
        }
      } catch (error) {
        setStatusBannerState(sqlTranslationStatusBanner, error.message || "处理数据库数据审批条目失败", {
          isError: true,
          isLoading: false,
        });
      }
    });

    sqlTranslationPendingList.addEventListener("input", event => {
      const target = event.target instanceof Element ? event.target.closest("[data-sql-prompt-id]") : null;
      if (!target) return;
      state.sqlTranslationPromptDrafts[target.dataset.sqlPromptId || ""] = target.value;
    });

    resultsReportHost.addEventListener("zh-audit-report-updated", event => {
      if (!event.detail) return;
      state.summary = event.detail.summary || state.summary;
      state.findings = Array.isArray(event.detail.findings) ? event.detail.findings : state.findings;
      state.hasResults = state.findings.length > 0;
      state.resultsRevision += 1;
      renderResultsPage();
      renderStatus();
    });

    updateLocationForTab(state.activeTab);
    renderAll();
    if (state.scanStatus.status === "running") {
      startPolling();
    }
    if (((state.translation || {}).status || {}).status === "running") {
      startTranslationPolling();
    }
    if (((state.sqlTranslation || {}).status || {}).status === "running") {
      startSqlTranslationPolling();
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
