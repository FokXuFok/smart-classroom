<template>
  <el-card>
    <template #header><span class="card-title">管辖班级</span></template>
    <el-table :data="classes" v-loading="loading" stripe>
      <el-table-column prop="class_id" label="班级代码" width="120" />
      <el-table-column prop="class_name" label="班级名称" min-width="160" />
      <el-table-column prop="grade" label="年级" width="80" />
      <el-table-column prop="major" label="专业" min-width="140" />
      <el-table-column prop="department" label="院系" min-width="120" />
      <el-table-column prop="student_count" label="学生数" width="80" />
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { counselorApi } from '@/api/counselor';
import type { CounselorClass } from '@/api/types';

const classes = ref<CounselorClass[]>([]);
const loading = ref(false);

async function load() {
  loading.value = true;
  try {
    classes.value = await counselorApi.classes();
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
