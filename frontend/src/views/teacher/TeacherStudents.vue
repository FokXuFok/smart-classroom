<template>
  <el-card>
    <template #header><span class="card-title">学生管理</span></template>
    <div class="filters">
      <el-select
        v-model="courseId"
        placeholder="选择课程"
        style="width: 240px"
        @change="onCourseChange"
      >
        <el-option
          v-for="c in courses"
          :key="c.course_id"
          :label="`${c.course_id} ${c.course_name}`"
          :value="c.course_id"
        />
      </el-select>
      <el-select
        v-model="sessionId"
        placeholder="选择签到会话"
        style="width: 280px"
        :disabled="!sessions.length"
        @change="loadStudents"
      >
        <el-option
          v-for="s in sessions"
          :key="s.id"
          :label="`${fmtTime(s.create_time)} (${s.status === 1 ? '进行中' : '已结束'})`"
          :value="s.id"
        />
      </el-select>
    </div>
    <el-empty
      v-if="!sessionId"
      description="请选择课程和签到会话查看学生名单(学生名单来自选课 + 签到会话)"
    />
    <el-table
      v-else
      :data="students"
      v-loading="loading"
      stripe
    >
      <el-table-column prop="student_no" label="学号" width="120" />
      <el-table-column prop="name" label="姓名" width="100" />
      <el-table-column prop="status" label="签到状态" width="100" />
      <el-table-column label="人脸重注册" width="160">
        <template #default="{ row }">
          <el-button
            size="small"
            type="primary"
            @click="onFaceRegen(row.student_no, row.name)"
          >
            授权重注册
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { teacherApi } from '@/api/teacher';
import { fmtTime } from '@/utils/format';
import type { Course, CheckinSession, DashboardStudent } from '@/api/types';

const courses = ref<Course[]>([]);
const courseId = ref('');
const sessions = ref<CheckinSession[]>([]);
const sessionId = ref<number | undefined>(undefined);
const students = ref<DashboardStudent[]>([]);
const loading = ref(false);

async function loadCourses() {
  try {
    courses.value = await teacherApi.myCourses();
  } catch {
    /* ignore */
  }
}

async function onCourseChange() {
  sessionId.value = undefined;
  students.value = [];
  if (!courseId.value) {
    sessions.value = [];
    return;
  }
  try {
    sessions.value = await teacherApi.listSessions(courseId.value);
    if (sessions.value.length > 0) {
      sessionId.value = sessions.value[0].id;
      loadStudents();
    }
  } catch {
    /* ignore */
  }
}

async function loadStudents() {
  if (!sessionId.value) return;
  loading.value = true;
  try {
    const data = await teacherApi.dashboard(sessionId.value);
    students.value = data.students;
  } catch {
    /* ignore */
  } finally {
    loading.value = false;
  }
}

async function onFaceRegen(studentNo: string, name: string) {
  try {
    await ElMessageBox.confirm(
      `确定授权 ${name}(${studentNo}) 重新注册人脸?`,
      '提示',
      { type: 'warning' },
    );
  } catch {
    return;
  }
  try {
    await teacherApi.allowFaceRegen(studentNo);
    ElMessage.success('已授权该学生重新注册人脸');
  } catch {
    /* ignore */
  }
}

onMounted(loadCourses);
</script>

<style scoped lang="scss">
.card-title {
  font-weight: 600;
}
.filters {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
</style>
