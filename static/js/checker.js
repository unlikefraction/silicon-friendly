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
    try {
        const res = await fetch('/api/check/' + encodeURIComponent(DOMAIN) + '/');
        checkResults = await res.json();
    } catch(e) {
        document.getElementById('checker-intro').innerHTML =
            '<h1 class="hero-title">error.</h1>' +
            '<p class="hero-subtitle">could not check ' + DOMAIN + '. make sure the url is correct.</p>' +
            '<a href="/" class="btn btn-primary" style="margin-top:2rem;">Try Again</a>';
        return;
    }

    await sleep(1500);

    // Hide intro hero, show compact static hero + level section
    document.getElementById('checker-intro').style.display = 'none';
    document.getElementById('checker-hero-static').style.display = 'flex';
    document.getElementById('level-section').style.display = 'block';

    // Run through levels
    for (let level = 1; level <= 3; level++) {
        const levelKey = 'l' + level;
        const levelData = checkResults.results[levelKey];
        const levelSummary = checkResults.levels[levelKey];

        // Update section label
        showLevelLabel(level);

        // Build criteria grid
        const criteriaKeys = Object.keys(levelData);
        const grid = document.getElementById('criteria-grid');
        grid.innerHTML = '';

        for (let i = 0; i < criteriaKeys.length; i++) {
            const key = criteriaKeys[i];
            const row = createCriterionRow(key, i);
            grid.appendChild(row);
        }

        // Animate rows appearing
        await sleep(400);
        const rows = grid.querySelectorAll('.criteria-row');
        for (let i = 0; i < rows.length; i++) {
            rows[i].classList.add('visible');
            await sleep(120);
        }

        // Reveal results one by one with random delays
        for (let i = 0; i < criteriaKeys.length; i++) {
            const key = criteriaKeys[i];
            const result = levelData[key];
            const delay = 800 + Math.random() * 3500;
            await sleep(delay);
            revealCriterion(rows[i], result.pass);
        }

        // Show level result
        await sleep(800);
        const passed = levelSummary.pass;
        showLevelResult(level, passed, levelSummary.passed, levelSummary.total);

        if (!passed) {
            await sleep(1500);
            break;
        }

        if (level < 3) {
            await sleep(2000);
            document.getElementById('level-result').style.display = 'none';
        }
    }

    // Show final result
    await sleep(1500);
    showFinalResult();
}

function showLevelLabel(level) {
    const label = document.getElementById('level-label');
    label.textContent = 'LEVEL ' + level + ' / ' + LEVEL_NAMES[level].toUpperCase();

    // Reset animation
    label.classList.remove('animate');
    void label.offsetWidth;
    label.classList.add('animate');
}

function createCriterionRow(key, index) {
    const div = document.createElement('div');
    div.className = 'criteria-row';
    div.style.animationDelay = (index * 0.08) + 's';
    div.innerHTML =
        '<span class="criteria-row-label">' + (CRITERIA_LABELS[key] || key) + '</span>' +
        '<span class="criteria-row-status"><span class="criterion-spinner"></span></span>';
    return div;
}

function revealCriterion(row, passed) {
    const status = row.querySelector('.criteria-row-status');
    row.classList.add(passed ? 'pass' : 'fail');
    status.textContent = passed ? 'PASS' : 'FAIL';
}

function showLevelResult(level, passed, count, total) {
    const result = document.getElementById('level-result');
    const text = document.getElementById('level-result-text');

    if (passed) {
        text.innerHTML = '> LEVEL ' + level + ' PASSED — ' + count + '/' + total + ' criteria met';
        result.className = 'checker-level-result level-passed';
    } else {
        text.innerHTML = '> STOPPED AT LEVEL ' + level + ' — ' + count + '/' + total + ' criteria met';
        result.className = 'checker-level-result level-failed';
    }
    result.style.display = 'block';
}

function showFinalResult() {
    document.getElementById('level-section').style.display = 'none';
    document.getElementById('checker-hero-static').style.display = 'none';
    const final = document.getElementById('checker-final');
    final.style.display = 'block';

    const level = checkResults.overall_level;

    // Set hero domain
    const domainTitle = document.getElementById('final-domain-title');
    domainTitle.innerHTML = DOMAIN + '.';

    const levelNames = {0: 'Not Yet Friendly', 1: 'Basic Accessibility', 2: 'Discoverable', 3: 'Structured Interaction'};
    document.getElementById('final-level-text').textContent = 'level ' + level + ': ' + (levelNames[level] || 'silicon friendly');

    // Badge in terminal block
    const badge = document.getElementById('final-badge');
    const resultLine = document.getElementById('final-result-line');

    if (level >= 3) {
        badge.innerHTML =
            '<div class="badge-unlock-container">' +
            '<div class="badge-unlock-glow" style="--glow-color: ' + ({3: '#7C3AED', 4: '#059669', 5: '#4f46e5'}[level] || '#4f46e5') + '"></div>' +
            '<img src="/static/badges/credential-l' + level + '.svg" alt="Silicon Friendly L' + level + '" class="badge-unlock-img">' +
            '</div>';
        requestAnimationFrame(function() {
            requestAnimationFrame(function() {
                badge.querySelector('.badge-unlock-container').classList.add('unlocked');
            });
        });
        resultLine.innerHTML = '> BADGE UNLOCKED: SILICON FRIENDLY L' + level;
    } else {
        badge.innerHTML = '<span class="sf-badge sf-badge-lg level-' + level + '-bg">L' + level + '</span>';
        resultLine.innerHTML = '> SILICON FRIENDLY LEVEL ' + level;
    }

    // Build summary with grid rows per level
    const summary = document.getElementById('final-summary');
    let html = '';
    for (let l = 1; l <= 3; l++) {
        const lk = 'l' + l;
        const ld = checkResults.results[lk];
        const ls = checkResults.levels[lk];
        html += '<div class="summary-level-block">';
        html += '<div class="section-label" style="margin-bottom:1rem;">LEVEL ' + l + ' / ' + LEVEL_NAMES[l].toUpperCase() + ' — ' + ls.passed + '/' + ls.total + '</div>';
        html += '<div class="checker-criteria-grid">';
        for (const [key, val] of Object.entries(ld)) {
            html += '<div class="criteria-row visible ' + (val.pass ? 'pass' : 'fail') + '">' +
                '<span class="criteria-row-label">' + (CRITERIA_LABELS[key] || key) + '</span>' +
                '<span class="criteria-row-status">' + (val.pass ? 'PASS' : 'FAIL') + '</span>' +
                '</div>';
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

    if (typeof renderBubbleChart === 'function') {
        fetch('/api/check/' + encodeURIComponent(DOMAIN) + '/similar/')
            .then(function(r) { return r.json(); })
            .then(function(data) {
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
    return new Promise(function(resolve) { setTimeout(resolve, ms); });
}

document.addEventListener('DOMContentLoaded', startCheck);
