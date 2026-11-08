(function () {
  "use strict";

  const data = window.ZHIYA_DATA;
  if (!data || !Array.isArray(data.books)) {
    document.getElementById("app").innerHTML =
      '<div class="empty-state">没有读取到绘本数据。</div>';
    return;
  }

  const books = data.books;
  const navItems = [
    { key: "home", label: "首页", icon: "home" },
    { key: "library", label: "绘本馆", icon: "book" },
    { key: "moments", label: "亲子时光", icon: "heart" },
    { key: "growth", label: "成长记录", icon: "growth" },
  ];

  const state = {
    view: "home",
    activeTab: "home",
    selectedBookId: books.find((book) => book.title.includes("小狐狸"))?.id || books[0].id,
    pageIndex: 0,
    search: "",
    age: "all",
    childAge: "4-5",
    accountOpen: false,
    showPinyin: true,
    aiOpen: false,
    aiAnswer: false,
    speech: "idle",
    interactions: 0,
    visitedPages: new Set(),
    sessionStartedAt: null,
    lastReadBookId: null,
    records: readRecords(),
  };

  let toastTimer = null;
  let highlightTimer = null;
  let highlightFallbackIndex = 0;
  let activeUtterance = null;

  function icon(name) {
    const paths = {
      home: '<path d="M3 10.5 12 3l9 7.5M5.5 9.5V21h13V9.5M9.5 21v-6.5h5V21"/>',
      book: '<path d="M4 5.5c3-1 5.5-.5 8 1.5v13c-2.5-2-5-2.5-8-1.5zM20 5.5c-3-1-5.5-.5-8 1.5v13c2.5-2 5-2.5 8-1.5z"/>',
      heart:
        '<path d="M12 20c-3.5-3-8.5-6.3-8.5-11.2C3.5 5.9 6.8 4 9.2 6.2L12 9l2.8-2.8C17.2 4 20.5 5.9 20.5 8.8 20.5 13.7 15.5 17 12 20z"/>',
      growth:
        '<path d="M4 20v-8M10 20V8M16 20V4M22 20v-10M2 20h21"/>',
      search:
        '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.2 15.2 5.8 5.8"/>',
      play: '<path d="m9 6 9 6-9 6z"/>',
      pause: '<path d="M9 6v12M15 6v12"/>',
      stop: '<rect x="7" y="7" width="10" height="10" rx="1"/>',
      left: '<path d="M19 12H5m5-5-5 5 5 5"/>',
      right: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
      leaf:
        '<path d="M20.5 3.5C12.2 3.5 5.5 7.3 5.5 14.2c0 3.4 2.6 6.3 6 6.3 6.7 0 9-8.7 9-17zM3.5 21.5c3.7-6 8-10.3 14-13.7"/>',
      sparkle:
        '<path d="M12 2.5c.9 4.6 3.2 6.9 7.8 7.8-4.6.9-6.9 3.2-7.8 7.8-.9-4.6-3.2-6.9-7.8-7.8C8.8 9.4 11.1 7.1 12 2.5zM19 16.5c.4 1.7 1.3 2.6 3 3-1.7.4-2.6 1.3-3 3-.4-1.7-1.3-2.6-3-3 1.7-.4 2.6-1.3 3-3z"/>',
      close: '<path d="m5 5 14 14M19 5 5 19"/>',
      volume:
        '<path d="M4 10h4l5-4v12l-5-4H4zM16 9c1.5 1.5 1.5 4.5 0 6M18.5 6.5c3.3 3 3.3 8 0 11"/>',
      check: '<path d="m5 12 4 4L19 6"/>',
    };
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || ""}</svg>`;
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function readRecords() {
    try {
      return JSON.parse(localStorage.getItem("zhiya-reading-records") || "[]");
    } catch (_) {
      return [];
    }
  }

  function writeRecords(records) {
    state.records = records;
    try {
      localStorage.setItem("zhiya-reading-records", JSON.stringify(records));
    } catch (_) {
      // Local files can have restricted storage; the prototype still works in-session.
    }
  }

  function selectedBook() {
    return books.find((book) => book.id === state.selectedBookId) || books[0];
  }

  function currentPage() {
    return selectedBook().pages[state.pageIndex] || selectedBook().pages[0];
  }

  function showToast(message) {
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("show"), 2200);
  }

  function coverMarkup(book, alt = book.title, className = "") {
    if (!book.cover) {
      return `<div class="cover-placeholder ${className}">${escapeHtml(book.title)}</div>`;
    }
    return `<img class="${className}" src="${book.cover}" alt="${escapeHtml(alt)}" loading="lazy" />`;
  }

  function statusBar() {
    return `
      <div class="statusbar">
        <span>9:41</span>
        <div class="status-icons"><span></span><span></span><span></span><div class="battery"></div></div>
      </div>`;
  }

  function topbar() {
    return `
      <header class="topbar">
        <div class="brand-mark">${icon("leaf")}</div>
        <div class="brand-copy"><strong>知芽绘本</strong><small>亲子共读</small></div>
        <div class="topbar-actions">
          <button class="icon-btn" data-action="go-library" aria-label="搜索绘本">${icon("search")}</button>
          <button class="avatar" data-action="open-account" aria-label="账号与孩子档案">禾</button>
        </div>
      </header>`;
  }

  function navMarkup() {
    return navItems
      .map(
        (item) => `
        <button class="nav-item ${state.activeTab === item.key ? "active" : ""}" data-action="nav" data-tab="${item.key}">
          ${icon(item.icon)}<span>${item.label}</span>
        </button>`,
      )
      .join("");
  }

  function appFrame(content, showNav) {
    return `
      <div class="app">
        ${statusBar()}
        <main class="main">${content}</main>
        ${showNav ? `<nav class="bottom-nav">${navMarkup()}</nav>` : ""}
        ${state.accountOpen ? accountSheet() : ""}
      </div>`;
  }

  function accountSheet() {
    return `
      <div class="modal-backdrop" data-action="close-account">
        <section class="sheet" data-sheet>
          <div class="sheet-handle"></div>
          <div class="sheet-head">
            <div class="avatar" style="width:42px;height:42px">禾</div>
            <div><h2>石不转的账号</h2><p>个人账号与孩子阅读档案</p></div>
            <button class="close-btn" data-action="close-account" aria-label="关闭">${icon("close")}</button>
          </div>
          <div class="account-profile">
            <div class="info-card">
              <h3>当前孩子档案</h3>
              <p>芽芽 · ${escapeHtml(state.childAge)} 岁 · 已保存 ${state.records.length} 条阅读记录</p>
              <div class="segmented" aria-label="孩子年龄段">
                ${["3-4", "4-5", "5-6"]
                  .map(
                    (age) =>
                      `<button class="${state.childAge === age ? "active" : ""}" data-action="set-child-age" data-age="${age}">${age} 岁</button>`,
                  )
                  .join("")}
              </div>
            </div>
            <div class="info-card" style="background:var(--paper);border:1px solid var(--line)">
              <h3>朗读设置</h3>
              <p>优先使用系统中的自然中文语音。若声音仍然机械，请在 Windows“设置 → 时间和语言 → 语音”中安装中文自然语音。</p>
            </div>
            <div class="info-card">
              <h3>本机数据</h3>
              <p>阅读记录保存在当前浏览器本机，不会自动上传。原型暂不包含正式账号登录和云端同步。</p>
            </div>
          </div>
        </section>
      </div>`;
  }

  function homeView() {
    const featured = books.find((book) => book.title.includes("小狐狸")) || books[0];
    const selected = books.filter((book) => book.id !== featured.id).slice(0, 4);
    return `
      <section class="page">
        ${topbar()}
        <section class="hero">
          ${coverMarkup(featured, featured.title, "hero-image")}
          <div class="hero-content">
            <span class="eyebrow">今日共读 · ${escapeHtml(featured.ageLabel)}</span>
            <h1>和孩子一起<br />打开更大的世界</h1>
            <p>在绘本中，遇见有趣的故事。</p>
            <button class="primary hero-cta" data-action="open-book" data-id="${featured.id}">开始探索 ${icon("right")}</button>
          </div>
          <button class="featured-chip" data-action="open-book" data-id="${featured.id}">
            ${coverMarkup(featured, featured.title)}
            <span><strong>${escapeHtml(featured.title)}</strong><small>${escapeHtml(featured.ageLabel)} · ${featured.pages.length} 页</small></span>
          </button>
        </section>

        <section class="plan-card">
          <div class="plan-title">${icon("sparkle")} 今日阅读计划</div>
          <div>
            <div class="plan-number">15<small>分钟</small></div>
            <div class="plan-copy">和芽芽一起读一本关于勇气和陪伴的书。</div>
          </div>
          <div class="plan-side">
            <div class="progress"><span></span></div>
            <small style="font-size:9px;color:var(--muted)">连续共读 ${Math.max(1, state.records.length)} 天</small>
            <button class="primary" data-action="continue-reading">继续共读</button>
          </div>
        </section>

        <div class="section-head"><h2>为你精选</h2><span>${books.length} 本原创绘本</span></div>
        <div class="book-row">
          ${selected
            .map(
              (book) => `
              <button class="book-card" data-action="open-book" data-id="${book.id}">
                <span class="cover">${coverMarkup(book)}</span>
                <strong>${escapeHtml(book.title)}</strong>
                <small>${escapeHtml(book.ageLabel)} · ${book.pages.length} 页</small>
              </button>`,
            )
            .join("")}
        </div>
      </section>`;
  }

  function filteredBooks() {
    const query = state.search.trim().toLowerCase().replaceAll(" ", "");
    return books.filter((book) => {
      const ageMatch = state.age === "all" || book.age === state.age;
      const text = String(book.searchText || `${book.title} ${book.themes.join(" ")} ${book.bookNo}`)
        .toLowerCase()
        .replaceAll(" ", "");
      return ageMatch && (!query || text.includes(query));
    });
  }

  function libraryResultsMarkup() {
    const filtered = filteredBooks();
    return `
      <div class="filter-note">
        ${icon("sparkle")}
        <div><strong>当前筛选 ${filtered.length} 本</strong><p>年龄和标签来自项目仓库的绘本样例集，不是占位数据。</p></div>
      </div>
      <div class="library-grid">
        ${
          filtered.length
            ? filtered
                .map(
                  (book) => `
                  <button class="book-card" data-action="open-book" data-id="${book.id}">
                    <span class="cover">${coverMarkup(book)}</span>
                    <strong>${escapeHtml(book.title)}</strong>
                    <small>${escapeHtml(book.ageLabel)} · ${escapeHtml(book.themes.slice(0, 2).join(" / "))}</small>
                  </button>`,
                )
                .join("")
            : '<div class="empty-state">没有找到匹配的绘本。<br />支持中文书名、主题，也支持 xiaoxiong 这类拼音搜索。</div>'
        }
      </div>`;
  }

  function libraryView() {
    return `
      <section class="page">
        ${topbar()}
        <div class="page-title">
          <h1>绘本馆</h1>
          <p>仓库内 ${books.length} 本原创绘本，按年龄与主题查找。</p>
        </div>
        <label class="searchbar">
          ${icon("search")}
          <input id="library-search" value="${escapeHtml(state.search)}" placeholder="搜索绘本、主题或角色" />
        </label>
        <div class="segmented" aria-label="年龄筛选">
          ${[
            ["all", "全部"],
            ["3-4", "3–4 岁"],
            ["4-5", "4–5 岁"],
            ["5-6", "5–6 岁"],
          ]
            .map(
              ([value, label]) =>
                `<button class="${state.age === value ? "active" : ""}" data-action="set-age" data-age="${value}">${label}</button>`,
            )
            .join("")}
        </div>
        <div id="library-dynamic">${libraryResultsMarkup()}</div>
      </section>`;
  }

  function detailView() {
    const book = selectedBook();
    return `
      <section class="page">
        <div class="detail-header">
          <button class="icon-btn" data-action="back-home" aria-label="返回">${icon("left")}</button>
          <span class="pill solid">${escapeHtml(book.bookNo)}</span>
        </div>
        <div class="detail-cover">${coverMarkup(book)}</div>
        <div class="detail-title"><h1>${escapeHtml(book.title)}</h1></div>
        <div class="detail-meta">原创绘本 · ${book.pages.length} 页 · ${escapeHtml(book.difficulty)}</div>
        <div class="pill-row">
          <span class="pill solid">${escapeHtml(book.ageLabel)}</span>
          ${book.themes.map((theme) => `<span class="pill">${escapeHtml(theme)}</span>`).join("")}
        </div>
        <p class="detail-summary">${escapeHtml(book.summary)}</p>
        <div class="notice-card">
          ${icon("sparkle")}
          <div>
            <h3>知芽推荐</h3>
            <p>这篇故事适合亲子共读。阅读时会显示逐字拼音，也可以使用浏览器语音朗读。</p>
          </div>
        </div>
        <div class="bottom-actions">
          <button class="secondary" data-action="add-shelf">加入书架</button>
          <button class="primary" data-action="start-reading">开始共读 ${icon("right")}</button>
        </div>
      </section>`;
  }

  function rubyMarkup(page) {
    return page.ruby
      .map((item, index) => {
        const char = item.char === " " ? "&nbsp;" : escapeHtml(item.char);
        if (!item.pinyin) {
          return `<span class="char-plain" data-char-index="${index}">${char}</span>`;
        }
        return `<ruby class="char" data-char-index="${index}">${char}<rt>${escapeHtml(item.pinyin)}</rt></ruby>`;
      })
      .join("");
  }

  function readerView() {
    const book = selectedBook();
    const page = currentPage();
    const positions = ["50% 50%", "22% 48%", "78% 48%", "42% 62%", "62% 40%"];
    const position = positions[state.pageIndex % positions.length];
    return `
      <section class="page">
        <header class="reader-head">
          <button class="icon-btn" data-action="back-detail" aria-label="返回详情">${icon("left")}</button>
          <strong>${escapeHtml(book.title)}</strong>
          <span>${state.pageIndex + 1} / ${book.pages.length}</span>
        </header>
        <div class="reader-image">
          ${book.cover ? `<img src="${book.cover}" style="object-position:${position}" alt="${escapeHtml(book.title)}" />` : `<div class="cover-placeholder">${escapeHtml(book.title)}</div>`}
          <div class="scene-label">画面：${escapeHtml(page.scene || "绘本画面")}</div>
        </div>
        <div style="display:flex;justify-content:flex-end;margin-top:8px">
          <button class="pinyin-toggle" data-action="toggle-pinyin">${state.showPinyin ? "隐藏拼音" : "显示拼音"}</button>
        </div>
        <div class="reader-text ${state.showPinyin ? "" : "hide-pinyin"}" id="reader-text">${rubyMarkup(page)}</div>
        <div class="audio-card">
          <button class="round-btn" data-action="speak" aria-label="朗读当前页">${state.speech === "playing" ? icon("pause") : icon("play")}</button>
          <div class="audio-meta">
            <strong data-speech-label>${state.speech === "playing" ? "正在朗读" : state.speech === "paused" ? "朗读已暂停" : "听知芽读这一页"}</strong>
            <small>使用浏览器中文语音，无需外部音频资源</small>
            <div class="audio-progress"><span data-speech-progress></span></div>
          </div>
          <button class="icon-btn" data-action="stop-speech" aria-label="停止朗读">${icon("stop")}</button>
        </div>
        <div class="reader-controls">
          <button class="icon-btn" data-action="prev-page" ${state.pageIndex === 0 ? "disabled" : ""} aria-label="上一页">${icon("left")}</button>
          <button class="primary" data-action="next-page">${state.pageIndex === book.pages.length - 1 ? "完成阅读" : "下一页"} ${icon("right")}</button>
          <button class="icon-btn" data-action="next-page" ${state.pageIndex === book.pages.length - 1 ? "disabled" : ""} aria-label="下一页">${icon("right")}</button>
        </div>
        <button class="question-card" data-action="open-ai">
          ${icon("sparkle")}
          <span><strong>共读小问题 · ${escapeHtml(page.promptType || "理解")}</strong><p>${escapeHtml(page.prompt || "你从这一页看到了什么？")}</p></span>
          ${icon("right")}
        </button>
      </section>
      ${state.aiOpen ? aiSheet(page) : ""}`;
  }

  function aiSheet(page) {
    return `
      <div class="modal-backdrop" data-action="close-ai">
        <section class="sheet" data-sheet>
          <div class="sheet-handle"></div>
          <div class="sheet-head">
            <div class="brand-mark">${icon("leaf")}</div>
            <div><h2>知芽共读伙伴</h2><p>基于当前页生成提示</p></div>
            <button class="close-btn" data-action="close-ai" aria-label="关闭">${icon("close")}</button>
          </div>
          <span class="pill" style="margin-top:20px">第 ${page.page} 页 · ${escapeHtml(page.promptType || "共读问题")}</span>
          <h3>${escapeHtml(page.prompt || "你从这一页看到了什么？")}</h3>
          <p class="sheet-copy">没有标准答案，先听听孩子怎么说。这个原型会给出一个示范回答。</p>
          <div class="option-list">
            <button class="option-btn" data-action="ai-answer"><b>A</b><span>让孩子先自由回答</span>${icon("right")}</button>
            <button class="option-btn" data-action="ai-answer"><b>B</b><span>请知芽给一个提示</span>${icon("right")}</button>
          </div>
          ${
            state.aiAnswer
              ? `<div class="info-card"><h3>知芽的提示</h3><p>先观察画面里角色的表情和动作，再回到文字找线索。${escapeHtml(page.scene || "")}</p></div>`
              : ""
          }
        </section>
      </div>`;
  }

  function summaryView() {
    const book = selectedBook();
    const minutes = readingMinutes();
    const pagesRead = Math.max(1, state.visitedPages.size || book.pages.length);
    return `
      <section class="page">
        <div class="detail-header">
          <button class="icon-btn" data-action="back-home" aria-label="关闭">${icon("close")}</button>
          <span class="pill">完成阅读</span>
        </div>
        <section class="summary-hero">
          <small>今天，我们一起读完了</small>
          <h1>《${escapeHtml(book.title)}》</h1>
        </section>
        <div class="stats">
          <div class="stat"><strong>${minutes}</strong><small>分钟共读</small></div>
          <div class="stat"><strong>${pagesRead}</strong><small>页一起读完</small></div>
          <div class="stat"><strong>${state.interactions}</strong><small>次亲子互动</small></div>
        </div>
        <div class="info-card">
          <h3>知芽看到的小小闪光</h3>
          <p>孩子已经能关注角色的动作，并尝试用“因为……”表达自己的想法。下一轮可以继续问“你觉得它为什么这样做？”</p>
        </div>
        <div class="info-card" style="background:var(--paper);border:1px solid var(--line)">
          <h3>亲子延伸活动</h3>
          <p>读完后再一起看一遍封面，让孩子指出自己最喜欢的地方，并用自己的话复述一页故事。</p>
        </div>
        <div class="bottom-actions">
          <button class="secondary" data-action="back-home">回到首页</button>
          <button class="primary" data-action="save-record">记录到成长</button>
        </div>
      </section>`;
  }

  function growthView() {
    const totalMinutes = state.records.reduce((sum, record) => sum + record.minutes, 0);
    const bookCount = new Set(state.records.map((record) => record.bookId)).size;
    return `
      <section class="page">
        ${topbar()}
        <div class="page-title"><h1>成长记录</h1><p>每一次共读，都在悄悄发芽。</p></div>
        <section class="summary-hero" style="margin-top:18px">
          <small>累计共读</small>
          <h1>${totalMinutes || readingMinutes()} 分钟</h1>
        </section>
        <div class="stats">
          <div class="stat"><strong>${state.records.length}</strong><small>共读次数</small></div>
          <div class="stat"><strong>${bookCount}</strong><small>读过的书</small></div>
          <div class="stat"><strong>${Math.max(1, state.records.length)}</strong><small>连续天数</small></div>
        </div>
        <div class="section-head"><h2>最近读过</h2><span>${state.records.length ? "已保存到本机" : "完成阅读后会出现在这里"}</span></div>
        <div class="records">
          ${
            state.records.length
              ? state.records
                  .slice(0, 8)
                  .map((record) => {
                    const book = books.find((item) => item.id === record.bookId) || selectedBook();
                    return `<button class="record-row" data-action="open-book" data-id="${book.id}">
                      ${coverMarkup(book)}
                      <span><strong>${escapeHtml(book.title)}</strong><small>${new Date(record.at).toLocaleDateString("zh-CN")} · ${record.minutes} 分钟 · ${record.pages} 页</small></span>
                      ${icon("right")}
                    </button>`;
                  })
                  .join("")
              : '<div class="empty-state">还没有阅读记录。<br />先从首页开始一次共读吧。</div>'
          }
        </div>
      </section>`;
  }

  function momentsView() {
    return `
      <section class="page">
        ${topbar()}
        <div class="page-title"><h1>亲子时光</h1><p>把读过的故事，变成一起做过的事。</p></div>
        <section class="hero" style="min-height:230px;margin-top:18px">
          ${coverMarkup(books[0], books[0].title, "hero-image")}
          <div class="hero-content" style="min-height:230px;justify-content:flex-end">
            <span class="eyebrow">今日亲子灵感</span>
            <h1 style="font-size:24px;margin:10px 0 8px">做一把小狐狸的纸伞</h1>
            <p style="color:var(--paper);max-width:230px">用 15 分钟，把故事里最温暖的一幕带到生活里。</p>
            <button class="primary" data-action="activity-tip">查看做法 ${icon("right")}</button>
          </div>
        </section>
        <div class="section-head"><h2>把故事留下来</h2><span>亲子共读记录</span></div>
        <div class="moment-grid">
          <button class="moment-card" data-action="memory-tip">
            <span class="eyebrow">共读回忆</span>
            <h3>今天孩子说了什么？</h3>
            <p>完成一次阅读后，可以在成长记录里看到本次摘要。</p>
          </button>
          <button class="moment-card sage" data-action="studio-tip">
            <span class="eyebrow">原创绘本工坊</span>
            <h3>即将开放</h3>
            <p>后续会支持生成专属故事，当前版本先不伪装成可用功能。</p>
          </button>
        </div>
      </section>`;
  }

  function viewMarkup() {
    if (state.view === "home") return appFrame(homeView(), true);
    if (state.view === "library") return appFrame(libraryView(), true);
    if (state.view === "detail") return appFrame(detailView(), false);
    if (state.view === "reader") return appFrame(readerView(), false);
    if (state.view === "summary") return appFrame(summaryView(), false);
    if (state.view === "growth") return appFrame(growthView(), true);
    if (state.view === "moments") return appFrame(momentsView(), true);
    return appFrame(homeView(), true);
  }

  function render() {
    const app = document.getElementById("app");
    app.innerHTML = viewMarkup();
    if (state.view === "library" && document.activeElement?.id === "library-search") {
      const input = document.getElementById("library-search");
      input?.focus();
    }
  }

  function stopHighlight() {
    clearInterval(highlightTimer);
    highlightTimer = null;
    document.querySelectorAll(".spoken").forEach((node) => node.classList.remove("spoken"));
  }

  function highlightChar(index) {
    document.querySelectorAll(".spoken").forEach((node) => node.classList.remove("spoken"));
    const node = document.querySelector(`[data-char-index="${index}"]`);
    node?.classList.add("spoken");
    const progress = document.querySelector("[data-speech-progress]");
    const page = currentPage();
    if (progress) progress.style.width = `${Math.min(100, ((index + 1) / page.text.length) * 100)}%`;
  }

  function startFallbackHighlight(text) {
    clearInterval(highlightTimer);
    highlightFallbackIndex = 0;
    highlightTimer = setInterval(() => {
      highlightChar(highlightFallbackIndex);
      highlightFallbackIndex += 1;
      if (highlightFallbackIndex >= Array.from(text).length) clearInterval(highlightTimer);
    }, 260);
  }

  function updateSpeechUI() {
    const button = document.querySelector('[data-action="speak"]');
    const label = document.querySelector("[data-speech-label]");
    if (button) {
      button.innerHTML =
        state.speech === "playing" ? icon("pause") : icon("play");
      button.setAttribute(
        "aria-label",
        state.speech === "playing" ? "暂停朗读" : state.speech === "paused" ? "继续朗读" : "朗读当前页",
      );
    }
    if (label) {
      label.textContent =
        state.speech === "playing"
          ? "正在朗读"
          : state.speech === "paused"
            ? "朗读已暂停"
            : "听知芽读这一页";
    }
  }

  function stopSpeech(silent = false) {
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    activeUtterance = null;
    state.speech = "idle";
    stopHighlight();
    const progress = document.querySelector("[data-speech-progress]");
    if (progress) progress.style.width = "0";
    updateSpeechUI();
    if (!silent) showToast("已停止朗读");
  }

  async function bestChineseVoice() {
    if (!("speechSynthesis" in window)) return null;
    let voices = window.speechSynthesis.getVoices();
    if (!voices.length) {
      await new Promise((resolve) => {
        const timer = setTimeout(resolve, 500);
        window.speechSynthesis.onvoiceschanged = () => {
          clearTimeout(timer);
          resolve();
        };
      });
      voices = window.speechSynthesis.getVoices();
    }
    const chineseVoices = voices
      .filter((voice) => voice.lang.toLowerCase().startsWith("zh"));
    const score = (voice) => {
      const name = `${voice.name} ${voice.voiceURI}`.toLowerCase();
      let value = 0;
      if (name.includes("natural")) value += 100;
      if (name.includes("online")) value += 80;
      if (name.includes("xiaoxiao")) value += 70;
      if (name.includes("xiaoyi")) value += 60;
      if (name.includes("yunxi")) value += 55;
      if (name.includes("yunyang")) value += 50;
      if (name.includes("huihui")) value += 20;
      if (voice.lang.toLowerCase() === "zh-cn") value += 10;
      return value;
    };
    return chineseVoices.sort((a, b) => score(b) - score(a))[0] || null;
  }

  async function speakCurrentPage() {
    if (!("speechSynthesis" in window)) {
      showToast("当前浏览器不支持语音朗读，请使用 Edge 或 Chrome。");
      return;
    }
    if (state.speech === "playing") {
      window.speechSynthesis.pause();
      state.speech = "paused";
      stopHighlight();
      updateSpeechUI();
      return;
    }
    if (state.speech === "paused") {
      window.speechSynthesis.resume();
      state.speech = "playing";
      startFallbackHighlight(currentPage().text);
      updateSpeechUI();
      return;
    }

    window.speechSynthesis.cancel();
    const page = currentPage();
    const utterance = new SpeechSynthesisUtterance(page.text);
    utterance.lang = "zh-CN";
    utterance.rate = 0.9;
    utterance.pitch = 1.02;
    const voice = await bestChineseVoice();
    if (voice) utterance.voice = voice;
    utterance.onstart = () => {
      state.speech = "playing";
      updateSpeechUI();
      startFallbackHighlight(page.text);
    };
    utterance.onboundary = (event) => {
      if (Number.isFinite(event.charIndex)) highlightChar(event.charIndex);
    };
    utterance.onend = () => {
      state.speech = "idle";
      stopHighlight();
      updateSpeechUI();
      const progress = document.querySelector("[data-speech-progress]");
      if (progress) progress.style.width = "100%";
    };
    utterance.onerror = () => {
      state.speech = "idle";
      stopHighlight();
      updateSpeechUI();
      showToast("朗读启动失败，请检查系统中文语音。");
    };
    activeUtterance = utterance;
    window.speechSynthesis.speak(utterance);
  }

  function readingMinutes() {
    if (!state.sessionStartedAt) return 1;
    return Math.max(1, Math.round((Date.now() - state.sessionStartedAt) / 60000));
  }

  function startReading() {
    stopSpeech(true);
    state.view = "reader";
    state.pageIndex = 0;
    state.visitedPages = new Set([0]);
    state.sessionStartedAt = Date.now();
    state.interactions = 0;
    state.aiOpen = false;
    state.aiAnswer = false;
    render();
  }

  function nextPage() {
    const book = selectedBook();
    stopSpeech(true);
    if (state.pageIndex >= book.pages.length - 1) {
      state.view = "summary";
      render();
      return;
    }
    state.pageIndex += 1;
    state.visitedPages.add(state.pageIndex);
    render();
  }

  function previousPage() {
    if (state.pageIndex <= 0) return;
    stopSpeech(true);
    state.pageIndex -= 1;
    state.visitedPages.add(state.pageIndex);
    render();
  }

  function saveRecord() {
    const book = selectedBook();
    const record = {
      bookId: book.id,
      title: book.title,
      at: Date.now(),
      minutes: readingMinutes(),
      pages: Math.max(1, state.visitedPages.size),
    };
    const next = [record, ...state.records].slice(0, 40);
    writeRecords(next);
    showToast("已保存到成长记录");
    state.view = "growth";
    state.activeTab = "growth";
    render();
  }

  function handleAction(action, target) {
    if (action === "nav") {
      stopSpeech(true);
      state.view = target.dataset.tab;
      state.activeTab = target.dataset.tab;
      render();
      return;
    }
    if (action === "open-book") {
      stopSpeech(true);
      state.selectedBookId = Number(target.dataset.id);
      state.view = "detail";
      render();
      return;
    }
    if (action === "go-library") {
      state.view = "library";
      state.activeTab = "library";
      render();
      return;
    }
    if (action === "open-account") {
      state.accountOpen = true;
      render();
      return;
    }
    if (action === "close-account") {
      if (target.closest("[data-sheet]") && !target.closest(".close-btn")) return;
      state.accountOpen = false;
      render();
      return;
    }
    if (action === "set-child-age") {
      state.childAge = target.dataset.age;
      render();
      showToast(`孩子档案已切换为 ${state.childAge} 岁`);
      return;
    }
    if (action === "back-home") {
      state.view = "home";
      state.activeTab = "home";
      render();
      return;
    }
    if (action === "back-detail") {
      stopSpeech(true);
      state.view = "detail";
      render();
      return;
    }
    if (action === "continue-reading") {
      const book = books.find((item) => item.title.includes("小狐狸")) || books[0];
      state.selectedBookId = book.id;
      startReading();
      return;
    }
    if (action === "start-reading") {
      startReading();
      return;
    }
    if (action === "add-shelf") {
      showToast("已加入书架，书架页面将在下一轮接入。");
      return;
    }
    if (action === "set-age") {
      state.age = target.dataset.age;
      render();
      return;
    }
    if (action === "toggle-pinyin") {
      state.showPinyin = !state.showPinyin;
      document.getElementById("reader-text")?.classList.toggle("hide-pinyin");
      target.textContent = state.showPinyin ? "隐藏拼音" : "显示拼音";
      return;
    }
    if (action === "speak") {
      void speakCurrentPage();
      return;
    }
    if (action === "stop-speech") {
      stopSpeech();
      return;
    }
    if (action === "next-page" || action === "prev-page") {
      if (action === "next-page") nextPage();
      else previousPage();
      return;
    }
    if (action === "open-ai") {
      state.aiOpen = true;
      state.aiAnswer = false;
      render();
      return;
    }
    if (action === "close-ai") {
      if (target.closest("[data-sheet]") && !target.closest(".close-btn")) return;
      state.aiOpen = false;
      state.aiAnswer = false;
      render();
      return;
    }
    if (action === "ai-answer") {
      if (!state.aiAnswer) state.interactions += 1;
      state.aiAnswer = true;
      render();
      return;
    }
    if (action === "save-record") {
      saveRecord();
      return;
    }
    if (action === "activity-tip") {
      showToast("材料：彩纸、吸管、胶带。先把故事里的纸伞画出来，再一起剪贴。");
      return;
    }
    if (action === "memory-tip") {
      showToast("完成一次阅读后，本次共读摘要会进入成长记录。");
      return;
    }
    if (action === "studio-tip") {
      showToast("原创绘本工坊将在下一轮开放。");
    }
  }

  document.addEventListener("click", (event) => {
    const target = event.target.closest("[data-action]");
    if (!target) return;
    if (["close-ai", "close-account"].includes(target.dataset.action) && event.target !== target) {
      if (target.contains(event.target) && !event.target.closest(".close-btn")) return;
    }
    handleAction(target.dataset.action, target);
  });

  document.addEventListener("input", (event) => {
    if (event.target.id !== "library-search") return;
    state.search = event.target.value;
    const dynamic = document.getElementById("library-dynamic");
    if (dynamic) dynamic.innerHTML = libraryResultsMarkup();
  });

  render();
})();
