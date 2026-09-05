<template>
  <div class="counselor-students">
    <el-card class="filter-card">
      <template #header><span class="card-title">学生档案</span></template>
      <div class="filters">
        <el-select
          v-model="classId"
          placeholder="选择班级"
          style="width: 240px"
          @change="onClassChange"
        >
          <el-option
            v-for="c in classes"
            :key="c.class_id"
            :label="`${c.class_id} ${c.class_name}`"
            :value="c.class_id"
          />
        </el-select>
        <el-input
          v-model="keyword"
          placeholder="搜索学号/姓名"
          style="width: 200px"
          clearable
        />
      </div>
      <el-table
        :data="filteredStudents"
        v-loading="studentsLoading"
        stripe
        highlight-current-row
        @current-change="onSelectStudent"
        style="margin-top: 12px"
        max-height="240"
      >
        <el-table-column prop="student_no" label="学号" width="120" />
        <el-table-column prop="name" label="姓名" width="100" />
        <el-table-column prop="class_id" label="班级" width="100" />
      </el-table>
    </el-card>

    <el-card v-if="profile" class="profile-card" v-loading="profileLoading">
      <template #header>
        <span class="card-title">
          {{ profile.student.name }}({{ profile.student.student_no }})学业档案
        </span>
      </template>
      <div class="profile-grid">
        <div class="info-block">
          <h4>基本信息</h4>
          <p>班级:{{ profile.student.class_name || profile.student.class_id }}</p>
          <p>性别:{{ profile.student.gender === 1 ? '男' : '女' }}</p>
          <p>电话:{{ profile.student.phone || '-' }}</p>
          <p>邮箱:{{ profile.student.email || '-' }}</p>
        </div>
        <div class="rate-block">
          <h4>出勤率</h4>
          <el-progress
            type="circle"
            :percentage="ratePercent"
            :color="rateColor"
            :width="120"
          />
          <p class="rate-total">共 {{ profile.attendance.total }} 条记录</p>
        </div>
      </div>

      <div class="section">
        <h4>最近考勤(10 条)</h4>
        <el-table :data="profile.attendance.recent" stripe size="small" max-height="200">
          <el-table-column prop="course_name" label="课程" min-width="140" />
          <el-table-column prop="attendance_date" label="日期" width="120" />
          <el-table-column prop="status_cn" label="状态" width="80" />
        </el-table>
      </div>

      <div class="section">
        <h4>成绩趋势</h4>
        <EChart v-if="profile.grades.length" :option="gradeOption" height="240px" />
        <el-empty v-else description="暂无成绩记录" />
      </div>
    </el-card>
    <el-empty v-else description="请从上方选择学生查看档案" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { counselorApi } from '@/api/counselor';
import EChart from '@/components/EChart.vue';
import type {
  CounselorClass,
  CounselorStudent,
  StudentProfile,
} from '@/api/types';

const classes = ref<CounselorClass[]>([]);
const classId = ref('');
const students = ref<CounselorStudent[]>([]);
const studentsLoading = ref(false);
const keyword = ref('');
const profile = ref<StudentProfile | null>(null);
const profileLoading = ref(false);

const filteredStudents = computed(() => {
  if (!keyword.value) return students.value;
  const kw = keyword.value.toLowerCase();
  return students.value.filter(
    (s) =>
      s.student_no.toLowerCase().includes(kw) ||
      s.name.toLowerCase().includes(kw),
  );
});

const ratePercent = computed(() => {
  const r = profile.value?.attendance.attendance_rate;
  return r != null ? Math.round(r * 100) : 0;
});

const rateColor = computed(() => {
  const r = ratePercent.value;
  if (r >= 80) return '#16a34a';
  if (r >= 60) return '#f59e0b';
  return '#dc2626';
});

const gradeOption = computed(() => {
  const grades = profile.value?.grades || [];
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 20, bottom: 60 },
    xAxis: {
      type: 'category',
      data: grades.map((g) => g.homework_title || `#${g.homework_id}`),
      axisLabel: { rotate: 30, fontSize: 11 },
    },
    yAxis: { type: 'value', max: 100 },
    series: [
      {
        type: 'line',
        data: grades.map((g) => g.score),
        smooth: true,
        itemStyle: { color: '#16337a' },
        areaStyle: { opacity: 0.1 },
      },
    ],
  };
});

async function loadClasses() {
  try {
    classes.value = await counselorApi.classes();
  } catch {
    /* ignore */
  }
}

async function onClassChange() {
  profile.value = null;
  if (!classId.value) {
    students.value = [];
    return;
  }
  studentsLoading.value = true;
  try {
    students.value = await counselorApi.students(classId.value);
  } catch {
    /* ignore */
  } finally {
    studentsLoading.value = false;
  }
}

async function onSelectStudent(row: CounselorStudent | null) {
  if (!row) return;
  profileLoading.value = true;
  try {
    profile.value = await counselorApi.profile(row.student_no);
  } catch {
    /* ignore */
  } finally {
    profileLoading.value = false;
  }
}

onMounted(loadClasses);
</script>

<style scoped lang="scss">
.counselor-students {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.filters {
  display: flex;
  gap: 12px;
}
.profile-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  margin-bottom: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--border);
  h4 {
    margin-bottom: 12px;
    color: var(--blue-deep);
  }
  p {
    line-height: 1.8;
    color: var(--text);
  }
}
.rate-block {
  text-align: center;
  .rate-total {
    margin-top: 8px;
    color: var(--text-sub);
    font-size: 13px;
  }
}
.section {
  margin-top: 20px;
  h4 {
    margin-bottom: 12px;
    color: var(--blue-deep);
  }
}
.card-title {
  font-weight: 600;
}
</style>
