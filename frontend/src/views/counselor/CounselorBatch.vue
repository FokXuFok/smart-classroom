<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span class="card-title">批量提醒预警学生</span>
        <el-button text @click="load">刷新</el-button>
      </div>
    </template>
    <el-table
      :data="warnings"
      v-loading="loading"
      stripe
      @selection-change="onSelectionChange"
    >
      <el-table-column type="selection" width="50" />
      <el-table-column prop="student_no" label="学号" width="120" />
      <el-table-column prop="name" label="姓名" width="100" />
      <el-table-column prop="class_name" label="班级" width="120" />
      <el-table-column label="出勤率" width="100">
        <template #default="{ row }">
          {{ row.attendance_rate != null ? (row.attendance_rate * 100).toFixed(1) + '%' : '-' }}
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

    <div class="batch-form">
      <el-input v-model="title" placeholder="通知标题" style="width: 240px" />
      <el-input
        v-model="content"
        placeholder="通知内容(如:请尽快补勤)"
        style="flex: 1"
      />
      <el-button
        type="primary"
        :loading="sending"
        :disabled="!selected.length || !title"
        @click="onBatchSend"
      >
        批量推送({{ selected.length }}人)
      </el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { counselorApi } from '@/api/counselor';
import type { WarningRow } from '@/api/types';

const warnings = ref<WarningRow[]>([]);
const loading = ref(false);
const selected = ref<WarningRow[]>([]);
const title = ref('');
const content = ref('');
const sending = ref(false);

function onSelectionChange(rows: WarningRow[]) {
  selected.value = rows;
}

async function load() {
  loading.value = true;
  try {
    warnings.value = await counselorApi.warnings();
  } catch {
    /* ignore */
  } finally {
    loading.value = false;
  }
}

async function onBatchSend() {
  if (!selected.value.length || !title.value) {
    ElMessage.warning('请选择学生并填写标题');
    return;
  }
  sending.value = true;
  try {
    const r = await counselorApi.notify({
      student_nos: selected.value.map((s) => s.student_no),
      title: title.value,
      content: content.value || '请关注学业情况',
    });
    ElMessage.success(`已通知 ${r.sent} 名学生`);
    title.value = '';
    content.value = '';
  } catch {
    /* http.ts 已 toast */
  } finally {
    sending.value = false;
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
.batch-form {
  display: flex;
  gap: 12px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}
</style>
