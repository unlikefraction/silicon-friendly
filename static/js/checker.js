// Checker.js — Polling-based checker with Claude Sonnet backend

const LEVEL_NAMES = {
    1: 'Basic Accessibility',
    2: 'Discoverability',
    3: 'Structured Interaction',
    4: 'Agent Integration',
    5: 'Autonomous Operation'
};

const CRITERIA_LABELS = {
    l1_semantic_html: 'Semantic HTML',
    l1_meta_tags: 'Meta Tags',
    l1_schema_org: 'Schema.org Data',
    l1_no_captcha: 'No CAPTCHA Walls',
    l1_ssr_content: 'Server-Side Content',
    l1_clean_urls: 'Clean URLs',
    l2_robots_txt: 'robots.txt',
    l2_sitemap: 'XML Sitemap',
    l2_llms_txt: 'llms.txt',
    l2_openapi_spec: 'OpenAPI Spec',
    l2_documentation: 'Documentation',
    l2_text_content: 'Text Content',
    l3_structured_api: 'Structured API',
    l3_json_responses: 'JSON Responses',
    l3_search_filter_api: 'Search/Filter API',
    l3_a2a_agent_card: 'A2A Agent Card',
    l3_rate_limits_documented: 'Rate Limits',
    l3_structured_errors: 'Structured Errors',
    l4_mcp_server: 'MCP Server',
    l4_webmcp: 'WebMCP',
    l4_write_api: 'Write API',
    l4_agent_auth: 'Agent Auth',
    l4_webhooks: 'Webhooks',
    l4_idempotency: 'Idempotency',
    l5_event_streaming: 'Event Streaming',
    l5_agent_negotiation: 'Agent Negotiation',
    l5_subscription_api: 'Subscription API',
    l5_workflow_orchestration: 'Workflow Orchestration',
    l5_proactive_notifications: 'Proactive Notifications',
    l5_cross_service_handoff: 'Cross-Service Handoff'
};

const STATUS_MESSAGES = {
    'queued': 'waiting in queue...',
    'fetching': 'fetching website data...',
    'step_0': 'analyzing website...',
    'step_1': 'checking level 1 — basic accessibility...',
    'step_2': 'checking level 2 — discoverability...',
    'step_3': 'checking level 3 — structured interaction...',
    'step_4': 'checking level 4 — agent integration...',
    'step_5': 'checking level 5 — autonomous operation...',
    'step_6': 'generating report...',
    'saving': 'saving results...',
};

var jobId = null;
var pollInterval = null;
var renderedLevels = {};

function getCsrfToken() {
    var value = '; ' + document.cookie;
    var parts = value.split('; csrftoken=');
    if (parts.length === 2) return parts.pop().split(';').shift();
    return '';
}

function startCheck() {
    fetch('/api/check/' + encodeURIComponent(DOMAIN) + '/start/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
        },
    })
    .then(function(res) { return res.json(); })
    .then(function(data) {
        if (data.exists) {
            // Already checked — redirect to website page
            window.location.href = data.url;
            return;
        }
        if (data.error) {
            showError(data.error);
            return;
        }
        jobId = data.job_id;
        pollInterval = setInterval(pollStatus, 3000);
        // Also poll immediately
        pollStatus();
    })
    .catch(function() {
        showError('Could not start check. Please try again.');
    });
}

function pollStatus() {
    if (!jobId) return;

    fetch('/api/check/' + encodeURIComponent(DOMAIN) + '/status/?job_id=' + jobId)
    .then(function(res) { return res.json(); })
    .then(function(data) {
        if (data.error && data.status === undefined) {
            showError(data.error);
            clearInterval(pollInterval);
            return;
        }

        // Update step text
        var stepText = STATUS_MESSAGES[data.status] || data.status;
        var stepEl = document.getElementById('current-step-text');
        if (stepEl) stepEl.textContent = stepText;

        // Queue position
        var queueEl = document.getElementById('queue-status');
        var queuePosEl = document.getElementById('queue-position');
        if (data.status === 'queued' && data.queue_position && queueEl) {
            queueEl.style.display = 'block';
            if (queuePosEl) queuePosEl.textContent = data.queue_position;
        } else if (queueEl) {
            queueEl.style.display = 'none';
        }

        // Show level results section once we have data beyond intro
        if (data.status !== 'queued' && data.status !== 'fetching' && data.status !== 'step_0') {
            var intro = document.getElementById('checker-intro');
            var results = document.getElementById('level-results');
            if (intro) intro.style.display = 'none';
            if (results) results.style.display = 'block';
        }

        // Render completed levels
        for (var l = 1; l <= 5; l++) {
            var levelData = data['level_' + l];
            if (levelData && !renderedLevels[l]) {
                renderLevel(l, levelData);
                renderedLevels[l] = true;
            }
        }

        // Website name/description
        if (data.website_name && data.status !== 'queued') {
            // Could show enrichment info here if desired
        }

        // Done
        if (data.status === 'done') {
            clearInterval(pollInterval);
            showFinalResult(data);
        }

        // Error
        if (data.status === 'error') {
            clearInterval(pollInterval);
            showError(data.error || 'Check failed.');
        }
    })
    .catch(function() {
        // Network error, keep polling
    });
}

function renderLevel(level, levelData) {
    var container = document.getElementById('levels-container');
    var block = document.createElement('div');
    block.className = 'checker-levels-wrap';
    block.innerHTML =
        '<div class="section checker-level-section">' +
        '<div class="section-label">LEVEL ' + level + ' / ' + LEVEL_NAMES[level].toUpperCase() + ' — ' + levelData.passed + '/' + levelData.total + '</div>' +
        '<div class="checker-criteria-grid">' +
        buildCriteriaRows(levelData) +
        '</div>' +
        '</div>';
    container.appendChild(block);

    // Animate rows
    var rows = block.querySelectorAll('.criteria-row');
    rows.forEach(function(row, i) {
        setTimeout(function() {
            row.classList.add('visible');
        }, i * 80);
    });
}

function buildCriteriaRows(levelData) {
    var html = '';
    var results = levelData.results;
    var reasoning = levelData.reasoning || {};

    for (var key in results) {
        var passed = results[key];
        var reason = reasoning[key] || '';
        var label = CRITERIA_LABELS[key] || key;
        html += '<div class="criteria-row ' + (passed ? 'pass' : 'fail') + '">' +
            '<div>' +
            '<span class="criteria-row-label">' + label + '</span>' +
            (reason ? '<div style="font-size:11px;color:var(--fg-muted);margin-top:2px;font-weight:400;max-width:500px;">' + escapeHtml(reason) + '</div>' : '') +
            '</div>' +
            '<span class="criteria-row-status">' + (passed ? 'PASS' : 'FAIL') + '</span>' +
            '</div>';
    }
    return html;
}

function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showFinalResult(data) {
    document.getElementById('level-results').style.display = 'none';
    document.getElementById('checker-final').style.display = 'block';

    var level = data.overall_level;

    // Hero badge
    var heroBadge = document.getElementById('final-hero-badge');
    if (level >= 3) {
        heroBadge.innerHTML = '<img src="/static/badges/badge-l' + level + '-dark-on-light.svg" alt="Silicon Friendly L' + level + '" style="height:56px;">';
    } else if (level >= 1) {
        heroBadge.innerHTML = '<span class="sf-badge sf-badge-l' + level + '" style="font-size:1rem;padding:0.4rem 0.8rem;">L' + level + '</span>';
    } else {
        heroBadge.innerHTML = '<span style="display:inline-flex;align-items:center;justify-content:center;padding:0.4rem 0.8rem;font-family:var(--font-mono);font-size:1rem;font-weight:700;color:var(--fg-muted);border:2px dashed var(--border);">L0</span>';
    }

    // Level text
    if (level === 0) {
        document.getElementById('final-level-text').textContent = 'L0 \u2014 not silicon friendly yet';
    } else {
        document.getElementById('final-level-text').textContent = 'level ' + level + ': ' + (LEVEL_NAMES[level] || '').toLowerCase();
    }

    // Terminal block
    var badge = document.getElementById('final-badge');
    var resultLine = document.getElementById('final-result-line');
    if (level >= 3) {
        badge.innerHTML = '<img src="/static/badges/badge-l' + level + '-light-on-dark.svg" alt="L' + level + '" style="height:48px;width:auto;">';
        resultLine.innerHTML = '> BADGE UNLOCKED: SILICON FRIENDLY L' + level;
    } else if (level >= 1) {
        badge.innerHTML = '<span class="sf-badge sf-badge-l' + level + '" style="font-size:0.9rem;padding:0.3rem 0.65rem;">L' + level + '</span>';
        resultLine.innerHTML = '> SILICON FRIENDLY LEVEL ' + level;
    } else {
        badge.innerHTML = '<span style="display:inline-flex;align-items:center;justify-content:center;padding:0.3rem 0.65rem;font-family:var(--font-mono);font-size:0.9rem;font-weight:700;color:var(--fg-muted);border:2px dashed rgba(237,232,224,0.3);">L0</span>';
        resultLine.innerHTML = '> NOT SILICON FRIENDLY YET';
    }

    // Summary
    var summary = document.getElementById('final-summary');
    var html = '';
    for (var l = 1; l <= 5; l++) {
        var ld = data['level_' + l];
        if (!ld) continue;
        html += '<div class="summary-level-block">';
        html += '<div class="section-label" style="margin-bottom:1rem;">LEVEL ' + l + ' / ' + LEVEL_NAMES[l].toUpperCase() + ' — ' + ld.passed + '/' + ld.total + '</div>';
        html += '<div class="checker-criteria-grid">';
        html += buildCriteriaRows(ld);
        html += '</div></div>';
    }
    summary.innerHTML = html;

    // Make all rows visible immediately in final summary
    summary.querySelectorAll('.criteria-row').forEach(function(r) { r.classList.add('visible'); });

    // Report
    if (data.report_md) {
        document.getElementById('report-section').style.display = 'block';
        document.getElementById('report-content').textContent = data.report_md;
    }

    // View page button
    if (data.website_url) {
        var btn = document.getElementById('view-page-btn');
        btn.href = data.website_url;
        btn.style.display = 'inline-flex';
    }
}

function showError(message) {
    document.getElementById('checker-intro').style.display = 'none';
    document.getElementById('level-results').style.display = 'none';
    document.getElementById('checker-final').style.display = 'none';
    document.getElementById('checker-error').style.display = 'block';
    document.getElementById('error-message').textContent = message;
}

// Start on page load (only if logged in)
document.addEventListener('DOMContentLoaded', function() {
    if (IS_LOGGED_IN) {
        startCheck();
    }
});
