/* ============================================================
 * api.js — 统一请求封装（httpOnly Cookie 认证版）
 * token 存放在 httpOnly cookie（统一命名 sc_token，登录自动覆盖）
 * 前端不存任何凭证，fetch 同源自动携带 cookie
 * 401 → 跳转登录页
 * ============================================================ */
(function (global) {
  "use strict";

  var API_BASE =
    location.protocol === "http:" || location.protocol === "https:"
      ? location.origin
      : "http://127.0.0.1:8000";

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
  global.api = { request: request, get: get, post: post };
})(window);
