// ECharts 按需引入 + 通用 composable(自动 init/resize/dispose)
import * as echarts from 'echarts/core';
import { BarChart, PieChart, LineChart } from 'echarts/charts';
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import { onMounted, onUnmounted, watch, type Ref } from 'vue';

echarts.use([
  BarChart,
  PieChart,
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  CanvasRenderer,
]);

export function useECharts(elRef: Ref<HTMLElement | null>, option: Ref<any>) {
  let chart: echarts.ECharts | null = null;
  const resize = () => chart?.resize();

  onMounted(() => {
    if (!elRef.value) return;
    chart = echarts.init(elRef.value);
    chart.setOption(option.value || {});
    window.addEventListener('resize', resize);
  });

  watch(
    option,
    (v) => chart?.setOption(v || {}, true),
    { deep: true },
  );

  onUnmounted(() => {
    window.removeEventListener('resize', resize);
    chart?.dispose();
    chart = null;
  });

  return { resize };
}
