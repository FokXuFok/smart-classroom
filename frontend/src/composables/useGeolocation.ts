import { ref } from 'vue';

// 定位错误码 → 中文提示
const GEO_ERROR_MSG: Record<number, string> = {
  1: '定位权限被拒绝,请在浏览器地址栏授权位置访问',
  2: '定位失败(信号不可用),请检查网络或无线开关',
  3: '定位超时,请检查定位权限后重试',
};

// 精度阈值：accuracy 大于该值认为是 IP 定位等低精度源，不可作为围栏基准
export const ACCURACY_LIMIT_M = 300;

export interface GeoPosition {
  lat: number;
  lng: number;
  accuracy: number;
}

/**
 * 高精度定位采集(增强版)
 * - 安全上下文检测:非 HTTPS/localhost 时明确提示,不无限等待
 * - 兜底超时:防止 getCurrentPosition 回调永不触发导致 UI 一直转圈
 * - 明确错误信息:权限拒绝/信号/超时分别提示
 * - 返回 accuracy 精度,供调用方判断是否可靠(IP 定位可达公里级误差)
 */
export function useGeolocation() {
  const loading = ref(false);
  const error = ref('');

  /** 浏览器当前定位权限状态:prompt/denied/unknown,失败时用于提示 */
  function permissionState(): string {
    try {
      // @ts-ignore 旧版浏览器可能不支持 navigator.permissions
      if (navigator.permissions?.query) {
        // query 是异步的,这里只返回是否可测,真正状态由 getCurrentPosition 决定
        return 'supported';
      }
    } catch {
      /* ignore */
    }
    return 'unsupported';
  }

  async function getPosition(): Promise<GeoPosition | null> {
    // 1. 浏览器不支持
    if (!('geolocation' in navigator)) {
      error.value = '浏览器不支持定位 API';
      return null;
    }
    // 2. 非安全上下文(非 HTTPS 且非 localhost)时浏览器直接禁止定位
    if (typeof window !== 'undefined' && !window.isSecureContext) {
      error.value =
        '当前页面非安全上下文(需 HTTPS 或 localhost),浏览器禁止定位。请用 http://127.0.0.1:5173 访问';
      return null;
    }

    loading.value = true;
    error.value = '';

    const waitTimeout = 8000; // getCurrentPosition 自身超时
    const hardTimeout = waitTimeout + 1500; // 兜底超时,防止回调永不触发

    return new Promise((resolve) => {
      let settled = false;
      const finish = (result: GeoPosition | null, msg = '') => {
        if (settled) return;
        settled = true;
        clearTimeout(hardTimer);
        loading.value = false;
        error.value = msg;
        resolve(result);
      };

      let hardTimer: ReturnType<typeof setTimeout>;
      // 兜底:到硬超时时间强制结束(某些浏览器在权限弹窗无响应时会永不回调)
      hardTimer = setTimeout(() => {
        finish(null, '定位超时,请检查浏览器位置权限并重试');
      }, hardTimeout);

      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const lat = pos.coords.latitude;
          const lng = pos.coords.longitude;
          const accuracy = pos.coords.accuracy ?? 0;
          finish({ lat, lng, accuracy });
        },
        (err) => {
          const msg =
            GEO_ERROR_MSG[err.code] ||
            err.message ||
            '定位失败,可使用默认坐标';
          finish(null, msg);
        },
        { enableHighAccuracy: true, timeout: waitTimeout, maximumAge: 0 },
      );
    });
  }

  return { loading, error, getPosition, permissionState, ACCURACY_LIMIT_M };
}