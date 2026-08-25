<template>
  <div class="toast-container">
    <TransitionGroup name="toast">
      <div v-for="t in toast.toasts" :key="t.id" :class="['toast', t.type]">
        <span class="toast-icon">{{ icons[t.type] }}</span>
        <span class="toast-msg">{{ t.message }}</span>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup>
import { useToast } from '../composables/useToast'
const toast = useToast()
const icons = { success: '✓', error: '✗', warning: '⚠', info: 'ℹ' }
</script>

<style scoped>
.toast-container {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 380px;
}
.toast {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 20px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  box-shadow: 0 8px 24px rgba(0,0,0,0.12);
  backdrop-filter: blur(8px);
}
.toast.success { background: #ecfdf5; color: #059669; border-left: 4px solid #10b981; }
.toast.error { background: #fef2f2; color: #dc2626; border-left: 4px solid #ef4444; }
.toast.warning { background: #fffbeb; color: #d97706; border-left: 4px solid #f59e0b; }
.toast.info { background: #eff6ff; color: #2563eb; border-left: 4px solid #3b82f6; }
.toast-icon { font-size: 16px; font-weight: 700; min-width: 20px; text-align: center; }
.toast.warning .toast-icon { margin-right: 4px; }
.toast-msg { flex: 1; }
.toast-enter-active { transition: all 0.3s ease; }
.toast-leave-active { transition: all 0.3s ease; }
.toast-enter-from { opacity: 0; transform: translateX(60px); }
.toast-leave-to { opacity: 0; transform: translateX(60px); }
</style>
