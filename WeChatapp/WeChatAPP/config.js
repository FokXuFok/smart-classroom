/**
 * 全局配置
 * API_BASE: 后端服务地址（自动判断模拟器/真机）
 *
 * 模拟器（微信开发者工具）：用 127.0.0.1，本机直连
 * 真机（手机扫码预览）：用电脑 WLAN IP，手机和电脑需在同一热点
 *
 * 真机调试前提：
 *   1) 手机和电脑在同一 WiFi/热点局域网
 *   2) 后端绑定 0.0.0.0（main.py 中 host 改为 "0.0.0.0"）
 *   3) 微信开发者工具 → 详情 → 本地设置 → 勾选"不校验合法域名"
 *
 * 正式发布：HTTPS 域名，并在微信公众平台配置 request 合法域名
 */

// 电脑 WLAN IP（真机预览用，连手机热点时改成对应 IP）
const LAN_IP = '10.140.234.105'
const PORT = 8080

// 自动判断运行环境：模拟器用 127.0.0.1，真机用 WLAN IP
let _API_BASE
try {
  const sys = wx.getSystemInfoSync()
  _API_BASE = sys.platform === 'devtools'
    ? 'http://127.0.0.1:' + PORT
    : 'http://' + LAN_IP + ':' + PORT
  console.log('[config] platform=' + sys.platform + ', API_BASE=' + _API_BASE)
} catch (e) {
  _API_BASE = 'http://127.0.0.1:' + PORT
}

const config = {
  API_BASE: _API_BASE,
  // 演示签到默认坐标（教师发起签到时使用的坐标，用于演示模式签到回退）
  DEMO_LAT: 25.272,
  DEMO_LNG: 110.331,
  // 签到状态中文映射
  ATT_STATUS_CN: { 0: '缺勤', 1: '正常', 2: '迟到', 3: '早退', 4: '请假' },
  // 提交状态中文映射
  SUBMIT_STATUS_CN: { 0: '待评测', 1: '已评测', 2: '已批改' },
}

module.exports = config
