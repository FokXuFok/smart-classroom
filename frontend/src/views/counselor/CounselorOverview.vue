<template>
  <div class="counselor-overview" v-loading="loading">
    <div class="stat-cards">
      <StatCard title="管辖班级" :value="stat?.class_count ?? 0" color="blue" />
      <StatCard title="学生总数" :value="stat?.student_total ?? 0" color="green" />
      <StatCard
        title="平均出勤率"
        :value="fmtRate(stat?.avg_attendance_rate)"
        color="amber"
      />
      <StatCard title="预警学生" :value="stat?.warning_count ?? 0" color="red" />
    </div>
    <el-card>
      <template #header><span class="card-title">预警学生出勤率(升序)</span></template>
      <EChart v-if="warnings.length" :option="rateOption" height="320px" />
      <el-empty v-else description="暂无预警学生" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { counselorApi } from '@/api/counselor';
import StatCard from '@/components/StatCard.vue';
import EChart from '@/components/EChart.vue';
import type { CounselorStat, WarningRow } from '@/api/types';

const loading = ref(false);
const stat = ref<CounselorStat | null>(null);
const warnings = ref<WarningRow[]>([]);

const rateOption = computed(() => {
  const rows = warnings.value
    .filter((w) => w.attendance_rate != null)
    .sort((a, b) => (a.attendance_rate! - b.attendance_rate!));
  return {
    tooltip: {
      trigger: 'axis',
      formatter: (p: any) =>
        `${p[0].name}<br/>出勤率: ${(p[0].value * 100).toFixed(1)}%`,
    },
    grid: { left: 140, right: 60, top: 20, bottom: 30 },
    xAxis: {
      type: 'value',
      max: 1,
      axisLabel: { formatter: (v: number) => `${(v * 100).toFixed(0)}%` },
    },
    yAxis: {
      type: 'category',
      data: rows.map((r) => `${r.name}(${r.student_no})`),
      axisLabel: { fontSize: 11 },
    },
    series: [
      {
        type: 'bar',
        data: rows.map((r) => r.attendance_rate),
        itemStyle: {
          color: (p: any) => (p.value < 0.8 ? '#dc2626' : '#f59e0b'),
        },
        label: {
          show: true,
          formatter: (p: any) => `${(p.value * 100).toFixed(0)}%`,
          position: 'right',
        },
      },
    ],
  };
});

function fmtRate(r: number | null | undefined): string {
  return r != null ? (r * 100).toFixed(1) + '%' : '-';
}

async function load() {
  loading.value = true;
  try {
    const [s, w] = await Promise.all([
      counselorApi.stat(),
      counselorApi.warnings(),
    ]);
    stat.value = s;
    warnings.value = w;
  } catch {
    /* ignore */
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<style scoped lang="scss">
.counselor-overview {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.stat-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.card-title {
  font-weight: 600;
}
</style>
