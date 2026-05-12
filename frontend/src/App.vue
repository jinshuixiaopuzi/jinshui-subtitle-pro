<script setup lang="ts">
import { ref, onMounted } from 'vue'
import ActivationScreen from './components/ActivationScreen.vue'
import MainEditor from './components/MainEditor.vue'

const activated = ref(false)
const engineReady = ref(false)

onMounted(async () => {
  // 尝试调用 Tauri API 检查激活状态
  try {
    const { invoke } = await import('@tauri-apps/api/core')
    const status: { activated: boolean; fingerprint: string } = await invoke('get_license_status')
    activated.value = status.activated
  } catch {
    // 非 Tauri 环境（浏览器开发模式），跳过激活直接展示
    activated.value = true
  }
})

function onActivated() {
  activated.value = true
}

function onEngineReady() {
  engineReady.value = true
}
</script>

<template>
  <div class="h-screen w-screen bg-gray-950 text-white overflow-hidden">
    <ActivationScreen v-if="!activated" @activated="onActivated" />
    <MainEditor v-else @engine-ready="onEngineReady" />
  </div>
</template>
