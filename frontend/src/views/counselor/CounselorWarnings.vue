<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span class="card-title">预警学生</span>
        <el-button text @click="load">刷新</el-button>
      </div>
    </template>
    <el-empty
      v-if="!loading && rows.length === 0"
      description="暂无预警学生(出勤率<80% 或 累计缺勤≥3次 或 作业均分低于班级均分20分)"
    />
    <el-table v-else :data="rows" v-loading="loading" stripe>
      <el-table-column prop="student_no" label="学号" width="120" />
      <el-table-column prop="name" label="姓名" width="100" />
      <el-table-column prop="class_name" label="班级" width="140" />
      <el-table-column label="出勤率" width="100">
        <template #default="{ row }">
          {{ row.attendance_rate != null ? (row.attendance_rate * 100).toFixed(1) + '%' : '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="absent_count" label="缺勤次数" width="100" />
      <el-table-column label="作业均分" width="100">
        <template #default="{ row }">
          {{ row.homework_avg != null ? row.homework_avg : '-' }}
        </template>
      </el-table-column>
      <el-table-column label="预警原因" min-width="320">
        <template #default="{ row }">
          <el-tag
            v-for="(r, i) in row.reasons"
            :key="i"
            type="danger"
            size="small"
            style="margin: 2px"
          >
            {{ r }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { counselorApi } from '@/api/counselor';
import type { WarningRow } from '@/api/types';

const rows = ref<WarningRow[]>([]);
const loading = ref(false);

async function load() {
  loading.value = true;
  try {
    rows.value = await counselorApi.warnings();
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
.card-title {
  font-weight: 600;
}
</style>
