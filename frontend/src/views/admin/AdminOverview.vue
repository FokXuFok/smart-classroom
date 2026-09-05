<template>
  <div class="admin-overview" v-loading="loading">
    <div class="stat-grid">
      <StatCard title="学生" :value="data?.student_count ?? 0" color="blue" />
      <StatCard title="教师" :value="data?.teacher_count ?? 0" color="green" />
      <StatCard title="辅导员" :value="data?.counselor_count ?? 0" color="amber" />
      <StatCard title="管理员" :value="data?.admin_count ?? 0" color="purple" />
      <StatCard title="课程" :value="data?.course_count ?? 0" color="blue" />
      <StatCard title="班级" :value="data?.class_count ?? 0" color="green" />
      <StatCard title="签到记录" :value="data?.attendance_count ?? 0" color="amber" />
      <StatCard title="作业提交" :value="data?.submission_count ?? 0" color="red" />
    </div>

    <el-card class="chart-card">
      <template #header><span class="card-title">近 7 日签到趋势</span></template>
      <EChart :option="trendOption" height="320px" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { adminApi } from '@/api/admin';
import StatCard from '@/components/StatCard.vue';
import EChart from '@/components/EChart.vue';
import type { AdminOverview } from '@/api/types';

const loading = ref(true);
const data = ref<AdminOverview | null>(null);

const trendOption = computed(() => {
  const trend = data.value?.attendance_trend || [];
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 30, bottom: 40 },
    xAxis: {
      type: 'category',
      data: trend.map((t) => fmtShort(t.date)),
      axisLabel: { fontSize: 11 },
    },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        name: '签到人次',
        type: 'bar',
        data: trend.map((t) => t.count),
        itemStyle: { color: '#16337a' },
        barMaxWidth: 40,
      },
    ],
  };
});

function fmtShort(t: string): string {
  const d = new Date(t);
  if (isNaN(d.valueOf())) return t;
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

async function load() {
  loading.value = true;
  try {
    data.value = await adminApi.overview();
  } catch {
    /* http.ts 已 toast */
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<style scoped lang="scss">
.admin-overview {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.chart-card {
  width: 100%;
}
.card-title {
  font-weight: 600;
}
</style>
