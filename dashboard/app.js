// API Base URL
const API_BASE = '/api';

// State
let charts = {};
let pollingInterval = null;
let currentTab = 'overview';

// Formatting Utilities
const formatDate = (isoString) => {
    if (!isoString) return '-';
    const date = new Date(isoString);
    return date.toLocaleString();
};

const formatTimeAgo = (isoString) => {
    if (!isoString) return '-';
    const date = new Date(isoString);
    const now = new Date();
    const diff = Math.floor((now - date) / 1000); // seconds

    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
};

// --- Initialization ---

document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
    initCharts();
    loadDashboardData();

    // Start Polling (every 30s)
    pollingInterval = setInterval(loadDashboardData, 30000);
});

// --- Tab Navigation ---

function switchTab(tabId) {
    // Update Nav
    document.querySelectorAll('.nav-links li').forEach(li => li.classList.remove('active'));
    document.querySelector(`.nav-links li[onclick="switchTab('${tabId}')"]`).classList.add('active');

    // Update Content
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    document.getElementById(`tab-${tabId}`).classList.add('active');

    currentTab = tabId;
}

// --- Data Loading ---

async function loadDashboardData() {
    updateLastUpdatedTime();

    try {
        await Promise.all([
            loadStats(),
            loadKpis(),
            loadFailureFeed(),
            loadAuditTrail(),
            loadRepositories()
        ]);
    } catch (error) {
        console.error("Failed to load dashboard data:", error);
    }
}

function updateLastUpdatedTime() {
    const now = new Date();
    document.getElementById('last-updated-time').textContent = now.toLocaleTimeString();
}

// --- API Calls & UI Updates ---

async function loadStats() {
    const res = await fetch(`${API_BASE}/stats`);
    const stats = await res.json();

    document.getElementById('kpi-failures-today').textContent = stats.total_failures_today;
    document.getElementById('kpi-success-rate').textContent = `${stats.success_rate_24h.toFixed(1)}%`;
    document.getElementById('kpi-avg-time').textContent = `${stats.avg_resolution_time_minutes.toFixed(1)} min`;
    document.getElementById('kpi-patterns').textContent = stats.patterns_learned;

    const openCircuitsEl = document.getElementById('kpi-open-circuits');
    openCircuitsEl.textContent = stats.circuit_breakers_open;
    if (stats.circuit_breakers_open > 0) openCircuitsEl.classList.add('alert');
    else openCircuitsEl.classList.remove('alert');

    // Update charts if on overview tab
    if (currentTab === 'overview') {
        loadChartsData();
    }
}

async function loadKpis() {
    const res = await fetch(`${API_BASE}/metrics/kpis`);
    const kpis = await res.json();
    document.getElementById('kpi-time-saved').textContent = `${kpis.time_saved_hours.toFixed(1)}h`;
}

async function loadChartsData() {
    // 1. Timeline
    const timelineRes = await fetch(`${API_BASE}/metrics/timeline?hours=24`);
    const timelineData = await timelineRes.json();
    updateChart('timeline', timelineData.labels, timelineData.data);

    // 2. Risk Distribution
    const riskRes = await fetch(`${API_BASE}/metrics/risk-distribution`);
    const riskData = await riskRes.json();
    updateChart('risk', Object.keys(riskData), Object.values(riskData));

    // 3. Categories
    const catRes = await fetch(`${API_BASE}/metrics/category-distribution`);
    const catData = await catRes.json();
    updateChart('categories', Object.keys(catData.categories), Object.values(catData.categories));
}

async function loadFailureFeed() {
    const res = await fetch(`${API_BASE}/failures/feed?limit=20`);
    const failures = await res.json();

    const tbody = document.getElementById('failures-table-body');
    tbody.innerHTML = '';

    failures.forEach(f => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><span class="badge ${f.status.toLowerCase()}">${f.status}</span></td>
            <td>${f.repository}</td>
            <td>${f.workflow_name}</td>
            <td>${f.failure_reason}</td>
            <td>${f.risk_score}/10</td>
            <td>${formatTimeAgo(f.created_at)}</td>
            <td><button class="btn-action" onclick="showFailureDetails('${f.failure_id}')">View</button></td>
        `;
        tbody.appendChild(tr);
    });
}

async function loadAuditTrail() {
    const res = await fetch(`${API_BASE}/audit/trail?limit=20`);
    const audit = await res.json();

    const container = document.getElementById('audit-list-container');
    container.innerHTML = '';

    if (audit.length === 0) {
        container.innerHTML = '<div class="empty-state">No audit logs found</div>';
        return;
    }

    const table = document.createElement('table');
    table.className = 'data-table';
    table.innerHTML = `
        <thead>
            <tr>
                <th>Time</th>
                <th>Actor</th>
                <th>Action</th>
                <th>Outcome</th>
                <th>Details</th>
            </tr>
        </thead>
        <tbody>
            ${audit.map(log => `
                <tr>
                    <td>${formatTimeAgo(log.timestamp)}</td>
                    <td>${log.actor}</td>
                    <td>${log.action_type}</td>
                    <td>${log.outcome}</td>
                    <td>${JSON.stringify(log.details).substring(0, 50)}...</td>
                </tr>
            `).join('')}
        </tbody>
    `;
    container.appendChild(table);
}

async function loadRepositories() {
    const res = await fetch(`${API_BASE}/repositories`);
    const repos = await res.json();

    const grid = document.getElementById('repo-grid-container');
    grid.innerHTML = '';

    repos.forEach(repo => {
        const card = document.createElement('div');
        card.className = 'kpi-card'; // Reuse card style
        card.style.cursor = 'pointer';
        card.onclick = () => showRepoProfile(repo);

        card.innerHTML = `
            <div class="kpi-label">Repository</div>
            <div class="kpi-value" style="font-size: 18px; margin-bottom: 10px;">${repo}</div>
            <div style="font-size: 12px; color: var(--accent);">Click to view health profile →</div>
        `;
        grid.appendChild(card);
    });
}

// --- Charts ---

function initCharts() {
    Chart.defaults.color = '#8b949e';
    Chart.defaults.borderColor = '#30363d';

    // Timeline Chart
    const ctxTimeline = document.getElementById('chart-timeline').getContext('2d');
    charts.timeline = new Chart(ctxTimeline, {
        type: 'bar',
        data: { labels: [], datasets: [{ label: 'Failures', data: [], backgroundColor: '#58a6ff' }] },
        options: { responsive: true, maintainAspectRatio: false }
    });

    // Risk Chart
    const ctxRisk = document.getElementById('chart-risk').getContext('2d');
    charts.risk = new Chart(ctxRisk, {
        type: 'doughnut',
        data: {
            labels: ['Low', 'Med-Low', 'Med', 'Med-High', 'High'],
            datasets: [{ data: [], backgroundColor: ['#238636', '#3fb950', '#d29922', '#db6d28', '#f85149'], borderWidth: 0 }]
        },
        options: { responsive: true, maintainAspectRatio: false, cutout: '70%' }
    });

    // Categories Chart
    const ctxCat = document.getElementById('chart-categories').getContext('2d');
    charts.categories = new Chart(ctxCat, {
        type: 'bar',
        data: { labels: [], datasets: [{ label: 'Count', data: [], backgroundColor: '#bc8cff' }] },
        options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false }
    });
}

function updateChart(chartId, labels, data) {
    if (charts[chartId]) {
        charts[chartId].data.labels = labels;
        charts[chartId].data.datasets[0].data = data;
        charts[chartId].update();
    }
}

// --- Modals ---

async function showFailureDetails(failureId) {
    const modal = document.getElementById('failure-modal');
    const body = document.getElementById('modal-body');
    body.innerHTML = 'Loading...';
    modal.style.display = 'block';

    try {
        const res = await fetch(`${API_BASE}/failures/${failureId}`);
        const data = await res.json();

        body.innerHTML = `
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                <div>
                    <h3>Overview</h3>
                    <p><strong>Repo:</strong> ${data.repository}</p>
                    <p><strong>Branch:</strong> ${data.branch}</p>
                    <p><strong>Workflow:</strong> ${data.workflow_run_id}</p>
                    <p><strong>Status:</strong> <span class="badge ${data.status.toLowerCase()}">${data.status}</span></p>
                </div>
                <div>
                    <h3>Analysis</h3>
                    <p><strong>Category:</strong> ${data.analysis?.category || 'Pending'}</p>
                    <p><strong>Risk Score:</strong> ${data.analysis?.risk_score || 0}/10</p>
                    <p><strong>Confidence:</strong> ${data.analysis?.confidence || 0}%</p>
                </div>
            </div>
            
            <h3>Reasoning</h3>
            <div style="background: rgba(0,0,0,0.2); padding: 15px; border-radius: 6px;">
                ${data.analysis?.reasoning || 'No analysis available yet.'}
            </div>
            
            <h3>Proposed Fix</h3>
            <pre style="background: #0d1117; padding: 15px; border-radius: 6px; overflow-x: auto;"><code>${data.analysis?.proposed_fix || 'No fix proposed yet.'}</code></pre>
            
            <h3>Logs</h3>
            <pre style="background: #0d1117; padding: 15px; border-radius: 6px; overflow-x: auto; max-height: 200px;"><code>${data.logs.substring(0, 2000)}...</code></pre>
        `;
    } catch (e) {
        body.innerHTML = `<p style="color: var(--danger)">Failed to load details: ${e.message}</p>`;
    }
}

async function showRepoProfile(repo) {
    const modal = document.getElementById('profile-modal');
    const body = document.getElementById('profile-body');
    body.innerHTML = 'Loading...';
    modal.style.display = 'block';

    try {
        const res = await fetch(`${API_BASE}/repositories/${repo}/profile`);
        const data = await res.json();

        body.innerHTML = `
            <div class="kpi-grid">
                <div class="kpi-card"><div class="kpi-label">Total Failures</div><div class="kpi-value">${data.total_failures}</div></div>
                <div class="kpi-card"><div class="kpi-label">Success Rate</div><div class="kpi-value">${data.success_rate.toFixed(1)}%</div></div>
                <div class="kpi-card"><div class="kpi-label">Flaky Rate</div><div class="kpi-value">${(data.flaky_test_rate * 100).toFixed(1)}%</div></div>
            </div>
            
            <h3>Attributes</h3>
            <ul>
                <li>Most common failure: <strong>${data.most_common_category}</strong></li>
                <li>Worst day: <strong>${data.most_common_day}</strong></li>
                <li>Worst hour: <strong>${data.most_common_hour}:00 UTC</strong></li>
            </ul>
            
            <h3>Learned Patterns</h3>
            ${data.patterns.length > 0 ? `
                <ul class="nav-links">
                    ${data.patterns.map(p => `
                        <li style="display: block; cursor: default;">
                            <strong>${p.pattern_type}</strong> (${(p.frequency * 100).toFixed(0)}% freq)<br>
                            <span style="font-size: 12px; color: var(--text-secondary)">${p.description}</span>
                        </li>
                    `).join('')}
                </ul>
            ` : '<p>No specific patterns learned yet.</p>'}
        `;
    } catch (e) {
        body.innerHTML = `<p style="color: var(--danger)">Failed to load profile (or no profile exists for this repo): ${e.message}</p>`;
    }
}

// Close Modals
document.querySelectorAll('.close-modal').forEach(btn => {
    btn.onclick = () => {
        document.querySelectorAll('.modal').forEach(m => m.style.display = 'none');
    };
});

window.onclick = (event) => {
    if (event.target.classList.contains('modal')) {
        event.target.style.display = 'none';
    }
};
