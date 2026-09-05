<template>
  <div class="admin-stats" v-loading="loading">
    <div class="stat-cards">
      <StatCard title="学生总数" :value="data?.student_count ?? 0" color="blue" />
      <StatCard title="教师总数" :value="data?.teacher_count ?? 0" color="green" />
      <StatCard title="课程总数" :value="data?.course_count ?? 0" color="amber" />
      <StatCard title="班级总数" :value="data?.class_count ?? 0" color="purple" />
    </div>

    <div class="stat-cards">
      <StatCard title="签到记录" :value="data?.attendance_count ?? 0" color="blue" />
      <StatCard title="作业总数" :value="data?.homework_count ?? 0" color="green" />
      <StatCard title="作业提交" :value="data?.submission_count ?? 0" color="amber" />
      <StatCard title="管理员数" :value="data?.admin_count ?? 0" color="purple" />
    </div>

    <div class="chart-row">
      <el-card class="chart-card">
        <template #header><span class="card-title">人员构成</span></template>
        <EChart :option="pieOption" height="320px" />
      </el-card>
      <el-card class="chart-card">
        <template #header><span class="card-title">近 7 日签到趋势</span></template>
        <EChart :option="trendOption" height="320px" />
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { adminApi } from '@/api/admin';
import StatCard from '@/components/StatCard.vue';
import EChart from '@/components/EChart.vue';
import type { AdminStat } from '@/api/types';

const loading = ref(true);
const data = ref<AdminStat | null>(null);

const pieOption = computed(() => {
  const d = data.value;
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c}人 ({d}%)' },
    legend: { bottom: 0, type: 'scroll' },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        data: [
          { name: '学生', value: d?.student_count ?? 0, itemStyle: { color: '#16337a' } },
          { name: '教师', value: d?.teacher_count ?? 0, itemStyle: { color: '#10b981' } },
          { name: '辅导员', value: d?.counselor_count ?? 0, itemStyle: { color: '#f59e0b' } },
          { name: '管理员', value: d?.admin_count ?? 0, itemStyle: { color: '#a855f7' } },
        ],
        label: { formatter: '{b}\n{c}人' },
      },
    ],
  };
});

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
    data.value = await adminApi.stat();
  } catch {
    /* http.ts 已 toast */
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<style scoped lang="scss">
.admin-stats {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.stat-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.chart-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}
.card-title {
  font-weight: 600;
}
</style>
