<template>
  <div class="page-header">
    <h1 class="page-title">{{ title }}</h1>
  </div>
</template>

<script setup lang="ts">
defineProps<{ title?: string }>();
</script>
