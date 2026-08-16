/* ============================================================
 * common.js — 公共工具 + 布局骨架 + hash 路由
 * 依赖：api.js（先于本文件引入）
 * 认证：token 在 httpOnly cookie 中，页面加载时调 /api/auth/me 验证
 * ============================================================ */
(function (global) {
  "use strict";

  /* ---------- 基础工具 ---------- */

  function escapeHtml(s) {
    if (s === null || s === undefined) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  /** 后端时间（ISO 或 "YYYY-MM-DD HH:MM:SS"）→ 可读文本 */
  function fmtTime(s, withDate) {
    if (!s) return "—";
    var m = String(s).match(/(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/);
    if (!m) return String(s).slice(0, 16);
    var md = m[2] + "-" + m[3];
    var hm = m[4] + ":" + m[5];
    return withDate ? m[1] + "-" + md + " " + hm : md + " " + hm;
  }
  function fmtDate(s) {
    if (!s) return "—";
    var m = String(s).match(/(\d{4})-(\d{2})-(\d{2})/);
    return m ? m[1] + "-" + m[2] + "-" + m[3] : String(s);
  }

  /** 数字滚动（统计卡 count-up） */
  function countUp(el, target, opts) {
    opts = opts || {};
    var dur = opts.duration || 700;
    var dec = opts.decimals || 0;
    var suffix = opts.suffix || "";
    var start = null;
    if (!window.requestAnimationFrame) { el.textContent = target.toFixed(dec) + suffix; return; }
    function frame(ts) {
      if (!start) start = ts;
      var p = Math.min(1, (ts - start) / dur);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = (target * eased).toFixed(dec) + suffix;
      if (p < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  /* ---------- toast ---------- */

  var TOAST_ICONS = {
    success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M20 6L9 17l-5-5"/></svg>',
    error: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M15 9l-6 6M9 9l6 6"/></svg>',
    info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M12 8h.01M12 11v5"/></svg>',
    warn: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 9v4M12 17h.01M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z"/></svg>'
  };

  function toast(msg, type) {
    type = type || "info";
    var wrap = document.querySelector(".toast-wrap");
    if (!wrap) {
      wrap = document.createElement("div");
      wrap.className = "toast-wrap";
      document.body.appendChild(wrap);
    }
    var t = document.createElement("div");
    t.className = "toast toast-" + type;
    t.innerHTML = (TOAST_ICONS[type] || TOAST_ICONS.info) + "<span>" + escapeHtml(msg) + "</span>";
    wrap.appendChild(t);
    setTimeout(function () {
      t.style.transition = "opacity .3s";
      t.style.opacity = "0";
      setTimeout(function () { t.remove(); }, 320);
    }, 2600);
  }

  /* ---------- 确认模态 ---------- */

  function confirmModal(title, text, okText, danger) {
    return new Promise(function (resolve) {
      var mask = document.createElement("div");
      mask.className = "modal-mask";
      mask.innerHTML =
        '<div class="modal" style="width:400px">' +
        '<div class="modal-head"><h3>' + escapeHtml(title) + '</h3></div>' +
        '<div class="modal-body" style="color:var(--text-sub)">' + escapeHtml(text) + "</div>" +
        '<div class="modal-foot">' +
        '<button class="btn btn-outline" data-act="no">取消</button>' +
        '<button class="btn ' + (danger ? "btn-danger" : "btn-primary") + '" data-act="yes">' +
        escapeHtml(okText || "确定") + "</button></div></div>";
      document.body.appendChild(mask);
      function close(val) { mask.remove(); resolve(val); }
      mask.addEventListener("click", function (e) {
        var act = e.target.getAttribute && e.target.getAttribute("data-act");
        if (act === "yes") close(true);
        else if (act === "no" || e.target === mask) close(false);
      });
    });
  }

  /* ---------- 内联图标（细线 stroke 1.5） ---------- */

  var ICONS = {
    logo: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 9L12 4 2 9l10 5 10-5z"/><path d="M6 11.5V16c0 1.2 2.7 3 6 3s6-1.8 6-3v-4.5"/><path d="M22 9v5"/></svg>',
    bell: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 01-3.4 0"/></svg>',
    logout: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><path d="M16 17l5-5-5-5M21 12H9"/></svg>',
    courses: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/></svg>',
    face: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7V5a2 2 0 012-2h2M17 3h2a2 2 0 012 2v2M21 17v2a2 2 0 01-2 2h-2M7 21H5a2 2 0 01-2-2v-2"/><circle cx="12" cy="11" r="3"/><path d="M8.5 17.5c.8-1.3 2-2 3.5-2s2.7.7 3.5 2"/></svg>',
    checkin: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M8.5 12.5l2.5 2.5 4.5-5"/></svg>',
    homework: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M16 18l6-6-6-6M8 6l-6 6 6 6"/></svg>',
    ai: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="8" width="16" height="12" rx="3"/><path d="M12 8V4M9 4h6"/><circle cx="9" cy="13" r="1" fill="currentColor"/><circle cx="15" cy="13" r="1" fill="currentColor"/><path d="M9.5 16.5h5"/></svg>',
    me: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-3.5 4.5-5 8-5s6.5 1.5 8 5"/></svg>',
    board: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/></svg>',
    interact: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>'
  };

  /* ---------- 布局骨架（侧栏 + 顶栏 + 通知铃铛） ---------- */

  var ROLE_CN = { student: "学生", teacher: "教师", counselor: "辅导员", admin: "管理员" };
  var NOTIF_TYPE_CN = {
    homework_graded: "作业批改", checkin_review: "签到复核",
    leave_review: "请假审批", system: "系统通知"
  };

  // 当前登录用户信息（由 initLayout 从 /api/auth/me 获取）
  var currentAuth = null;

  /**
   * initLayout(menus, activeKey?)
   * 异步：先调 /api/auth/me 验证登录 → 401 自动跳登录页（api.js 处理）
   * 验证通过后渲染布局，返回 Promise
   */
  function initLayout(menus, activeKey) {
    return api.get("/api/auth/me").then(function (user) {
      currentAuth = user;

      var navHtml = menus.map(function (m) {
        return '<button class="nav-item' + (m.key === activeKey ? " active" : "") + '" data-key="' + m.key + '">' +
          (ICONS[m.icon] || "") + "<span>" + escapeHtml(m.label) + "</span></button>";
      }).join("");

      var layout = document.createElement("div");
      layout.className = "layout";
      layout.innerHTML =
        '<aside class="sidebar">' +
        '<div class="sidebar-brand"><span class="logo">' + ICONS.logo + "</span>" +
        "<div><strong>智课堂</strong><small>SMARTCLASSROOM</small></div></div>" +
        '<nav class="sidebar-nav">' + navHtml + "</nav>" +
        '<div class="sidebar-foot">全流程智慧课堂系统</div>' +
        "</aside>" +
        '<div class="main">' +
        '<header class="topbar">' +
        "<h1 id=\"page-title\"></h1>" +
        '<div class="topbar-right">' +
        '<div class="bell-wrap">' +
        '<button class="bell-btn" id="bell-btn" title="通知">' + ICONS.bell +
        '<span class="bell-badge" id="bell-badge" style="display:none"></span></button>' +
        '<div class="bell-panel" id="bell-panel">' +
        '<div class="bell-panel-head"><span>通知中心</span><a id="bell-read-all">全部已读</a></div>' +
        '<div class="bell-list" id="bell-list"><div class="bell-empty">暂无通知</div></div>' +
        "</div></div>" +
        '<div class="user-chip">' +
        '<span class="avatar">' + escapeHtml((user.name || "?").charAt(0)) + "</span>" +
        '<span class="meta"><span class="name">' + escapeHtml(user.name || "") + "</span>" +
        '<span class="role">' + escapeHtml(ROLE_CN[user.role] || user.role || "") + " · " + escapeHtml(user.user_id || "") + "</span></span>" +
        '<button class="logout-btn" id="logout-btn" title="退出登录">' + ICONS.logout + "</button>" +
        "</div></div></header>" +
        '<main class="content" id="page-content"></main>' +
        "</div>";
      document.body.appendChild(layout);

      // 侧栏导航 → hash 路由
      layout.querySelectorAll(".nav-item").forEach(function (btn) {
        btn.addEventListener("click", function () {
          location.hash = "#/" + btn.getAttribute("data-key");
        });
      });

      // 退出登录
      document.getElementById("logout-btn").addEventListener("click", async function () {
        var yes = await confirmModal("退出登录", "确定要退出当前账号吗？", "退出", true);
        if (!yes) return;
        try { await api.post("/api/auth/logout"); } catch (e) { /* 忽略 */ }
        location.href = "index.html";
      });

      initBell();
    });
  }

  /* ---------- 通知铃铛 ---------- */

  function initBell() {
    var btn = document.getElementById("bell-btn");
    var panel = document.getElementById("bell-panel");
    var badge = document.getElementById("bell-badge");
    var listEl = document.getElementById("bell-list");

    document.addEventListener("click", function (e) {
      if (!panel.contains(e.target) && !btn.contains(e.target)) {
        panel.classList.remove("open");
      }
    });
    btn.addEventListener("click", function () {
      panel.classList.toggle("open");
      if (panel.classList.contains("open")) refresh(true);
    });
    document.getElementById("bell-read-all").addEventListener("click", async function () {
      try {
        await api.post("/api/notification/read-all");
        refresh(false);
        toast("已全部标记为已读", "success");
      } catch (err) { toast(err.message || "操作失败", "error"); }
    });

    async function refresh(showUnreadInList) {
      var data;
      try { data = await api.get("/api/notification/list?limit=20"); }
      catch (err) { return; /* 静默：铃铛失败不打扰 */ }
      if (!data) return;
      if (data.unread_count > 0) {
        badge.textContent = data.unread_count > 99 ? "99+" : data.unread_count;
        badge.style.display = "";
      } else {
        badge.style.display = "none";
      }
      var items = data.items || [];
      if (!items.length) {
        listEl.innerHTML = '<div class="bell-empty">暂无通知</div>';
        return;
      }
      listEl.innerHTML = items.map(function (n) {
        return '<div class="bell-item' + (n.is_read ? "" : " unread") + '">' +
          '<div class="bell-title">' + escapeHtml(n.title) + "</div>" +
          '<div class="bell-content">' + escapeHtml(n.content || "") + "</div>" +
          '<div class="bell-time">[' + escapeHtml(NOTIF_TYPE_CN[n.notif_type] || n.notif_type || "通知") + "] " +
          fmtTime(n.create_time, true) + "</div></div>";
      }).join("");
    }
    refresh(); // 初始加载未读数
  }

  /* ---------- 极简 markdown → html（标题/粗体/行内码/列表/表格） ---------- */

  function mdToHtml(md) {
    var lines = escapeHtml(md || "").split(/\r?\n/);
    var out = [], para = [], list = [], table = [];
    function inline(s) {
      return s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/`([^`]+)`/g, "<code>$1</code>");
    }
    function fPara() { if (para.length) { out.push("<p>" + para.map(inline).join("<br>") + "</p>"); para = []; } }
    function fList() { if (list.length) { out.push("<ul>" + list.map(function (i) { return "<li>" + inline(i) + "</li>"; }).join("") + "</ul>"); list = []; } }
    function fTable() {
      if (!table.length) return;
      var rows = table.filter(function (r) { return !r.every(function (c) { return /^:?-{2,}:?$/.test(c); }); });
      if (rows.length) {
        var t = "<table><thead><tr>" + rows[0].map(function (c) { return "<th>" + inline(c) + "</th>"; }).join("") + "</tr></thead><tbody>";
        rows.slice(1).forEach(function (r) { t += "<tr>" + r.map(function (c) { return "<td>" + inline(c) + "</td>"; }).join("") + "</tr>"; });
        out.push(t + "</tbody></table>");
      }
      table = [];
    }
    lines.forEach(function (raw) {
      var line = raw.trim();
      if (/^\|.*\|$/.test(line)) { fPara(); fList(); table.push(line.slice(1, -1).split("|").map(function (c) { return c.trim(); })); return; }
      fTable();
      if (!line) { fPara(); fList(); return; }
      var h = line.match(/^#{1,6}\s+(.*)/);
      if (h) { fPara(); fList(); out.push("<h3>" + inline(h[1]) + "</h3>"); return; }
      if (/^[-*]\s+/.test(line) || /^\d+\.\s+/.test(line)) { fPara(); list.push(line.replace(/^([-*]|\d+\.)\s+/, "")); return; }
      fList();
      para.push(line);
    });
    fPara(); fList(); fTable();
    return out.join("");
  }

  /* ---------- hash 路由 ---------- */

  /**
   * registerRoutes(routes)
   * routes: {key: {title, render(container)}}
   * hash 形如 #/courses；路由切换时更新侧栏高亮与顶栏标题
   */
  function registerRoutes(routes) {
    var keys = Object.keys(routes);
    var first = keys[0];

    function currentKey() {
      var h = (location.hash || "").replace(/^#\/?/, "").split("?")[0];
      return routes[h] ? h : first;
    }

    function apply() {
      var key = currentKey();
      var route = routes[key];
      document.querySelectorAll(".nav-item").forEach(function (b) {
        b.classList.toggle("active", b.getAttribute("data-key") === key);
      });
      var titleEl = document.getElementById("page-title");
      if (titleEl) titleEl.textContent = route.title || "";
      var content = document.getElementById("page-content");
      if (!content) return;
      content.innerHTML = "";
      content.classList.remove("page-enter");
      void content.offsetWidth; // 重触发动画
      content.classList.add("page-enter");
      try {
        route.render(content);
      } catch (err) {
        console.error(err);
        content.innerHTML = '<div class="empty">页面渲染出错：' + escapeHtml(err.message || err) + "</div>";
      }
    }

    window.addEventListener("hashchange", apply);
    apply();
  }

  /* ---------- 导出 ---------- */
  global.common = {
    escapeHtml: escapeHtml,
    fmtTime: fmtTime,
    fmtDate: fmtDate,
    countUp: countUp,
    toast: toast,
    confirmModal: confirmModal,
    initLayout: initLayout,
    registerRoutes: registerRoutes,
    mdToHtml: mdToHtml,
    ICONS: ICONS,
    ROLE_CN: ROLE_CN,
    getAuth: function () { return currentAuth; }
  };
})(window);
