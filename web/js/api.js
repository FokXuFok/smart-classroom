/* ============================================================
 * api.js — 统一请求封装（多角色 Cookie 认证版）
 * 每个角色独立 httpOnly cookie（sc_token_student/teacher/...），
 * 同一浏览器可同时登录多个角色，各标签互不影响。
 * api.setRole(role) 声明当前页面角色 → 请求自动带 X-Role 头，
 * 后端据此从对应角色 cookie 解析身份。
 * 401 → 跳转登录页
 * ============================================================ */
(function (global) {
  "use strict";

  var API_BASE =
    location.protocol === "http:" || location.protocol === "https:"
      ? location.origin
      : "http://127.0.0.1:8000";

  var _role = null;   // 当前页面角色（student/teacher/counselor/admin）

  /** 声明当前页面角色，此后所有请求携带 X-Role 头 */
  function setRole(role) { _role = role; }

  /**
   * request(path, {method, body, silent})
   * 成功 → resolve(data)；失败 → reject({code, message})
   * code === 401 → 跳转登录页（silent 时不跳，供登录页自用）
   */
  function request(path, opts) {
    opts = opts || {};
    var method = (opts.method || "GET").toUpperCase();
    var headers = {};
    if (opts.body !== undefined) headers["Content-Type"] = "application/json";
    if (_role) headers["X-Role"] = _role;

    return fetch(API_BASE + path, {
      method: method,
      headers: headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      credentials: "same-origin",
    })
      .then(function (res) {
        if (!res.ok) {
          if (res.status === 401 && !opts.silent) {
            location.href = "index.html";
            return new Promise(function () {});
          }
          throw { code: res.status, message: "服务异常（HTTP " + res.status + "）" };
        }
        return res.json().catch(function () {
          throw { code: -2, message: "响应格式错误" };
        });
      })
      .then(function (json) {
        if (json.code === 401 && !opts.silent) {
          location.href = "index.html";
          return new Promise(function () {});
        }
        if (json.code !== 0) {
          throw { code: json.code, message: json.message || "请求失败" };
        }
        return json.data;
      })
      .catch(function (err) {
        if (err && typeof err.code === "number") throw err;
        throw { code: -1, message: "无法连接服务器，请确认后端已启动（" + API_BASE + "）" };
      });
  }

  function get(path, opts) {
    return request(path, Object.assign({ method: "GET" }, opts));
  }

  function post(path, body, opts) {
    return request(path, Object.assign({ method: "POST", body: body || {} }, opts));
  }

  global.API_BASE = API_BASE;
  global.api = { request: request, get: get, post: post, setRole: setRole };
})(window);
