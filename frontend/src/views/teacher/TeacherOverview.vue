<template>
  <div class="teacher-overview" v-loading="loading">
    <div class="stat-cards">
      <StatCard title="教授课程" :value="courseCount" color="blue" />
      <StatCard title="签到会话" :value="sessionCount" color="green" />
      <StatCard title="进行中" :value="activeCount" color="amber" />
      <StatCard title="累计签到人次" :value="totalSigned" color="purple" />
    </div>

    <div class="chart-row">
      <el-card class="chart-card">
        <template #header><span class="card-title">近 15 次会话签到趋势</span></template>
        <EChart :option="trendOption" height="300px" />
      </el-card>
      <el-card class="chart-card">
        <template #header><span class="card-title">课程人数占比</span></template>
        <EChart :option="pieOption" height="300px" />
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { teacherApi } from '@/api/teacher';
import StatCard from '@/components/StatCard.vue';
import EChart from '@/components/EChart.vue';
import type { Course, CheckinSession } from '@/api/types';

const loading = ref(true);
const courses = ref<Course[]>([]);
const sessions = ref<CheckinSession[]>([]);

const courseCount = computed(() => courses.value.length);
const sessionCount = computed(() => sessions.value.length);
const activeCount = computed(
  () => sessions.value.filter((s) => s.status === 1).length,
);
const totalSigned = computed(
  () => sessions.value.reduce((sum, s) => sum + (s.signed_count || 0), 0),
);

const trendOption = computed(() => {
  // 近 15 次(倒序取前 15 再翻转为正序展示)
  const recent = sessions.value.slice(0, 15).reverse();
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 30, bottom: 60 },
    xAxis: {
      type: 'category',
      data: recent.map((s) => fmtShort(s.create_time)),
      axisLabel: { rotate: 30, fontSize: 11 },
    },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        name: '已签到',
        type: 'bar',
        data: recent.map((s) => s.signed_count || 0),
        itemStyle: { color: '#16337a' },
      },
    ],
  };
});

const pieOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c}人 ({d}%)' },
  legend: { bottom: 0, type: 'scroll' },
  series: [
    {
      type: 'pie',
      radius: ['40%', '70%'],
      data: courses.value.map((c) => ({
        name: c.course_id,
        value: c.student_count || 0,
      })),
      label: { formatter: '{b}\n{c}人' },
    },
  ],
}));

function fmtShort(t: string): string {
  // 简化时间显示为 MM-DD HH:mm
  const d = new Date(t);
  if (isNaN(d.valueOf())) return t;
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

async function load() {
  loading.value = true;
  try {
    const [c, s] = await Promise.all([
      teacherApi.myCourses(),
      teacherApi.listSessions(),
    ]);
    courses.value = c;
    sessions.value = s;
  } catch {
    /* http.ts 已 toast */
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<style scoped lang="scss">
.teacher-overview {
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
  grid-template-columns: 1.4fr 1fr;
  gap: 20px;
}
.card-title {
  font-weight: 600;
}
</style>
