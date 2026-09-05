<template>
  <div class="teacher-interact">
    <el-card>
      <template #header>
        <div class="card-header">
          <span class="card-title">课堂互动</span>
          <div class="header-actions">
            <el-select
              v-model="courseId"
              placeholder="选择课程"
              style="width: 220px"
              @change="loadAll"
            >
              <el-option
                v-for="c in courses"
                :key="c.course_id"
                :label="`${c.course_id} ${c.course_name}`"
                :value="c.course_id"
              />
            </el-select>
            <el-button
              type="primary"
              :loading="picking"
              :disabled="!courseId"
              @click="onRandomPick"
            >
              随机点名
            </el-button>
          </div>
        </div>
      </template>

      <div v-if="picked" class="picked-result">
        <el-alert
          :title="`点名结果:${picked.name}(${picked.student_no})`"
          type="success"
          :closable="false"
          show-icon
        />
      </div>

      <div v-if="stats" class="stat-row">
        <StatCard title="总互动" :value="stats.total" color="blue" />
        <StatCard title="今日" :value="stats.today_count" color="green" />
        <StatCard title="选课人数" :value="stats.enrolled_count" color="amber" />
      </div>

      <div v-if="stats" class="chart-row">
        <el-card class="chart-card">
          <template #header><span class="card-title">互动类型分布</span></template>
          <EChart :option="typePieOption" height="280px" />
        </el-card>
        <el-card class="chart-card">
          <template #header><span class="card-title">互动 Top10</span></template>
          <EChart :option="topBarOption" height="280px" />
        </el-card>
      </div>
    </el-card>

    <el-card>
      <template #header><span class="card-title">互动历史</span></template>
      <el-table :data="list" v-loading="listLoading" stripe>
        <el-table-column prop="student_name" label="学生" width="120">
          <template #default="{ row }">{{ row.student_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="typeTagType(row.interaction_type)">
              {{ typeCn(row.interaction_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="content" label="内容" min-width="160" />
        <el-table-column label="评分" width="80">
          <template #default="{ row }">{{ row.score ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="日期" width="120">
          <template #default="{ row }">{{ fmtTime(row.lesson_date, 'YYYY-MM-DD') }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { teacherApi } from '@/api/teacher';
import { interactionApi } from '@/api/interaction';
import StatCard from '@/components/StatCard.vue';
import EChart from '@/components/EChart.vue';
import { fmtTime } from '@/utils/format';
import type { Course, Interaction, InteractionStats, RandomPickResult } from '@/api/types';

const courses = ref<Course[]>([]);
const courseId = ref('');
const picking = ref(false);
const picked = ref<RandomPickResult | null>(null);
const stats = ref<InteractionStats | null>(null);
const list = ref<Interaction[]>([]);
const listLoading = ref(false);

const typePieOption = computed(() => {
  const byType = stats.value?.by_type || {};
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0 },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        data: Object.entries(byType).map(([k, v]) => ({
          name: typeCn(k),
          value: v,
        })),
      },
    ],
  };
});

const topBarOption = computed(() => {
  const top = stats.value?.top_students || [];
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 80, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'value', minInterval: 1 },
    yAxis: {
      type: 'category',
      data: top.map((t) => t.name || t.student_id).reverse(),
      axisLabel: { fontSize: 11 },
    },
    series: [
      {
        type: 'bar',
        data: top.map((t) => t.count).reverse(),
        itemStyle: { color: '#16337a' },
      },
    ],
  };
});

function typeCn(t: string): string {
  return { question: '提问', rating: '评分', random_pick: '点名' }[t] || t;
}

function typeTagType(t: string): '' | 'success' | 'info' | 'warning' | 'danger' {
  return { question: '', rating: 'warning', random_pick: 'success' }[t] as any || 'info';
}

async function loadCourses() {
  try {
    courses.value = await teacherApi.myCourses();
  } catch {
    /* ignore */
  }
}

async function loadAll() {
  if (!courseId.value) return;
  picked.value = null;
  loadStats();
  loadList();
}

async function loadStats() {
  if (!courseId.value) return;
  try {
    stats.value = await interactionApi.stats(courseId.value);
  } catch {
    /* ignore */
  }
}

async function loadList() {
  if (!courseId.value) return;
  listLoading.value = true;
  try {
    list.value = await interactionApi.list({ course_id: courseId.value });
  } catch {
    /* ignore */
  } finally {
    listLoading.value = false;
  }
}

async function onRandomPick() {
  if (!courseId.value) return;
  picking.value = true;
  try {
    picked.value = await interactionApi.randomPick(courseId.value);
    ElMessage.success(`点名:${picked.value.name}`);
    loadStats();
    loadList();
  } catch {
    /* http.ts 已 toast */
  } finally {
    picking.value = false;
  }
}

onMounted(loadCourses);
</script>

<style scoped lang="scss">
.teacher-interact {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-actions {
  display: flex;
  gap: 12px;
}
.card-title {
  font-weight: 600;
}
.picked-result {
  margin-bottom: 16px;
}
.stat-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin: 16px 0;
}
.chart-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}
</style>
