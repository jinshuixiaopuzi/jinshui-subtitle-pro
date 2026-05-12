<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{ activated: [] }>()
const code = ref('')
const loading = ref(false)
const error = ref('')
const exiting = ref(false)

async function activate() {
  if (!code.value.trim()) return
  loading.value = true
  error.value = ''
  try {
    const { invoke } = await import('@tauri-apps/api/core')
    await invoke('activate_license', { code: code.value.trim() })
    // Link Start 退出动画
    exiting.value = true
    setTimeout(() => emit('activated'), 1200)
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
}

function fillCode() {
  code.value = 'B站：金水1987'
}
</script>

<template>
  <div
    class="h-full w-full sao-grid sao-crt flex items-center justify-center relative overflow-hidden"
    :class="{ 'animate-exit': exiting }"
  >
    <!-- 背景数据流光效 -->
    <div
      class="absolute inset-0 opacity-[0.04] pointer-events-none"
      :style="{
        backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 30px, rgba(0,245,212,1) 30px, transparent 31px)',
        backgroundSize: '100% 60px',
        animation: exiting ? 'none' : 'data-stream 3s linear infinite'
      }"
    ></div>

    <!-- 顶部品牌 -->
    <div class="absolute top-6 left-6 flex items-center gap-2.5 z-10">
      <div class="w-7 h-7 flex items-center justify-center border border-accent/40 text-accent text-xs font-bold tracking-widest">
        金
      </div>
      <span class="text-xs text-text-dim tracking-[0.2em]">JINSHUI SUBTITLE PRO</span>
    </div>

    <!-- 中央卡片 -->
    <div
      class="relative flex flex-col items-center z-10 transition-all duration-1000"
      :class="exiting ? 'opacity-0 scale-150 blur-xl' : ''"
    >
      <!-- 脉冲光环 -->
      <div class="relative mb-10">
        <div class="w-24 h-24 rounded-full border border-primary/30 animate-[pulse-ring_2.5s_ease-in-out_infinite] absolute inset-0"></div>
        <div class="w-24 h-24 rounded-full border border-accent/20 animate-[pulse-ring_2.5s_ease-in-out_infinite_0.8s] absolute inset-0"></div>
        <div class="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center relative z-10 backdrop-blur-sm border border-primary/30">
          <span class="text-3xl">🎬</span>
        </div>
      </div>

      <!-- 标题 -->
      <h1 class="text-2xl font-bold tracking-[0.15em] text-text-primary mb-1">LINK START</h1>
      <p class="text-xs text-text-dim tracking-[0.1em] mb-8">—— 激活金水字幕 Pro ——</p>

      <!-- 激活卡片 -->
      <div class="w-80 bg-surface/60 backdrop-blur-xl border border-primary/20 p-6 sao-hud">
        <div class="corner-bl"></div>
        <div class="corner-br"></div>

        <div class="mb-4">
          <label class="text-[10px] text-text-dim tracking-wider block mb-2">ACTIVATION CODE</label>
          <div class="relative">
            <input
              v-model="code"
              type="text"
              placeholder="B站：金水1987"
              class="w-full px-3 py-2.5 bg-background/80 border border-primary/30 text-sm text-text-primary placeholder-text-dim/30 focus:outline-none focus:border-primary/70 transition-all tracking-wider"
              @keyup.enter="activate"
            />
            <button
              v-if="!code"
              @click="fillCode"
              class="absolute right-2 top-1/2 -translate-y-1/2 text-[9px] text-accent/50 hover:text-accent transition-colors tracking-wider"
            >
              AUTO-FILL
            </button>
          </div>
        </div>

        <p v-if="error" class="text-[11px] text-danger mb-3 text-center bg-danger/5 py-1.5 tracking-wider">{{ error }}</p>

        <button
          @click="activate"
          :disabled="loading || !code.trim()"
          class="w-full py-2.5 text-xs font-semibold tracking-[0.2em] bg-primary/20 border border-primary/50 text-primary hover:bg-primary/30 hover:shadow-[0_0_20px_rgba(157,78,221,0.3)] disabled:opacity-20 disabled:cursor-not-allowed transition-all duration-300"
        >
          {{ loading ? 'AUTHENTICATING...' : '▶  LINK START' }}
        </button>

        <div class="mt-4 pt-3 border-t border-primary/10 text-center">
          <p class="text-[9px] text-text-dim/50 tracking-wider">
            FREE LICENSE · MADE WITH ❤️ BY
            <span class="text-accent/60">B站 金水1987</span>
          </p>
        </div>
      </div>
    </div>

    <!-- 底部版本号 -->
    <div class="absolute bottom-4 text-[9px] text-text-dim/20 tracking-[0.3em]">SYSTEM v2.0.0</div>
  </div>
</template>

<style scoped>
.animate-exit {
  animation: link-start-exit 1.2s ease-in-out forwards;
}
</style>
