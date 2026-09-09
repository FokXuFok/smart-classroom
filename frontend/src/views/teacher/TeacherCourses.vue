<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span class="card-title">我的课程 · 上课安排</span>
        <div class="header-actions">
          <el-input
            v-model="keyword"
            placeholder="输入课程代码 / 名称筛选"
            clearable
            :prefix-icon="Search"
            style="width: 300px"
          />
          <el-button :loading="loading" @click="load">刷新</el-button>
        </div>
      </div>
    </template>
    <el-alert
      class="tip"
      title="大学课堂为合班大课，一门课对应一个授课安排：选课人数为课程全部选课学生；教室/上课时间来自课表，多时段分别列出。"
      type="info"
      :closable="false"
    />
    <el-table :data="filtered" v-loading="loading" stripe>
      <el-table-column prop="course_id" label="课程代码" width="110" />
      <el-table-column prop="course_name" label="课程名称" min-width="170" />
      <el-table-column label="学分" width="70">
        <template #default="{ row }">{{ row.credit ?? '—' }}</template>
      </el-table-column>
      <el-table-column label="学时" width="70">
        <template #default="{ row }">{{ row.hours ?? '—' }}</template>
      </el-table-column>
      <el-table-column label="选课人数" width="100" sortable :sort-method="countSort">
        <template #default="{ row }">
          <b>{{ row.student_count }}</b>
          <span class="light"> 人</span>
        </template>
      </el-table-column>
      <el-table-column label="教室" width="150">
        <template #default="{ row }">
          <template v-if="row.classrooms.length">
            <el-tag
              v-for="r in row.classrooms"
              :key="r"
              size="small"
              class="room-tag"
            >
              {{ r }}
            </el-tag>
          </template>
          <span v-else class="light">—</span>
        </template>
      </el-table-column>
      <el-table-column label="上课时间" min-width="240">
        <template #default="{ row }">
          <template v-if="row.times.length">
            <div v-for="(t, i) in row.times" :key="i" class="time-line">
              <el-icon v-if="i === 0" class="time-icon"><Clock /></el-icon>
              {{ weekdayCn(t.weekday) }} {{ t.start_time }}-{{ t.end_time }}
              <span class="light">{{ t.weeks ? `(第${t.weeks}周)` : '' }}</span>
            </div>
          </template>
          <el-tag v-else size="small" type="warning">未排课</el-tag>
        </template>
      </el-table-column>
    </el-table>
    <div class="foot">
      <span class="light">
        当前显示 {{ filtered.length }} 门课程（共 {{ rows.length }} 门）
      </span>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { Clock, Search } from '@element-plus/icons-vue';
import { teacherApi } from '@/api/teacher';
import type { CourseTeachingRow } from '@/api/types';

const rows = ref<CourseTeachingRow[]>([]);
const loading = ref(false);
const keyword = ref('');

const WEEK = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];

function weekdayCn(w: number): string {
  return WEEK[w - 1] || `周${w}`;
}

function countSort(a: CourseTeachingRow, b: CourseTeachingRow): number {
  return a.student_count - b.student_count;
}

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase();
  if (!kw) return rows.value;
  // 课程代码/名称关键词筛选(忽略大小写,模糊匹配)
  return rows.value.filter(
    (r) =>
      r.course_id.toLowerCase().includes(kw) ||
      (r.course_name || '').toLowerCase().includes(kw),
  );
});

async function load() {
  loading.value = true;
  try {
    rows.value = await teacherApi.courseTeaching();
  } catch {
    /* ignore */
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<style scoped lang="scss">
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
.light {
  color: var(--text-sub);
  font-size: 12px;
  line-height: 1.4;
}
.tip {
  margin-bottom: 14px;
}
.room-tag {
  margin: 2px 4px 2px 0;
}
.time-line {
  display: flex;
  align-items: center;
  gap: 4px;
  line-height: 1.7;
  font-size: 13px;
}
.time-icon {
  color: var(--text-sub);
}
.foot {
  margin-top: 12px;
}
</style>
