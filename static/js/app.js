/**
 * VC/PE 学术论文推送站 — 前端逻辑 v4
 * 处理论文列表渲染、搜索、筛选、分页、翻译
 * 专注：风险投资 | 创业投资 | 私募股权 | 引导基金
 */

// ==================== 状态管理 ====================

const state = {
    papers: [],
    currentPage: 1,
    totalPages: 1,
    perPage: 20,
    filters: {
        q: "",
        year: "",
        journal: "",
        topic: "",
        oa: false,
        sort: "newest",
    },
    stats: {
        total: 0,
        journalCount: 0,
        oaCount: 0,
    },
    translatedCache: {},
};

// ==================== API 封装 ====================

const API_BASE = "/api";

async function fetchPapers(page = 1) {
    const params = new URLSearchParams({
        page: page,
        sort: state.filters.sort,
    });

    if (state.filters.q) params.set("q", state.filters.q);
    if (state.filters.year) params.set("year", state.filters.year);
    if (state.filters.journal) params.set("journal", state.filters.journal);
    if (state.filters.topic) params.set("topic", state.filters.topic);
    if (state.filters.oa) params.set("oa", "1");

    const resp = await fetch(`${API_BASE}/papers?${params}`);
    if (!resp.ok) throw new Error("获取论文失败");
    return resp.json();
}

async function fetchStats() {
    const resp = await fetch(`${API_BASE}/stats`);
    if (!resp.ok) throw new Error("获取统计失败");
    return resp.json();
}

async function fetchJournals() {
    const resp = await fetch(`${API_BASE}/journals`);
    if (!resp.ok) throw new Error("获取期刊失败");
    return resp.json();
}

async function translateText(text) {
    if (state.translatedCache[text]) {
        return state.translatedCache[text];
    }

    try {
        const resp = await fetch(`${API_BASE}/translate`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({text, target: "ZH"}),
        });

        if (!resp.ok) throw new Error("翻译失败");

        const result = await resp.json();
        state.translatedCache[text] = result.translated;
        return result.translated;
    } catch (e) {
        return "[翻译失败，请稍后重试]";
    }
}

// ==================== 渲染函数 ====================

function renderStats(stats) {
    document.getElementById("total-count").textContent = stats.total;
    document.getElementById("journal-count").textContent = stats.journal_count;
    document.getElementById("oa-count").textContent = stats.oa_count;

    state.stats = stats;
}

function renderJournals(journals) {
    const select = document.getElementById("journal-filter");
    select.innerHTML = '<option value="">全部期刊</option>';

    journals.forEach((j) => {
        const opt = document.createElement("option");
        opt.value = j.name;
        opt.textContent = `${j.name} (${j.count})`;
        select.appendChild(opt);
    });
}

function renderYearFilters() {
    const container = document.getElementById("year-filters");
    if (!state.stats.by_year) return;

    const years = Object.keys(state.stats.by_year)
        .filter((y) => y !== "未知")
        .sort((a, b) => b - a)
        .slice(0, 15);

    let html = '<span class="year-pill active" data-year="">全部</span>';
    years.forEach((y) => {
        html += `<span class="year-pill" data-year="${y}">${y}</span>`;
    });

    container.innerHTML = html;

    container.querySelectorAll(".year-pill").forEach((pill) => {
        pill.addEventListener("click", () => {
            container.querySelectorAll(".year-pill").forEach((p) => p.classList.remove("active"));
            pill.classList.add("active");
            state.filters.year = pill.dataset.year;
            state.currentPage = 1;
            loadPapers();
        });
    });
}

function getTagStyle(tag) {
    const map = {
        "风险投资/创业投资": {bg: "var(--accent)", color: "white"},
        "私募股权": {bg: "#1565c0", color: "white"},
        "政府引导基金": {bg: "#2e7d32", color: "white"},
        "LP/GP": {bg: "#7b1fa2", color: "white"},
        "退出机制": {bg: "#c62828", color: "white"},
        "公司创业投资": {bg: "#00838f", color: "white"},
        "创业与创新": {bg: "#f57f17", color: "white"},
        "业绩与回报": {bg: "#4527a0", color: "white"},
        "投资决策": {bg: "#00695c", color: "white"},
        "公司治理": {bg: "#37474f", color: "white"},
        "中国": {bg: "#fff3e0", color: "#bf360c"},
        "美国": {bg: "#e3f2fd", color: "#0d47a1"},
        "欧洲": {bg: "#f3e5f5", color: "#4a148c"},
    };
    const style = map[tag] || {bg: "var(--bg)", color: "var(--text-secondary)"};
    return `background: ${style.bg}; color: ${style.color};`;
}

function renderPapers(papers) {
    const container = document.getElementById("paper-list-container");

    if (!papers || papers.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                </svg>
                <h3>暂未找到 VC/PE 相关论文</h3>
                <p>请调整筛选条件或等待新论文入库</p>
            </div>
        `;
        return;
    }

    container.innerHTML = papers.map((paper, idx) => {
        const tags = (paper.auto_tags || []).filter(t => !['中国', '美国', '欧洲', '其他'].includes(t));
        const regionTags = (paper.auto_tags || []).filter(t => ['中国', '美国', '欧洲'].includes(t));
        const tagHtml = tags.map((t) => `<span class="paper-vcpe-tag">${t}</span>`).join("");
        const regionTagHtml = regionTags.map((t) => `<span class="paper-tag">${t}</span>`).join("");
        const keywords = (paper.keywords || []).slice(0, 6);
        const kwHtml = keywords.map((k) => `<span class="paper-keyword">${k}</span>`).join("");
        const authors = paper.authors ? paper.authors.slice(0, 5).join(", ") : "未知作者";
        const isSsrn = paper.source === 'SSRN' || paper.paper_type === 'working_paper';
        const oaBadge = paper.is_oa
            ? '<span class="paper-oa-badge">OA</span>'
            : "";

        return `
            <div class="paper-card" data-idx="${idx}">
                <div>
                    <span class="paper-category-badge ${paper.category || 'Other'}">${paper.category || 'Other'}</span>
                    ${isSsrn ? '<span class="paper-source-badge SSRN">SSRN</span>' : ''}
                    ${oaBadge}
                </div>
                <div class="paper-title" onclick="openModal(${idx})">${paper.title || "无标题"}</div>
                <div class="paper-meta">
                    <span>📖 ${paper.journal || "未知期刊"}</span>
                    <span>📅 ${paper.year || "未知年份"}</span>
                    ${paper.cited_by ? `<span>📊 被引 ${paper.cited_by}</span>` : ""}
                </div>
                <div class="paper-authors">👤 ${authors}${paper.authors && paper.authors.length > 5 ? "..." : ""}</div>
                <div class="paper-abstract" id="abstract-${idx}">${paper.abstract ? paper.abstract.slice(0, 300) + (paper.abstract.length > 300 ? '...' : '') : "暂无摘要"}</div>
                ${tags.length > 0 ? `<div class="paper-vcpe-tags">${tagHtml}</div>` : ""}
                ${regionTagHtml ? `<div class="paper-tags">${regionTagHtml}</div>` : ""}
                <div class="paper-actions">
                    <a href="${paper.url || (paper.doi ? `https://doi.org/${paper.doi}` : '#')}" target="_blank"
                       class="btn btn-primary" ${!paper.doi ? 'onclick="return false;"' : ''}>
                        前往期刊
                    </a>
                    ${isSsrn ? `
                    <button class="btn btn-secondary" onclick="window.open('${paper.url || '#'}', '_blank')">
                        SSRN 链接
                    </button>
                    ` : ''}
                </div>
            </div>
        `;
    }).join("");

    state.currentPapers = papers;
}

function renderPagination(page, totalPages) {
    const container = document.getElementById("pagination");
    if (totalPages <= 1) {
        container.innerHTML = "";
        return;
    }

    let html = "";

    html += `<a class="page-btn ${page === 1 ? "disabled" : ""}" onclick="${page !== 1 ? `gotoPage(${page - 1})` : ""}">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15,18 9,12 15,6"/></svg>
    </a>`;

    const maxVisible = 5;
    let startPage = Math.max(1, page - Math.floor(maxVisible / 2));
    let endPage = Math.min(totalPages, startPage + maxVisible - 1);

    if (endPage - startPage < maxVisible - 1) {
        startPage = Math.max(1, endPage - maxVisible + 1);
    }

    if (startPage > 1) {
        html += `<a class="page-btn" onclick="gotoPage(1)">1</a>`;
        if (startPage > 2) html += `<span style="color: var(--text-secondary); padding: 0 0.25rem;">...</span>`;
    }

    for (let i = startPage; i <= endPage; i++) {
        html += `<a class="page-btn ${i === page ? "active" : ""}" onclick="gotoPage(${i})">${i}</a>`;
    }

    if (endPage < totalPages) {
        if (endPage < totalPages - 1) html += `<span style="color: var(--text-secondary); padding: 0 0.25rem;">...</span>`;
        html += `<a class="page-btn" onclick="gotoPage(${totalPages})">${totalPages}</a>`;
    }

    html += `<a class="page-btn ${page === totalPages ? "disabled" : ""}" onclick="${page !== totalPages ? `gotoPage(${page + 1})` : ""}">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9,18 15,12 9,6"/></svg>
    </a>`;

    container.innerHTML = html;
}

// ==================== 交互处理 ====================

function openModal(idx) {
    const paper = state.currentPapers[idx];
    if (!paper) return;

    const tags = (paper.auto_tags || []).map(
        (t) => `<span class="paper-tag" style="${getTagStyle(t)}">${t}</span>`
    ).join("");

    const modalHtml = `
        <div class="modal-overlay active" id="detail-modal" onclick="closeModal(event)">
            <div class="modal" onclick="event.stopPropagation()">
                <div class="modal-header">
                    <h2>论文详情</h2>
                    <button class="modal-close" onclick="closeModal()">&times;</button>
                </div>
                <div class="modal-body">
                    <h3 style="font-size: 1.1rem; color: var(--primary); margin-bottom: 1rem; line-height: 1.5;">${paper.title || "无标题"}</h3>
                    <div class="paper-meta" style="margin-bottom: 1.5rem;">
                        <span class="paper-meta-item">${(paper.authors || []).join(", ")}</span>
                        <span class="paper-meta-item"><strong>${paper.journal || "未知期刊"}</strong></span>
                        <span class="paper-meta-item">${paper.year || "未知年份"}</span>
                        ${paper.doi ? `<span class="paper-meta-item">DOI: ${paper.doi}</span>` : ""}
                    </div>
                    ${tags ? `<div style="margin-bottom: 1.5rem;">${tags}</div>` : ""}
                    <div style="margin-bottom: 1.5rem;">
                        <strong style="font-size: 0.85rem; color: var(--text-secondary); display: block; margin-bottom: 0.5rem;">摘要</strong>
                        <div class="paper-abstract" style="font-size: 0.9rem;">${paper.abstract || "暂无摘要"}</div>
                    </div>
                    <div class="paper-actions" style="border-top: none; padding-top: 0;">
                        <a href="${paper.url || (paper.doi ? `https://doi.org/${paper.doi}` : '#')}" target="_blank"
                           class="btn btn-primary" ${!paper.doi ? 'onclick="return false;"' : ''}>
                            前往期刊
                        </a>
                    </div>
                </div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML("beforeend", modalHtml);
}

function closeModal(event) {
    if (event && event.target !== event.currentTarget) return;
    const modal = document.getElementById("detail-modal");
    if (modal) modal.remove();
}

function showOaHint() {
    alert("本文为付费订阅论文，全文需通过机构账号访问获取。\n\n如需下载全文，请使用学校图书馆提供的远程访问服务。");
}

function gotoPage(page) {
    state.currentPage = page;
    loadPapers();
    window.scrollTo({top: 0, behavior: "smooth"});
}

// ==================== 数据加载 ====================

async function loadPapers() {
    const container = document.getElementById("paper-list-container");
    container.innerHTML = `
        <div class="loading">
            <div class="loading-spinner"></div>
            <p>正在加载 VC/PE 相关论文...</p>
        </div>
    `;

    try {
        const data = await fetchPapers(state.currentPage);
        state.papers = data.papers;
        state.totalPages = data.total_pages;
        state.perPage = data.per_page;

        document.getElementById("paper-total").textContent = data.total;

        renderPapers(data.papers);
        renderPagination(state.currentPage, state.totalPages);
    } catch (e) {
        container.innerHTML = `
            <div class="empty-state">
                <h3>加载失败</h3>
                <p>${e.message}</p>
            </div>
        `;
    }
}

async function init() {
    try {
        const [stats, journals] = await Promise.all([fetchStats(), fetchJournals()]);

        renderStats(stats);
        renderJournals(journals);
        renderYearFilters();

        await loadPapers();
    } catch (e) {
        console.error("初始化失败:", e);
        document.getElementById("paper-list-container").innerHTML = `
            <div class="empty-state">
                <h3>初始化失败</h3>
                <p>请确保后端服务已启动</p>
                <p style="font-size: 0.8rem; margin-top: 0.5rem; opacity: 0.7;">${e.message}</p>
            </div>
        `;
    }
}

// ==================== 事件绑定 ====================

document.addEventListener("DOMContentLoaded", () => {
    let searchTimer;
    const searchInput = document.getElementById("search-input");
    searchInput.addEventListener("input", () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => {
            state.filters.q = searchInput.value.trim();
            state.currentPage = 1;
            loadPapers();
        }, 400);
    });

    document.getElementById("journal-filter").addEventListener("change", (e) => {
        state.filters.journal = e.target.value;
        state.currentPage = 1;
        loadPapers();
    });

    document.getElementById("oa-filter").addEventListener("change", (e) => {
        state.filters.oa = e.target.checked;
        state.currentPage = 1;
        loadPapers();
    });

    document.getElementById("sort-select").addEventListener("change", (e) => {
        state.filters.sort = e.target.value;
        state.currentPage = 1;
        loadPapers();
    });

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") closeModal();
    });

    init();
});
