<template>
  <div class="stat-card" :class="`stat-${color || 'blue'}`">
    <div class="stat-value">{{ value }}</div>
    <div class="stat-label">{{ title }}</div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ title: string; value: number | string; color?: string }>();
</script>

<style scoped lang="scss">
.stat-card {
  background: #fff;
  border-radius: 8px;
  border: 1px solid var(--border);
  padding: 20px;
  position: relative;
  overflow: hidden;
  &::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 4px;
  }
  .stat-value {
    font-size: 28px;
    font-weight: 700;
    line-height: 1.2;
  }
  .stat-label {
    font-size: 13px;
    color: var(--text-sub);
    margin-top: 4px;
  }
}
.stat-blue::before { background: var(--blue); }
.stat-green::before { background: var(--ok); }
.stat-amber::before { background: var(--amber); }
.stat-purple::before { background: var(--pending); }
.stat-red::before { background: var(--absent); }
</style>
