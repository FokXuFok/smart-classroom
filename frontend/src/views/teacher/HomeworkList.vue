<template>
  <div class="homework-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span class="card-title">作业管理</span>
          <div class="header-actions">
            <el-select
              v-model="courseFilter"
              placeholder="全部课程"
              clearable
              :loading="coursesLoading"
              style="width: 220px"
              @change="load"
            >
              <el-option
                v-for="c in courses"
                :key="c.course_id"
                :label="`${c.course_id} ${c.course_name}`"
                :value="c.course_id"
              />
            </el-select>
            <el-button type="primary" @click="router.push('/teacher/homework/new')">
              新建作业
            </el-button>
          </div>
        </div>
      </template>
      <el-table :data="list" v-loading="loading" stripe>
        <el-table-column prop="title" label="作业标题" min-width="160" />
        <el-table-column prop="course_id" label="课程" width="100" />
        <el-table-column prop="programming_language" label="语言" width="80" />
        <el-table-column prop="max_score" label="满分" width="80" />
        <el-table-column label="截止时间" width="160">
          <template #default="{ row }">
            {{ row.deadline ? fmtTime(row.deadline) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="test_case_count" label="用例数" width="80" />
        <el-table-column label="提交" width="100">
          <template #default="{ row }">
            {{ row.submit_count }}/{{ row.student_count }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="320" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              type="primary"
              @click="router.push(`/teacher/homework/${row.id}`)"
            >
              编辑
            </el-button>
            <el-button size="small" @click="onSimilarity(row.id)">查重</el-button>
            <el-button size="small" @click="onRejudge(row.id)">重评</el-button>
            <el-button size="small" @click="onExport(row.id)">成绩册</el-button>
            <el-button
              size="small"
              type="danger"
              :loading="deletingId === row.id"
              @click="onDelete(row.id)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { homeworkApi } from '@/api/homework';
import { teacherApi } from '@/api/teacher';
import { useDownload } from '@/composables/useDownload';
import { fmtTime } from '@/utils/format';
import type { Course, Homework } from '@/api/types';

const router = useRouter();
const { download } = useDownload();

const courses = ref<Course[]>([]);
const coursesLoading = ref(false);
const list = ref<Homework[]>([]);
const loading = ref(false);
const courseFilter = ref('');
const deletingId = ref<number | null>(null);

async function loadCourses() {
  coursesLoading.value = true;
  try {
    courses.value = await teacherApi.myCourses();
  } catch {
    /* ignore */
  } finally {
    coursesLoading.value = false;
  }
}

async function load() {
  loading.value = true;
  try {
    list.value = await homeworkApi.list(courseFilter.value);
  } catch {
    /* ignore */
  } finally {
    loading.value = false;
  }
}

async function onSimilarity(id: number) {
  try {
    const r: any = await homeworkApi.similarity(id);
    ElMessage.success(`查重完成,命中 ${r.length} 对疑似抄袭`);
  } catch {
    /* ignore */
  }
}

async function onRejudge(id: number) {
  try {
    await ElMessageBox.confirm('确定重评所有提交?', '提示', { type: 'warning' });
  } catch {
    return;
  }
  try {
    const r: any = await homeworkApi.rejudge(id);
    ElMessage.success(`重评任务已提交,共 ${r.rejudge_count} 条`);
  } catch {
    /* ignore */
  }
}

function onExport(id: number) {
  download(homeworkApi.gradebookExportUrl(id));
}

async function onDelete(id: number) {
  try {
    await ElMessageBox.confirm('确定删除该作业?', '提示', { type: 'warning' });
  } catch {
    return;
  }
  deletingId.value = id;
  try {
    await homeworkApi.delete(id);
    ElMessage.success('作业已删除');
    await load();
  } catch {
    /* http.ts 已 toast(有提交记录拒绝) */
  } finally {
    deletingId.value = null;
  }
}

onMounted(() => {
  loadCourses();
  load();
});
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
</style>
