# Report Schema — HTML & Excel

`audit-reporter` 输出报告的格式契约。Slice B / C 落地脚本时按本文实现。

## HTML 报告（单文件）

### 顶层结构

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>Code Audit Report — {{ run_id }}</title>
  <style>{{ inline_css }}</style>
</head>
<body>
  <header class="report-banner">
    <h1>Code Audit Report</h1>
    <dl class="run-meta">
      <dt>Run ID</dt><dd>{{ run_id }}</dd>
      <dt>Target</dt><dd>{{ target }}</dd>
      <dt>Generated</dt><dd>{{ generated_at }}</dd>
      <dt>Pack</dt><dd>code-audit v{{ pack_version }}</dd>
    </dl>
  </header>

  <section class="summary">
    <div class="stat-card stat-total">{{ total }} findings</div>
    <div class="stat-card stat-critical">{{ critical }} critical</div>
    <div class="stat-card stat-high">{{ high }} high</div>
    <div class="stat-card stat-medium">{{ medium }} medium</div>
    <div class="stat-card stat-low">{{ low }} low</div>
    <div class="stat-card stat-info">{{ info }} info</div>
    <svg class="severity-donut">...</svg>
    <table class="by-module">...</table>
  </section>

  <section class="filters">
    <fieldset><legend>Severity</legend>
      <label><input type="checkbox" data-filter="severity" value="critical" checked> critical</label>
      ... (high / medium / low / info)
    </fieldset>
    <fieldset><legend>Category</legend>...</fieldset>
    <fieldset><legend>Confidence</legend>...</fieldset>
    <fieldset><legend>Module</legend>...</fieldset>
    <fieldset><legend>Verifier Status</legend>...</fieldset>
  </section>

  <main class="findings">
    {% for finding in confirmed_findings %}
    <article class="finding"
             data-severity="{{ finding.severity }}"
             data-category="{{ finding.category }}"
             data-confidence="{{ finding.confidence }}"
             data-module="{{ finding.module }}"
             data-verifier-status="{{ finding.verifier.status }}">
      <header>
        <span class="badge badge-severity-{{ finding.severity }}">{{ finding.severity }}</span>
        <span class="badge badge-category">{{ finding.category }}</span>
        <span class="badge badge-confidence-{{ finding.confidence }}">{{ finding.confidence }}</span>
        {% if file_changed %}<span class="warning">⚠ file changed since audit</span>{% endif %}
        <h2>{{ finding.title }}</h2>
        <code class="location">{{ finding.file }}:{{ finding.line_start }}-{{ finding.line_end }}</code>
      </header>
      <section class="description">{{ finding.description | escape }}</section>
      <section class="evidence">
        <pre><code>{{ finding.evidence.code_snippet | escape }}</code></pre>
        <dl>
          <dt>Reasoning</dt><dd>{{ finding.evidence.reasoning | escape }}</dd>
          <dt>Trigger</dt><dd>{{ finding.evidence.trigger_conditions | escape }}</dd>
          <dt>Expected vs Actual</dt><dd>{{ finding.evidence.expected_vs_actual | escape }}</dd>
          {% if finding.evidence.related_files %}
          <dt>Related</dt><dd><ul>{% for f in finding.evidence.related_files %}<li><code>{{ f }}</code></li>{% endfor %}</ul></dd>
          {% endif %}
        </dl>
      </section>
      <section class="suggested-fix">
        <h3>Suggested fix</h3>
        <p>{{ finding.suggested_fix | escape }}</p>
      </section>
      <footer class="audit-trail">
        <div class="reviewer">
          Reviewed by <code>{{ finding.reviewer.agent }}</code> at {{ finding.reviewer.ts }}
        </div>
        <div class="verifier">
          {{ finding.verifier.status }} by <code>{{ finding.verifier.agent }}</code> at {{ finding.verifier.ts }}
          <details>
            <summary>Reason &amp; evidence_check</summary>
            <p><strong>Reason:</strong> {{ finding.verifier.reason | escape }}</p>
            <p><strong>Evidence check:</strong> {{ finding.verifier.evidence_check | escape }}</p>
            {% if finding.verifier.severity_after %}
            <p><strong>Severity adjusted:</strong> {{ finding.severity_before }} → {{ finding.severity }}</p>
            {% endif %}
          </details>
        </div>
      </footer>
    </article>
    {% endfor %}
  </main>

  <details class="rejected-section">
    <summary>Rejected &amp; needs_more_evidence findings ({{ rejected_count }})</summary>
    <table>
      <thead><tr><th>id</th><th>module</th><th>file</th><th>status</th><th>reason</th></tr></thead>
      <tbody>...</tbody>
    </table>
  </details>

  <script>{{ inline_js }}</script>
</body>
</html>
```

### CSS 设计要点

- 全部 inline 在 `<style>` 中
- severity 配色：critical=#c0392b, high=#e67e22, medium=#f1c40f, low=#27ae60, info=#7f8c8d
- 卡片间隔、悬停高亮、code 块用等宽字体
- 移动端友好（max-width: 100% 自适应）
- 不依赖 Bootstrap / Tailwind / 任何外部框架

### JS 设计要点

- 全部 inline 在 `<script>` 中（vanilla JS，无依赖）
- 监听 `input[type=checkbox]` 的 change 事件，根据 `data-*` 属性切换 `article.finding` 的 `display: none`
- "复制 file:line" 按钮用 `navigator.clipboard.writeText`
- "展开 / 收起所有 evidence" 全局开关

### 文件漂移告警

渲染时为每条 finding 计算"当前 `file` 的 sha256"：

- 若文件存在且 sha 与 `file_sha256` 一致 → 不加 banner
- 若文件存在但 sha 不同 → 卡片顶部加 ⚠ "file changed since audit, line numbers may have shifted"
- 若文件已不存在 → 卡片顶部加 ⚠ "file no longer exists" + 仍展示原 code_snippet

## Excel 报告（可选，Slice C 落地）

### Sheet 1: Findings

| 列 | 字段 |
|---|---|
| A | id |
| B | module |
| C | file |
| D | line_start |
| E | line_end |
| F | title |
| G | category |
| H | severity |
| I | confidence |
| J | description |
| K | evidence.code_snippet（前 500 字符） |
| L | evidence.reasoning |
| M | evidence.trigger_conditions |
| N | evidence.expected_vs_actual |
| O | suggested_fix |
| P | reviewer.agent |
| Q | reviewer.ts |
| R | verifier.status |
| S | verifier.reason |
| T | verifier.evidence_check |
| U | severity_before（仅 upgrade/downgrade） |

第 1 行冻结表头，severity 列条件格式（背景色与 HTML 一致）。

### Sheet 2: Summary

| | runtime | knowledge | adapter | ... | Total |
|---|---|---|---|---|---|
| critical | N | N | N | ... | N |
| high | N | N | N | ... | N |
| medium | ... | | | | |
| low | | | | | |
| info | | | | | |
| **Total** | N | N | N | ... | N |

### Sheet 3: RunMeta

key-value 表：

| key | value |
|---|---|
| run_id | audit-2026-05-16-0435 |
| target | src/garage_os/ |
| generated_at | 2026-05-16T05:00:00Z |
| pack_version | 0.1.0 |
| total_findings | 47 |
| modules_audited | 7 |
| rejected_count | 12 |

### Sheet 4: Rejected

| id | module | file | status | verifier.reason |
|---|---|---|---|---|

## 行号文本协议

`<file>:<line_start>-<line_end>` 是默认协议字符串（人类可读 + 多数 IDE 支持复制粘贴跳转）。

未来可考虑根据用户配置生成 IDE 协议链接（`vscode://file/...` / `cursor://file/...`），但本 pack 第一版只输出纯文本协议（避免与 host adapter 绑定）。
