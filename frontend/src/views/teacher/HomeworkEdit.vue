<template>
  <div class="homework-edit">
    <el-card v-loading="loading">
      <template #header>
        <div class="card-header">
          <span class="card-title">{{ isEdit ? '编辑作业' : '新建作业' }}</span>
          <el-button text @click="router.back()">← 返回</el-button>
        </div>
      </template>
      <el-form :model="form" label-width="120px" style="max-width: 900px">
        <el-form-item label="课程" required>
          <el-select
            v-model="form.course_id"
            :disabled="isEdit"
            placeholder="选择课程"
            style="width: 320px"
          >
            <el-option
              v-for="c in courses"
              :key="c.course_id"
              :label="`${c.course_id} ${c.course_name}`"
              :value="c.course_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="作业标题" required>
          <el-input v-model="form.title" placeholder="作业标题" />
        </el-form-item>
        <el-form-item label="作业描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="作业描述"
          />
        </el-form-item>
        <el-form-item label="编程语言">
          <el-select v-model="form.programming_language" style="width: 160px">
            <el-option label="Python" value="python" />
            <el-option label="C" value="c" />
            <el-option label="C++" value="cpp" />
            <el-option label="Java" value="java" />
          </el-select>
        </el-form-item>
        <el-form-item label="满分">
          <el-input-number v-model="form.max_score" :min="1" :max="1000" />
        </el-form-item>
        <el-form-item label="截止时间">
          <el-date-picker
            v-model="form.deadline"
            type="datetime"
            placeholder="选择截止时间"
            style="width: 240px"
          />
        </el-form-item>
        <el-form-item label="允许迟交">
          <el-switch v-model="form.allow_late_submit" />
        </el-form-item>

        <el-form-item label="测试用例">
          <div class="cases">
            <div
              v-for="(tc, i) in form.test_cases"
              :key="i"
              class="case-row"
            >
              <el-input
                v-model="tc.name"
                placeholder="用例名"
                style="width: 120px"
              />
              <el-input
                v-model="tc.test_input"
                type="textarea"
                :rows="2"
                placeholder="输入"
                class="case-input"
              />
              <el-input
                v-model="tc.expected_output"
                type="textarea"
                :rows="2"
                placeholder="期望输出"
                class="case-input"
              />
              <el-input-number
                v-model="tc.score_weight"
                :min="0"
                :step="0.5"
                style="width: 110px"
              />
              <el-checkbox v-model="tc.is_public">公开</el-checkbox>
              <el-button
                type="danger"
                size="small"
                @click="form.test_cases.splice(i, 1)"
              >
                删除
              </el-button>
            </div>
            <el-button @click="addCase">+ 添加用例</el-button>
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="onSave">
            保存
          </el-button>
          <el-button @click="router.back()">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { homeworkApi } from '@/api/homework';
import { teacherApi } from '@/api/teacher';
import type { Course, TestCase } from '@/api/types';

const route = useRoute();
const router = useRouter();

const hwId = computed(() => route.params.id as string | undefined);
const isEdit = computed(() => !!hwId.value && hwId.value !== 'new');

const courses = ref<Course[]>([]);
const loading = ref(false);
const saving = ref(false);

const form = reactive({
  course_id: '',
  title: '',
  description: '',
  programming_language: 'python',
  max_score: 100,
  deadline: null as Date | null,
  allow_late_submit: false,
  test_cases: [] as TestCase[],
});

function addCase() {
  form.test_cases.push({
    name: `用例${form.test_cases.length + 1}`,
    test_input: '',
    expected_output: '',
    score_weight: 1,
    is_public: false,
  });
}

async function loadCourses() {
  try {
    courses.value = await teacherApi.myCourses();
  } catch {
    /* ignore */
  }
}

async function loadDetail() {
  if (!isEdit.value) return;
  loading.value = true;
  try {
    const d = await homeworkApi.detail(Number(hwId.value));
    form.course_id = d.course_id;
    form.title = d.title;
    form.description = d.description || '';
    form.programming_language = d.programming_language;
    form.max_score = d.max_score;
    form.deadline = d.deadline ? new Date(d.deadline) : null;
    form.allow_late_submit = !!d.allow_late_submit;
    form.test_cases = d.test_cases.map((c) => ({
      ...c,
      is_public: !!c.is_public,
    }));
    if (form.test_cases.length === 0) addCase();
  } catch {
    /* ignore */
  } finally {
    loading.value = false;
  }
}

async function onSave() {
  if (!form.course_id) {
    ElMessage.warning('请选择课程');
    return;
  }
  if (!form.title) {
    ElMessage.warning('请输入作业标题');
    return;
  }
  saving.value = true;
  try {
    const payload = {
      course_id: form.course_id,
      title: form.title,
      description: form.description,
      programming_language: form.programming_language,
      max_score: form.max_score,
      deadline: form.deadline ? form.deadline.toISOString() : null,
      allow_late_submit: form.allow_late_submit,
      test_cases: form.test_cases,
    };
    if (isEdit.value) {
      await homeworkApi.update(Number(hwId.value), payload);
    } else {
      await homeworkApi.create(payload);
    }
    router.replace('/teacher/homework');
    ElMessage.success(isEdit.value ? '作业已更新' : '作业创建成功');
  } catch {
    /* http.ts 已 toast */
  } finally {
    saving.value = false;
  }
}

onMounted(() => {
  loadCourses();
  loadDetail();
  if (!isEdit.value && form.test_cases.length === 0) addCase();
});
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
.cases {
  width: 100%;
}
.case-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px dashed var(--border);
  .case-input {
    flex: 1;
    min-width: 200px;
  }
}
</style>
