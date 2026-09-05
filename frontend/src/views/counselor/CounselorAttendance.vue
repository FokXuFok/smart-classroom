<template>
  <div class="counselor-attendance" v-loading="loading">
    <el-card>
      <template #header><span class="card-title">班级概览</span></template>
      <el-table :data="classes" stripe>
        <el-table-column prop="class_id" label="班级代码" width="120" />
        <el-table-column prop="class_name" label="班级名称" min-width="160" />
        <el-table-column prop="grade" label="年级" width="80" />
        <el-table-column prop="major" label="专业" min-width="140" />
        <el-table-column prop="student_count" label="学生数" width="80" />
      </el-table>
    </el-card>
    <el-card>
      <template #header><span class="card-title">预警学生出勤率对比(升序)</span></template>
      <EChart v-if="warnings.length" :option="rateOption" height="320px" />
      <el-empty v-else description="暂无预警学生" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { counselorApi } from '@/api/counselor';
import EChart from '@/components/EChart.vue';
import type { CounselorClass, WarningRow } from '@/api/types';

const loading = ref(false);
const classes = ref<CounselorClass[]>([]);
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

async function load() {
  loading.value = true;
  try {
    const [c, w] = await Promise.all([
      counselorApi.classes(),
      counselorApi.warnings(),
    ]);
    classes.value = c;
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
.counselor-attendance {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.card-title {
  font-weight: 600;
}
</style>
