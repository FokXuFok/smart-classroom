<template>
  <div ref="elRef" class="echart-container" :style="{ height }"></div>
</template>

<script setup lang="ts">
import { ref, toRef } from 'vue';
import { useECharts } from '@/composables/useECharts';

const props = defineProps<{
  option: any;
  height?: string;
}>();

const elRef = ref<HTMLElement | null>(null);
useECharts(elRef, toRef(props, 'option'));
</script>

<style scoped>
.echart-container {
  width: 100%;
}
</style>
