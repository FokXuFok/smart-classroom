<template>
  <el-card>
    <template #header><span class="card-title">我的课程</span></template>
    <el-table :data="courses" v-loading="loading" stripe>
      <el-table-column prop="course_id" label="课程代码" width="120" />
      <el-table-column prop="course_name" label="课程名称" min-width="160" />
      <el-table-column prop="credit" label="学分" width="80" />
      <el-table-column prop="hours" label="学时" width="80" />
      <el-table-column prop="semester" label="学期" width="140" />
      <el-table-column prop="student_count" label="选课人数" width="100" />
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { teacherApi } from '@/api/teacher';
import type { Course } from '@/api/types';

const courses = ref<Course[]>([]);
const loading = ref(false);

async function load() {
  loading.value = true;
  try {
    courses.value = await teacherApi.myCourses();
  } catch {
    /* ignore */
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.card-title {
  font-weight: 600;
}
</style>
