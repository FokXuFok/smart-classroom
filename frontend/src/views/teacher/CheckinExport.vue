<template>
  <div class="checkin-export">
    <el-card>
      <template #header><span class="card-title">考勤导出</span></template>
      <el-table :data="sessions" v-loading="loading" stripe>
        <el-table-column prop="course_name" label="课程" min-width="160" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'">
              {{ row.status === 1 ? '进行中' : '已结束' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="signed_count" label="已签" width="80" />
        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">{{ fmtTime(row.create_time) }}</template>
        </el-table-column>
        <el-table-column label="结束时间" width="160">
          <template #default="{ row }">
            {{ row.end_time ? fmtTime(row.end_time) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="onExport(row.id)">
              导出 Excel
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { teacherApi } from '@/api/teacher';
import { useDownload } from '@/composables/useDownload';
import { fmtTime } from '@/utils/format';
import type { CheckinSession } from '@/api/types';

const { download } = useDownload();
const loading = ref(false);
const sessions = ref<CheckinSession[]>([]);

async function load() {
  loading.value = true;
  try {
    sessions.value = await teacherApi.listSessions();
  } catch {
    /* ignore */
  } finally {
    loading.value = false;
  }
}

function onExport(id: number) {
  download(teacherApi.exportUrl(id));
}

onMounted(load);
</script>

<style scoped>
.card-title {
  font-weight: 600;
}
</style>
