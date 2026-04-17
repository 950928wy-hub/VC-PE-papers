/**
 * VC/PE 论文推送站 — 前端逻辑
 * 处理论文列表渲染、搜索、筛选、分页、AI 翻译
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
        oa: false,
        sort: "newest",
    },
    stats: {
        total: 0,
        journalCount: 0,
        oaCount: 0,
    },
    translatedCache: {}, // 翻译缓存
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
        .slice(0, 8);

    let html = '<span class="year-pill active" data-year="">全部</span>';
    years.forEach((y) => {
        html += `<span class="year-pill" data-year="${y}">${y}</span>`;
    });

    container.innerHTML = html;

    // 重新绑定事件
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
        "风险投资": {bg: "var(--tag-vc)", color: "var(--tag-vc-text)"},
        "私募股权": {bg: "var(--tag-pe)", color: "var(--tag-pe-text)"},
        "LP": {bg: "var(--tag-lp)", color: "var(--tag-lp-text)"},
        "GP": {bg: "var(--tag-gp)", color: "var(--tag-gp-text)"},
        "退出策略": {bg: "var(--tag-exit)", color: "var(--tag-exit-text)"},
        "创业": {bg: "var(--tag-startup)", color: "var(--tag-startup-text)"},
        "杠杆收购": {bg: "var(--tag-vc)", color: "var(--tag-vc-text)"},
        "天使投资": {bg: "var(--tag-startup)", color: "var(--tag-startup-text)"},
        "融资": {bg: "var(--tag-pe)", color: "var(--tag-pe-text)"},
        "估值": {bg: "var(--tag-lp)", color: "var(--tag-lp-text)"},
        "公司治理": {bg: "var(--tag-gp)", color: "var(--tag-gp-text)"},
        "业绩回报": {bg: "var(--tag-lp)", color: "var(--tag-lp-text)"},
        "风险管理": {bg: "var(--tag-other)", color: "var(--tag-other-text)"},
        "中国": {bg: "#fff3e0", color: "#bf360c"},
        "美国": {bg: "#e3f2fd", color: "#0d47a1"},
        "欧洲": {bg: "#f3e5f5", color: "#4a148c"},
    };
    const style = map[tag] || {bg: "var(--tag-other)", color: "var(--tag-other-text)"};
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
                <h3>暂无论文</h3>
                <p>请先运行抓取脚本获取数据，或调整筛选条件</p>
            </div>
        `;
        return;
    }

    container.innerHTML = papers.map((paper, idx) => {
        const tags = paper.auto_tags || [];
        const tagHtml = tags.map((t) => `<span class="tag" style="${getTagStyle(t)}">${t}</span>`).join("");
        const keywords = (paper.keywords || []).slice(0, 6);
        const kwHtml = keywords.map((k) => `<span class="paper-keyword">${k}</span>`).join("");
        const authors = paper.authors ? paper.authors.slice(0, 5).join(", ") : "未知作者";
        const oaBadge = paper.is_oa
            ? '<span class="paper-oa-badge"><svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>开放获取</span>'
            : "";

        return `
            <div class="paper-card" data-idx="${idx}">
                <div class="paper-header">
                    <div class="paper-title" onclick="openModal(${idx})">${paper.title || "无标题"}</div>
                    ${oaBadge}
                </div>
                <div class="paper-meta">
                    <span class="paper-meta-item">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
                        ${authors}${paper.authors && paper.authors.length > 5 ? "..." : ""}
                    </span>
                    <span class="paper-meta-item">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/></svg>
                        ${paper.journal || "未知期刊"}
                    </span>
                    <span class="paper-meta-item">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
                        ${paper.year || "未知年份"}
                    </span>
                    ${paper.doi ? `<span class="paper-meta-item">DOI: ${paper.doi}</span>` : ""}
                </div>
                <div class="paper-authors">${authors}</div>
                <div class="paper-abstract" id="abstract-${idx}">${paper.abstract || "暂无摘要"}</div>
                <button class="translate-btn" onclick="handleTranslate(this, '${idx}')" style="display: ${paper.abstract ? 'flex' : 'none'}">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 8l6 6M4 14l6-6 2-3M2 5h12M7 2v3M22 22l-5-10-5 10M14 18h6"/></svg>
                    翻译摘要
                </button>
                ${tags.length > 0 ? `<div class="paper-tags">${tagHtml}</div>` : ""}
                ${kwHtml ? `<div class="paper-keywords">${kwHtml}</div>` : ""}
                <div class="paper-actions">
                    <a href="${paper.url || '#'}" target="_blank" class="btn btn-primary">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15,3 21,3 21,9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                        ScienceDirect
                    </a>
                    ${paper.is_oa ? `
                    <a href="https://doi.org/${paper.doi}" target="_blank" class="btn btn-accent">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7,10 12,15 17,10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                        免费下载
                    </a>
                    ` : `
                    <button class="btn btn-secondary" onclick="showOaHint()">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                        全文需订阅
                    </button>
                    `}
                </div>
            </div>
        `;
    }).join("");

    // 存储当前页论文数据
    state.currentPapers = papers;
}

function renderPagination(page, totalPages) {
    const container = document.getElementById("pagination");
    if (totalPages <= 1) {
        container.innerHTML = "";
        return;
    }

    let html = "";

    // 上一页
    html += `<a class="page-btn ${page === 1 ? "disabled" : ""}" onclick="${page !== 1 ? `gotoPage(${page - 1})` : ""}">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15,18 9,12 15,6"/></svg>
    </a>`;

    // 页码
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

    // 下一页
    html += `<a class="page-btn ${page === totalPages ? "disabled" : ""}" onclick="${page !== totalPages ? `gotoPage(${page + 1})` : ""}">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9,18 15,12 9,6"/></svg>
    </a>`;

    container.innerHTML = html;
}

// ==================== 交互处理 ====================

async function handleTranslate(btn, idx) {
    const paper = state.currentPapers[idx];
    if (!paper || !paper.abstract) return;

    const card = btn.closest(".paper-card");
    const abstractEl = card.querySelector(".paper-abstract");
    const zhEl = card.querySelector(".paper-abstract-zh");

    // 如果已翻译，显示/隐藏切换
    if (zhEl) {
        const isVisible = zhEl.style.display !== "none";
        zhEl.style.display = isVisible ? "none" : "block";
        btn.innerHTML = isVisible
            ? `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 8l6 6M4 14l6-6 2-3M2 5h12M7 2v3M22 22l-5-10-5 10M14 18h6"/></svg> 翻译摘要`
            : `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 8l6 6M4 14l6-6 2-3M2 5h12M7 2v3M22 22l-5-10-5 10M14 18h6"/></svg> 隐藏翻译`;
        return;
    }

    // 翻译中
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation: spin 1s linear infinite"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg> 翻译中...`;

    const translated = await translateText(paper.abstract);

    // 插入中文摘要
    const zhDiv = document.createElement("div");
    zhDiv.className = "paper-abstract-zh";
    zhDiv.textContent = translated;
    abstractEl.parentNode.insertBefore(zhDiv, abstractEl.nextSibling);

    btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 8l6 6M4 14l6-6 2-3M2 5h12M7 2v3M22 22l-5-10-5 10M14 18h6"/></svg> 隐藏翻译`;

    // 启用按钮（移除 spinner）
    const spinnerStyle = document.createElement("style");
    spinnerStyle.textContent = "@keyframes spin { to { transform: rotate(360deg); } }";
    document.head.appendChild(spinnerStyle);
    btn.disabled = false;
}

function openModal(idx) {
    const paper = state.currentPapers[idx];
    if (!paper) return;

    const tags = (paper.auto_tags || []).map(
        (t) => `<span class="tag" style="${getTagStyle(t)}; margin: 0.2rem; display: inline-block;">${t}</span>`
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
                        <strong style="font-size: 0.85rem; color: var(--text-secondary); display: block; margin-bottom: 0.5rem;">英文摘要</strong>
                        <div class="paper-abstract" style="font-size: 0.9rem;">${paper.abstract || "暂无摘要"}</div>
                    </div>
                    <div class="paper-actions" style="border-top: none; padding-top: 0;">
                        <a href="${paper.url || '#'}" target="_blank" class="btn btn-primary">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15,3 21,3 21,9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                            在 ScienceDirect 查看
                        </a>
                        ${paper.is_oa ? `
                        <a href="https://doi.org/${paper.doi}" target="_blank" class="btn btn-accent">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7,10 12,15 17,10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                            免费下载 PDF
                        </a>` : ""}
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
    alert("本文为付费订阅论文，全文需通过机构账号访问 ScienceDirect 获取。\n\n如需下载全文，请使用学校图书馆提供的远程访问服务。");
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
            <p>正在加载论文...</p>
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
        // 并行加载统计数据和期刊列表
        const [stats, journals] = await Promise.all([fetchStats(), fetchJournals()]);

        renderStats(stats);
        renderJournals(journals);
        renderYearFilters();

        // 加载第一页论文
        await loadPapers();
    } catch (e) {
        console.error("初始化失败:", e);
        document.getElementById("paper-list-container").innerHTML = `
            <div class="empty-state">
                <h3>初始化失败</h3>
                <p>请确保后端服务已启动 (python app.py)</p>
                <p style="font-size: 0.8rem; margin-top: 0.5rem; opacity: 0.7;">${e.message}</p>
            </div>
        `;
    }
}

// ==================== 事件绑定 ====================

document.addEventListener("DOMContentLoaded", () => {
    // 搜索
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

    // 期刊筛选
    document.getElementById("journal-filter").addEventListener("change", (e) => {
        state.filters.journal = e.target.value;
        state.currentPage = 1;
        loadPapers();
    });

    // OA 筛选
    document.getElementById("oa-filter").addEventListener("change", (e) => {
        state.filters.oa = e.target.checked;
        state.currentPage = 1;
        loadPapers();
    });

    // 排序
    document.getElementById("sort-select").addEventListener("change", (e) => {
        state.filters.sort = e.target.value;
        state.currentPage = 1;
        loadPapers();
    });

    // 键盘 ESC 关闭弹窗
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") closeModal();
    });

    // 启动
    init();
});
