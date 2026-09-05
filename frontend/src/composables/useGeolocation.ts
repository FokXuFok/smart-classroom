import { ref } from 'vue';

// 高精度定位采集:10 秒超时,失败回退默认坐标(教师可手动输入)
export function useGeolocation() {
  const loading = ref(false);
  const error = ref('');

  async function getPosition(): Promise<{ lat: number; lng: number } | null> {
    if (!navigator.geolocation) {
      error.value = '浏览器不支持定位';
      return null;
    }
    loading.value = true;
    error.value = '';
    return new Promise((resolve) => {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          loading.value = false;
          resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        },
        (err) => {
          loading.value = false;
          error.value = err.message || '定位失败,可使用默认坐标';
          resolve(null);
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 },
      );
    });
  }

  return { loading, error, getPosition };
}
