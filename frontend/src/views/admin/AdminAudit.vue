<template>
  <div class="admin-audit" v-loading="loading">
    <el-card class="audit-card">
      <template #header>
        <div class="header-bar">
          <span class="card-title">操作审计日志</span>
          <div class="filter-bar">
            <el-input
              v-model="actionFilter"
              placeholder="按 action 过滤,如 user_create / course_update"
              clearable
              style="width: 320px"
              @keyup.enter="onSearch"
              @clear="onSearch"
            />
            <el-button type="primary" @click="onSearch">搜索</el-button>
          </div>
        </div>
      </template>

      <el-table :data="items" stripe border style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="时间" width="160">
          <template #default="{ row }">{{ fmtTime(row.create_time) }}</template>
        </el-table-column>
        <el-table-column label="角色" width="100">
          <template #default="{ row }">
            <el-tag :type="roleTagType(row.user_role)" effect="light">
              {{ row.user_role }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="user_id" label="用户 ID" width="160" />
        <el-table-column label="Action" width="180">
          <template #default="{ row }">
            <el-tag type="info" effect="plain">{{ row.action }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column
          prop="target_type"
          label="目标类型"
          width="120"
          show-overflow-tooltip
        >
          <template #default="{ row }">{{ row.target_type || '-' }}</template>
        </el-table-column>
        <el-table-column
          prop="target_id"
          label="目标 ID"
          width="160"
          show-overflow-tooltip
        >
          <template #default="{ row }">{{ row.target_id || '-' }}</template>
        </el-table-column>
        <el-table-column label="详情" min-width="240">
          <template #default="{ row }">
            <el-tooltip
              v-if="row.detail"
              :content="row.detail"
              placement="top"
              :show-after="300"
            >
              <div class="ellipsis-cell">{{ row.detail }}</div>
            </el-tooltip>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @current-change="load"
          @size-change="onSizeChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { adminApi } from '@/api/admin';
import type { AdminAudit } from '@/api/types';

const loading = ref(false);
const items = ref<AdminAudit[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const actionFilter = ref('');

async function load() {
  loading.value = true;
  try {
    const res = await adminApi.listAudit({
      page: page.value,
      page_size: pageSize.value,
      action: actionFilter.value.trim() || undefined,
    });
    items.value = res.items;
    total.value = res.total;
  } catch {
    /* http.ts 已 toast */
  } finally {
    loading.value = false;
  }
}

function onSearch() {
  page.value = 1;
  load();
}

function onSizeChange(size: number) {
  pageSize.value = size;
  page.value = 1;
  load();
}

function fmtTime(t: string): string {
  const d = new Date(t);
  if (isNaN(d.valueOf())) return t;
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(
    d.getHours(),
  )}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function roleTagType(role: string) {
  switch (role) {
    case 'student':
      return 'primary';
    case 'teacher':
      return 'success';
    case 'counselor':
      return 'warning';
    case 'admin':
      return 'danger';
    default:
      return 'info';
  }
}

onMounted(load);
</script>

<style scoped lang="scss">
.admin-audit {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.audit-card {
  width: 100%;
}
.header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.card-title {
  font-weight: 600;
}
.filter-bar {
  display: flex;
  gap: 8px;
  align-items: center;
}
.ellipsis-cell {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: default;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
