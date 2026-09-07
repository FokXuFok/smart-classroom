<template>
  <el-dialog
    :model-value="modelValue"
    title="地图选点（点击地图选择签到中心）"
    width="720px"
    @close="onClose"
    @opened="onOpened"
    append-to-body
    destroy-on-close
  >
    <div class="map-toolbar">
      <span class="toolbar-hint">在当前地图上点击选择签到中心</span>
      <span v-if="picked" class="picked-info">
        已选：{{ picked.lat.toFixed(6) }}, {{ picked.lng.toFixed(6) }}
      </span>
    </div>
    <div ref="mapEl" id="map-picker" class="map-canvas"></div>
    <div class="map-tip">提示：鼠标左键拖动查看，滚轮缩放，在地图上点击选择中心点。</div>
    <template #footer>
      <el-button @click="onClose">取消</el-button>
      <el-button type="primary" :disabled="!picked" @click="onConfirm">确定（{{ picked ? picked.lat.toFixed(5) + ', ' + picked.lng.toFixed(5) : '' }}）</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

interface Pos {
  lat: number;
  lng: number;
}

const props = defineProps<{
  modelValue: boolean;
  /** 初始中心（默认坐标） */
  initLat?: number;
  initLng?: number;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void;
  (e: 'picked', pos: Pos): void;
}>();

const mapEl = ref<HTMLDivElement | null>(null);
const picked = ref<Pos | null>(null);

let map: L.Map | null = null;
let marker: L.Marker | null = null;

const DEFAULT_LAT = props.initLat ?? 25.272; // 桂林信息科技学院
const DEFAULT_LNG = props.initLng ?? 110.331;

async function initMap() {
  if (!mapEl.value || map) return;
  map = L.map(mapEl.value, {
    center: [DEFAULT_LAT, DEFAULT_LNG],
    zoom: 15,
  });
  // 瓦片源按序回退：高德(国内直连,free) → OSM(国际,需能访问墙外)
  const tileServers: Array<[string, Record<string, unknown>]> = [
    [
      'https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
      {
        maxZoom: 18,
        subdomains: ['1', '2', '3', '4'],
        attribution: '© 高德',
      },
    ],
    [
      'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      {
        maxZoom: 19,
        subdomains: 'abc',
        attribution: '© OpenStreetMap',
      },
    ],
  ];
  // 尝试加载第一个可用瓦片源
  for (const [url, opts] of tileServers) {
    let ok = false;
    const layer = L.tileLayer(url, opts);
    layer.on('error', () => {
      if (map && !ok) layer.remove();
    });
    layer.on('load', () => {
      ok = true;
    });
    layer.addTo(map);
    await new Promise((r) => setTimeout(r, 1500));
    const loaded = map.getContainer().querySelectorAll(
      'img.leaflet-tile-loaded:not(.leaflet-tile-error)',
    ).length;
    if (ok || loaded > 0) break;
    layer.remove();
  }
  // 点击选点
  map.on('click', (e: L.LeafletMouseEvent) => {
    setPicked(e.latlng.lat, e.latlng.lng);
  });
  // 默认打一个标记
  setPicked(DEFAULT_LAT, DEFAULT_LNG);
}

function setPicked(lat: number, lng: number) {
  picked.value = { lat, lng };
  if (map) {
    // 用 divIcon 代替默认图片图标（打包后 Leaflet 默认 icon 路径会 404，导致 onload 抛错）
    const icon = L.divIcon({
      className: 'map-picker-marker',
      html: '📍',
      iconSize: [28, 28],
      iconAnchor: [14, 26],
    });
    if (!marker) {
      marker = L.marker([lat, lng], { icon }).addTo(map!);
    } else {
      marker.setLatLng([lat, lng]);
    }
  }
}

function onConfirm() {
  if (!picked.value) return;
  emit('picked', picked.value);
  onClose();
}

function onClose() {
  emit('update:modelValue', false);
  // 关闭后销毁地图实例，避免重复初始化
  if (map) {
    map.remove();
    map = null;
    marker = null;
    picked.value = null;
  }
}

// 对话框打开动画完成后调用：此时 #map-picker 容器已存在
function onOpened() {
  nextTick(() => initMap());
}
</script>

<style scoped>
.map-canvas {
  width: 100%;
  height: 420px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  z-index: 0;
}
.map-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.picked-info {
  color: #4f46e5;
  font-family: monospace;
  font-size: 13px;
}
.toolbar-hint {
  color: #64748b;
  font-size: 13px;
}
.map-tip {
  margin-top: 8px;
  font-size: 12px;
  color: #64748b;
}
:deep(.map-picker-marker) {
  font-size: 28px;
  line-height: 28px;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
}
</style>