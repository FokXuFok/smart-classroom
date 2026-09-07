// utils/server.js
// 服务器地址探测：换网/USB 共享后电脑 IP 会变，这里提供一键检测，
// 成功后把可用地址存入 storage（server_addr），下次启动自动使用，无需改代码
const config = require('../config')

/**
 * 探测单个地址是否可达（请求 /api/health，2.5 秒超时，不弹任何提示）
 * @param {string} base - 形如 http://192.168.1.5:8080
 * @returns {Promise<boolean>}
 */
function probe(base) {
  return new Promise((resolve) => {
    wx.request({
      url: base + '/api/health',
      method: 'GET',
      timeout: 2500,
      success: (res) => {
        const ok =
          res.statusCode === 200 &&
          res.data &&
          res.data.code === 0 &&
          res.data.data &&
          res.data.data.status === 'ok'
        resolve(!!ok)
      },
      fail: () => resolve(false),
    })
  })
}

/**
 * 自动检测可用后端地址
 * 依次尝试：已保存地址 → 当前地址 → 编译期默认地址 → 常见局域网地址
 * @param {object} opts
 * @param {Function} [opts.onProgress] - (index, total, url) 进度回调
 * @returns {Promise<string|null>} 成功返回 base，失败返回 null
 */
async function detectServer(opts) {
  opts = opts || {}
  const port = 8080

  // 候选列表（完整 URL，去重）
  const candidates = []
  const push = (u) => {
    if (u && candidates.indexOf(u) === -1) candidates.push(u)
  }
  config.candidateBases().forEach(push)

  // 常见局域网 IP（固定端口）
  ;[
    '192.168.1.1', '192.168.0.1', '192.168.31.1',
    '192.168.43.1',             // 安卓手机热点常见网关
    '10.90.193.20', '10.90.193.1',
    '172.20.10.1',              // iPhone 热点常见网关
  ].forEach((ip) => push('http://' + ip + ':' + port))

  for (let i = 0; i < candidates.length; i++) {
    const base = candidates[i]
    if (opts.onProgress) opts.onProgress(i + 1, candidates.length, base)
    if (await probe(base)) {
      config.setApiBase(base)
      return base
    }
  }
  return null
}

module.exports = { detectServer, probe }