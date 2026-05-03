<template>
  <div class="config-card">
    <div class="config-header">
      <slot name="header" />
    </div>
    <div class="config-body">
      <slot />
    </div>
    <div class="config-footer">
      <slot name="footer" />
    </div>
  </div>
</template>

<script setup>
</script>

<style lang="scss" scoped>
.config-card {
  background: $card-bg;
  border: 1px solid #ebeef5;
  border-radius: $border-radius;
  margin-bottom: 16px;
  transition: box-shadow 0.2s;
  overflow: hidden;

  &:hover {
    box-shadow: $card-shadow;
  }
}

.config-header {
  padding: 16px 20px 12px;
  border-bottom: 1px solid #f0f0f0;
}

.config-body {
  padding: 12px 20px;
}

.config-footer {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
  padding: 8px 12px;
  border-top: 1px solid #f0f0f0;
  background: #fafafa;
}
</style>
