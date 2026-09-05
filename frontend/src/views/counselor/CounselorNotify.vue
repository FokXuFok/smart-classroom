<template>
  <el-card>
    <template #header><span class="card-title">群发通知</span></template>
    <el-form :model="form" label-width="100px" style="max-width: 700px">
      <el-form-item label="班级" required>
        <el-select
          v-model="form.class_ids"
          multiple
          placeholder="选择班级(可多选)"
          style="width: 100%"
        >
          <el-option
            v-for="c in classes"
            :key="c.class_id"
            :label="`${c.class_id} ${c.class_name}(${c.student_count}人)`"
            :value="c.class_id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="标题" required>
        <el-input v-model="form.title" placeholder="通知标题" />
      </el-form-item>
      <el-form-item label="内容" required>
        <el-input
          v-model="form.content"
          type="textarea"
          :rows="5"
          placeholder="通知内容"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="sending" @click="onSend">
          发送
        </el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { counselorApi } from '@/api/counselor';
import type { CounselorClass } from '@/api/types';

const classes = ref<CounselorClass[]>([]);
const sending = ref(false);

const form = reactive({
  class_ids: [] as string[],
  title: '',
  content: '',
});

async function loadClasses() {
  try {
    classes.value = await counselorApi.classes();
  } catch {
    /* ignore */
  }
}

async function onSend() {
  if (!form.class_ids.length) {
    ElMessage.warning('请选择班级');
    return;
  }
  if (!form.title || !form.content) {
    ElMessage.warning('请填写标题和内容');
    return;
  }
  sending.value = true;
  try {
    const r = await counselorApi.notify({
      class_ids: form.class_ids,
      title: form.title,
      content: form.content,
    });
    ElMessage.success(`已通知 ${r.sent} 名学生`);
    form.title = '';
    form.content = '';
  } catch {
    /* http.ts 已 toast */
  } finally {
    sending.value = false;
  }
}

onMounted(loadClasses);
</script>

<style scoped>
.card-title {
  font-weight: 600;
}
</style>
