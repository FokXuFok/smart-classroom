/* ============================================================
 * demo.js — 演示前端共享模块：顶栏渲染 + 登录守卫 + 小工具
 * 依赖：api.js（先于本文件引入）
 * ============================================================ */
(function (global) {
  "use strict";

  var ROLE_CN = { student: "学生", teacher: "教师", counselor: "辅导员", admin: "管理员" };

  function esc(s) {
    if (s === null || s === undefined) return "";
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  /** "YYYY-MM-DD HH:MM" 截断显示 */
  function shortTime(s) {
    if (!s) return "—";
    var m = String(s).match(/(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/);
    return m ? m[2] + "-" + m[3] + " " + m[4] + ":" + m[5] : String(s).slice(0, 16);
  }

  /**
   * initDemo(pageTitle, role) → Promise<user>
   * 验证登录（401 跳登录页），渲染顶部演示栏。
   * role：当前页面所属角色（student/teacher/...）。不同角色使用独立
   * httpOnly cookie，同一浏览器可同时登录学生端与教师端；本页面只认
   * 本角色 cookie，角色未登录则回登录页，不会"串号"到其他角色。
   */
  function initDemo(pageTitle, role) {
    api.setRole(role);
    return api.get("/api/auth/me", { silent: true }).then(function (user) {
      var bar = document.createElement("header");
      bar.style.cssText = "height:56px;background:var(--blue-grad);color:#fff;" +
        "display:flex;align-items:center;gap:12px;padding:0 24px;position:sticky;top:0;z-index:50;";
      bar.innerHTML =
        '<span style="width:30px;height:30px;border-radius:8px;background:rgba(255,255,255,.16);' +
        'display:flex;align-items:center;justify-content:center">' +
        '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#fff" stroke-width="1.6"><path d="M22 9L12 4 2 9l10 5 10-5z"/><path d="M6 11.5V16c0 1.2 2.7 3 6 3s6-1.8 6-3v-4.5"/></svg></span>' +
        '<strong style="font-size:16px">智课堂</strong>' +
        '<span style="font-size:12px;color:#9db4e8;letter-spacing:2px">SMART CLASSROOM</span>' +
        '<span style="margin-left:8px;padding:3px 10px;border-radius:20px;background:var(--amber);' +
        'color:#fff;font-size:12px;font-weight:600">' + esc(pageTitle) + '</span>' +
        '<span style="margin-left:auto;font-size:13px">' +
        esc((user.name || "") + " · " + (ROLE_CN[user.role] || user.role) + "（" + user.user_id + "）") + '</span>' +
        '<a href="api-test.html" style="color:#c9d6f5;font-size:12.5px;text-decoration:none;' +
        'padding:6px 12px;border:1px solid rgba(255,255,255,.35);border-radius:6px">API 测试台</a>' +
        '<button id="demo-logout" style="padding:6px 12px;border:1px solid rgba(255,255,255,.35);' +
        'background:transparent;color:#c9d6f5;border-radius:6px;font-size:12.5px;cursor:pointer">退出</button>';
      document.body.prepend(bar);
      document.getElementById("demo-logout").addEventListener("click", async function () {
        try { await api.post("/api/auth/logout", {}, { silent: true }); } catch (e) { /* 忽略 */ }
        location.href = "index.html";
      });
      return user;
    }).catch(function () {
      location.href = "index.html";
      return new Promise(function () {}); // 挂起，等待跳转
    });
  }

  /** 渲染环形出勤率（纯 CSS conic-gradient） */
  function ringHtml(rate) {
    var pct = Math.round((rate || 0) * 100);
    return '<div class="ring" style="--p:' + pct + '">' +
      '<span class="ring-text">' + pct + '%<small>出勤率</small></span></div>';
  }

  /* ---------- 签到提醒（学生端）：轮询进行中签到，新会话弹顶部横幅 ---------- */

  /**
   * checkinNotice(courseNameMap?)
   * courseNameMap: {course_id: course_name}，用于横幅显示课程名
   * 每 3 秒轮询 /api/student/checkin/active：
   *   - 出现新会话 → 顶部滑入醒目横幅（含实时倒计时）
   *   - 会话结束/过期 → 横幅自动消失
   * 已提示过的会话 id 记在 sessionStorage，同会话不重复弹
   */
  function checkinNotice(courseNameMap) {
    var names = courseNameMap || {};
    var POLL_MS = 3000;
    var alive = {};    // session id -> {el, timer}
    var noticed = {};  // 已提示过的 session id
    try {
      JSON.parse(sessionStorage.getItem("sc_noticed_ck") || "[]")
        .forEach(function (id) { noticed[id] = 1; });
    } catch (e) { /* 忽略 */ }

    function saveNoticed() {
      try {
        sessionStorage.setItem("sc_noticed_ck", JSON.stringify(Object.keys(noticed)));
      } catch (e) { /* 忽略 */ }
    }

    function fmt(sec) {
      var m = Math.floor(sec / 60), s = sec % 60;
      return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
    }

    function removeOne(id) {
      var a = alive[id];
      if (!a) return;
      clearInterval(a.timer);
      a.el.style.transform = "translate(-50%,-120%)";
      a.el.style.opacity = "0";
      setTimeout(function () { a.el.remove(); }, 350);
      delete alive[id];
    }

    function spawn(s) {
      var el = document.createElement("div");
      el.style.cssText =
        "position:fixed;top:66px;left:50%;transform:translate(-50%,-130%);" +
        "z-index:9999;display:flex;align-items:center;gap:12px;padding:12px 18px;" +
        "background:var(--blue-grad);color:#fff;border-radius:12px;" +
        "box-shadow:0 12px 36px rgba(22,51,122,.4);border-left:5px solid var(--amber);" +
        "font-size:13.5px;transition:transform .35s cubic-bezier(.2,.9,.3,1.2),opacity .3s;" +
        "max-width:92vw;";
      el.innerHTML =
        '<span style="font-size:20px">📢</span>' +
        '<div><div style="font-weight:700">老师发起了课堂签到 ·《' +
        esc(names[s.course_id] || s.course_id) + '》</div>' +
        '<div style="font-size:12px;color:#c9d6f5">请在 ' + esc(s.range_meters || 200) +
        ' 米范围内完成 人脸 + 定位 签到</div></div>' +
        '<span class="ck-count" style="font-weight:800;font-size:17px;font-variant-numeric:tabular-nums;' +
        'background:rgba(255,255,255,.15);padding:4px 10px;border-radius:8px">--:--</span>';
      var close = document.createElement("button");
      close.textContent = "知道了";
      close.style.cssText = "border:1px solid rgba(255,255,255,.4);background:transparent;" +
        "color:#fff;border-radius:6px;padding:5px 10px;cursor:pointer;font-size:12px;";
      close.addEventListener("click", function () { removeOne(s.id); });
      el.appendChild(close);
      document.body.appendChild(el);
      requestAnimationFrame(function () {
        el.style.transform = "translate(-50%,0)";
      });

      var left = s.remaining_seconds || (s.duration_minutes || 5) * 60;
      var countEl = el.querySelector(".ck-count");
      var timer = setInterval(function () {
        left--;
        if (left <= 0) { removeOne(s.id); return; }
        countEl.textContent = fmt(left);
        if (left <= 60) countEl.style.color = "#fbbf24";
      }, 1000);
      countEl.textContent = fmt(left);
      alive[s.id] = { el: el, timer: timer };
    }

    async function poll() {
      try {
        var list = await api.get("/api/student/checkin/active", { silent: true });
        var ids = {};
        (list || []).forEach(function (s) {
          ids[s.id] = 1;
          if (!noticed[s.id]) { noticed[s.id] = 1; spawn(s); }
        });
        saveNoticed();
        Object.keys(alive).forEach(function (id) {
          if (!ids[id]) removeOne(id); // 会话已结束
        });
      } catch (err) {
        if (err && err.code === 401) location.href = "index.html";
        /* 其余失败静默，下轮重试 */
      }
    }

    setInterval(poll, POLL_MS);
    poll();
  }

  /* ---------- 站内消息监听：轮询通知列表，新消息弹右上角横幅 ---------- */

  /**
   * notifWatcher()
   * 每 5 秒轮询 /api/notification/list：
   *   - 出现新通知 → 右上角滑入横幅（堆叠显示），8 秒后自动滑出
   * 已看过的通知 id 存 sessionStorage，同条不重复弹
   */
  function notifWatcher() {
    var POLL_MS = 5000;
    var seen = {};
    var stack = null;
    try {
      JSON.parse(sessionStorage.getItem("sc_seen_notif") || "[]")
        .forEach(function (id) { seen[id] = 1; });
    } catch (e) { /* 忽略 */ }

    function ensureStack() {
      if (stack && document.body.contains(stack)) return stack;
      stack = document.createElement("div");
      stack.style.cssText =
        "position:fixed;top:66px;right:18px;z-index:9998;display:flex;" +
        "flex-direction:column;gap:10px;max-width:340px;";
      document.body.appendChild(stack);
      return stack;
    }

    function spawn(n) {
      var el = document.createElement("div");
      el.style.cssText =
        "background:var(--white);border:1px solid var(--border);border-left:5px solid var(--amber);" +
        "border-radius:10px;padding:12px 14px;box-shadow:0 10px 32px rgba(22,51,122,.18);" +
        "font-size:13px;cursor:pointer;transform:translateX(120%);opacity:0;" +
        "transition:transform .35s cubic-bezier(.2,.9,.3,1.2),opacity .3s;";
      el.innerHTML =
        '<div style="font-weight:700;margin-bottom:3px">🔔 ' + esc(n.title || "新消息") + "</div>" +
        '<div style="color:var(--text-sub);font-size:12.5px;line-height:1.6">' + esc(n.content || "") + "</div>" +
        '<div style="font-size:11px;color:#94a3b8;margin-top:5px">' + shortTime(n.create_time) + "</div>";
      var kill = function () {
        clearInterval(t);
        el.style.transform = "translateX(120%)";
        el.style.opacity = "0";
        setTimeout(function () { el.remove(); }, 350);
      };
      el.addEventListener("click", kill);
      ensureStack().appendChild(el);
      requestAnimationFrame(function () {
        el.style.transform = "translateX(0)";
        el.style.opacity = "1";
      });
      var t = setTimeout(kill, 8000);
    }

    async function poll() {
      try {
        var d = await api.get("/api/notification/list?limit=10", { silent: true });
        (d.items || []).forEach(function (n) {
          if (!seen[n.id]) {
            seen[n.id] = 1;
            if (!n.is_read) spawn(n); // 未读的新消息才弹
          }
        });
        try {
          sessionStorage.setItem("sc_seen_notif",
            JSON.stringify(Object.keys(seen).slice(-100)));
        } catch (e) { /* 忽略 */ }
      } catch (err) {
        if (err && err.code === 401) location.href = "index.html";
        /* 其余失败静默，下轮重试 */
      }
    }

    setInterval(poll, POLL_MS);
    poll();
  }

  /* ---------- Tab 导航 ---------- */

  /**
   * buildTabs(container, tabs) — 渲染 Tab 导航并管理切换
   * tabs: [{key, label, render(el)}]，render 在首次切入时调用一次
   * 返回 {go(key)} 可编程切换
   */
  function buildTabs(container, tabs) {
    var bar = document.createElement("nav");
    bar.style.cssText =
      "display:flex;gap:6px;flex-wrap:wrap;background:var(--white);" +
      "border:1px solid var(--border);border-radius:12px;padding:6px;" +
      "margin-bottom:18px;position:sticky;top:64px;z-index:40;";
    var panes = {};
    tabs.forEach(function (t) {
      var btn = document.createElement("button");
      btn.textContent = t.label;
      btn.setAttribute("data-tab", t.key);
      btn.style.cssText =
        "padding:8px 18px;border:none;background:transparent;border-radius:8px;" +
        "font-size:14px;cursor:pointer;color:var(--text-sub);font-family:inherit;transition:all .15s;";
      btn.addEventListener("click", function () { go(t.key); });
      bar.appendChild(btn);
      var pane = document.createElement("section");
      pane.style.display = "none";
      pane.dataset.pane = t.key;
      container.appendChild(pane);
      panes[t.key] = { pane: pane, btn: btn, tab: t, rendered: false };
    });
    container.prepend(bar);

    function go(key) {
      Object.keys(panes).forEach(function (k) {
        var p = panes[k];
        var on = k === key;
        p.pane.style.display = on ? "" : "none";
        p.btn.style.background = on ? "var(--blue-grad)" : "transparent";
        p.btn.style.color = on ? "#fff" : "var(--text-sub)";
        p.btn.style.fontWeight = on ? "600" : "400";
        if (on && !p.rendered) { p.rendered = true; p.tab.render(p.pane); }
      });
    }
    go(tabs[0].key);
    return { go: go };
  }

  global.demo = {
    initDemo: initDemo, esc: esc, shortTime: shortTime,
    ringHtml: ringHtml, checkinNotice: checkinNotice,
    notifWatcher: notifWatcher, buildTabs: buildTabs, ROLE_CN: ROLE_CN
  };
})(window);
