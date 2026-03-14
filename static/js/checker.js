// Checker.js - Gamified website checker animation engine

const LEVEL_NAMES = {
    1: 'Basic Accessibility',
    2: 'Discoverability',
    3: 'Structured Interaction'
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
    l3_a2a_agent_card: 'A2A Agent Card',
    l3_structured_api: 'Structured API',
    l3_json_responses: 'JSON Responses',
    l3_search_filter_api: 'Search/Filter API',
    l3_rate_limits_documented: 'Rate Limits',
    l3_structured_errors: 'Structured Errors'
};

let checkResults = null;

async function startCheck() {
    // Fetch results from API
    try {
        const res = await fetch('/api/check/' + encodeURIComponent(DOMAIN) + '/');
        checkResults = await res.json();
    } catch(e) {
        document.getElementById('checker-intro').innerHTML = '<h1>Error</h1><p>Could not check ' + DOMAIN + '. Make sure the URL is correct.</p><a href="/" class="btn btn-primary">Try Again</a>';
        return;
    }

    // Start the animation sequence
    await sleep(1500);
    document.getElementById('checker-intro').style.display = 'none';
    document.getElementById('level-section').style.display = 'block';

    // Run through levels
    for (let level = 1; level <= 3; level++) {
        const levelKey = 'l' + level;
        const levelData = checkResults.results[levelKey];
        const levelSummary = checkResults.levels[levelKey];

        // Show level announcement
        await showLevelAnnounce(level);

        // Show criteria one by one with random delays
        const criteriaKeys = Object.keys(levelData);
        const grid = document.getElementById('criteria-grid');
        grid.innerHTML = '';

        // Create all boxes first (hidden)
        for (let i = 0; i < criteriaKeys.length; i++) {
            const key = criteriaKeys[i];
            const box = createCriterionBox(key, i);
            grid.appendChild(box);
        }

        // Animate boxes appearing (staggered)
        await sleep(500);
        const boxes = grid.querySelectorAll('.criterion-box');
        for (let i = 0; i < boxes.length; i++) {
            boxes[i].classList.add('visible');
            await sleep(150);
        }

        // Reveal results one by one with random delays
        for (let i = 0; i < criteriaKeys.length; i++) {
            const key = criteriaKeys[i];
            const result = levelData[key];
            const delay = 1000 + Math.random() * 4000; // 1-5 seconds
            await sleep(delay);
            revealCriterion(boxes[i], result.pass);
        }

        // Show level result
        await sleep(800);
        const passed = levelSummary.pass;
        showLevelResult(level, passed, levelSummary.passed, levelSummary.total);

        if (!passed) {
            // Failed this level - stop here
            await sleep(1500);
            break;
        }

        if (level < 3) {
            // Passed - transition to next level
            await sleep(2000);
            document.getElementById('level-result').style.display = 'none';
        }
    }

    // Show final result
    await sleep(1500);
    showFinalResult();
}

async function showLevelAnnounce(level) {
    const title = document.getElementById('level-title');
    const subtitle = document.getElementById('level-subtitle');
    const announce = document.getElementById('level-announce');

    title.textContent = 'LEVEL ' + level;
    subtitle.textContent = LEVEL_NAMES[level];

    announce.style.display = 'block';
    announce.classList.remove('animate');
    void announce.offsetWidth; // reflow
    announce.classList.add('animate');

    await sleep(1200);
}

function createCriterionBox(key, index) {
    const div = document.createElement('div');
    div.className = 'criterion-box';
    div.style.animationDelay = (index * 0.1) + 's';
    div.innerHTML = `
        <div class="criterion-icon">
            <div class="criterion-spinner"></div>
        </div>
        <div class="criterion-label">${CRITERIA_LABELS[key] || key}</div>
    `;
    return div;
}

function revealCriterion(box, passed) {
    const icon = box.querySelector('.criterion-icon');
    box.classList.add(passed ? 'pass' : 'fail');
    icon.innerHTML = passed
        ? '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#00ff88" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>'
        : '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ff4444" stroke-width="3"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
}

function showLevelResult(level, passed, count, total) {
    const result = document.getElementById('level-result');
    const text = document.getElementById('level-result-text');

    if (passed) {
        text.innerHTML = `<span class="result-pass">PASSED L${level}</span> <span class="result-score">${count}/${total}</span>`;
        result.className = 'level-result level-passed';
    } else {
        text.innerHTML = `<span class="result-fail">STOPPED AT L${level}</span> <span class="result-score">${count}/${total}</span>`;
        result.className = 'level-result level-failed';
    }
    result.style.display = 'block';
}

function showFinalResult() {
    document.getElementById('level-section').style.display = 'none';
    const final = document.getElementById('checker-final');
    final.style.display = 'block';

    const level = checkResults.overall_level;
    const badge = document.getElementById('final-badge');
    badge.innerHTML = `<span class="sf-badge sf-badge-lg level-${level}-bg">L${level}</span>`;

    document.getElementById('final-domain').textContent = DOMAIN;

    const levelNames = {0: 'Not Yet Friendly', 1: 'Basic Accessibility', 2: 'Discoverable', 3: 'Structured Interaction'};
    document.getElementById('final-level-text').textContent = 'Level ' + level + ': ' + (levelNames[level] || 'Silicon Friendly');

    // Build summary
    const summary = document.getElementById('final-summary');
    let html = '';
    for (let l = 1; l <= 3; l++) {
        const lk = 'l' + l;
        const ld = checkResults.results[lk];
        html += `<div class="summary-level"><h4>Level ${l}</h4><div class="summary-criteria">`;
        for (const [key, val] of Object.entries(ld)) {
            html += `<div class="summary-item ${val.pass ? 'pass' : 'fail'}">
                <span class="criterion-check">${val.pass ? '&#10003;' : '&#10007;'}</span>
                <span>${CRITERIA_LABELS[key] || key}</span>
            </div>`;
        }
        html += '</div></div>';
    }
    summary.innerHTML = html;

    // Show upsell after a delay
    setTimeout(function() {
        document.getElementById('upsell-section').style.display = 'block';
    }, 2000);
}

function showComparison() {
    document.getElementById('comparison-cta').style.display = 'none';
    document.getElementById('bubble-container').style.display = 'block';

    // Use the bubble chart from bubbles.js
    if (typeof renderBubbleChart === 'function') {
        // Fetch similar websites
        fetch('/api/check/' + encodeURIComponent(DOMAIN) + '/similar/')
            .then(r => r.json())
            .then(data => {
                if (data.websites) {
                    renderBubbleChart(data.websites, DOMAIN, checkResults.overall_level);
                    document.getElementById('rank-text').style.display = 'block';
                    document.getElementById('rank-text').textContent = 'You rank #' + (data.rank || '?') + ' out of ' + data.websites.length + ' in your category';
                }
            })
            .catch(function() {
                document.getElementById('bubble-container').innerHTML = '<p>Could not load comparison data.</p>';
            });
    }
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Start the check when page loads
document.addEventListener('DOMContentLoaded', startCheck);
