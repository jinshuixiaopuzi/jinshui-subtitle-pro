<script setup lang="ts">
import { ref, watch, computed } from 'vue'

const props = defineProps<{ config: any }>()
const emit = defineEmits<{ close: []; save: [config: any] }>()

const cfg = ref({ ...props.config })

// ===== 颜色预设 =====
const colorPresets = [
  '#FFFFFF', '#FFFF00', '#00FF00', '#00FFFF', '#FF00FF', '#FF0000', '#0000FF',
  '#CCCCCC', '#FFD700', '#FF8C00', '#FF1493', '#7B68EE', '#A9A9A9', '#808080',
  '#F0E68C', '#E6E6FA', '#B0E0E6', '#98FB98', '#FFDAB9', '#DDA0DD',
]

// ===== 显示模式 =====
const displayMode = ref(cfg.value.mode || 'bilingual')
watch(displayMode, (v) => { cfg.value.mode = v })

// ===== 位置互换 =====
const swapped = ref(cfg.value.swap_order || false)
watch(swapped, (v) => { cfg.value.swap_order = v })

// ===== 独立底边距（原文/译文各自距屏幕底边，直接绑定 cfg 无需本地 ref） =====
// v-model.number 直接写入 cfg.value，无中间变量，保存时不会丢失

// ===== 字体列表（从系统 API 动态获取） =====
const fontOptions = ref<string[]>([])
const fontsLoaded = ref(false)
async function loadSystemFonts() {
  try {
    const resp = await fetch('http://127.0.0.1:8712/api/fonts')
    const data = await resp.json()
    if (data.success && data.fonts.length > 0) {
      fontOptions.value = data.fonts
      fontsLoaded.value = true
      return
    }
  } catch {}
  // Fallback
  fontOptions.value = [
    'Microsoft YaHei', 'SimHei', 'SimSun', 'FangSong', 'KaiTi', 'YouYuan',
    'Arial', 'Segoe UI', 'Consolas', 'Courier New', 'Times New Roman',
  ]
  fontsLoaded.value = true
}
loadSystemFonts()

function inFontList(f: string | undefined): boolean {
  return !!(f && fontOptions.value.includes(f))
}
const transFontCustom = ref(false)
const origFontCustom = ref(false)
watch(fontOptions, () => {
  transFontCustom.value = !inFontList(cfg.value.trans_font)
  origFontCustom.value = !inFontList(cfg.value.orig_font)
})
watch(() => cfg.value.trans_font, (v) => { transFontCustom.value = v && !fontOptions.value.includes(v) })
watch(() => cfg.value.orig_font, (v) => { origFontCustom.value = v && !fontOptions.value.includes(v) })

// ===== 预览背景 =====
const previewBg = ref(cfg.value.preview_bg || '')
function selectBgFile() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*,video/mp4'
  input.onchange = () => {
    const file = input.files?.[0]
    if (file) {
      const url = URL.createObjectURL(file)
      previewBg.value = url
      cfg.value.preview_bg = url
    }
  }
  input.click()
}
function clearBg() { previewBg.value = ''; cfg.value.preview_bg = '' }

// ===== 预设 =====
const presets = [
  { name: '经典双语', trans_size: 45, orig_size: 30, trans_color: '#FFFFFF', orig_color: '#CCCCCC', trans_bottom_margin: 60, orig_bottom_margin: 10 },
  { name: '大号清晰', trans_size: 55, orig_size: 36, trans_color: '#FFFF00', orig_color: '#AAAAAA', trans_bottom_margin: 80, orig_bottom_margin: 15 },
  { name: '电影风格', trans_size: 42, orig_size: 28, trans_color: '#FFD700', orig_color: '#D3D3D3', trans_bottom_margin: 30, orig_bottom_margin: 0 },
  { name: '霓虹字幕', trans_size: 48, orig_size: 32, trans_color: '#00FFFF', orig_color: '#FF69B4', trans_bottom_margin: 70, orig_bottom_margin: 15 },
  { name: '深色模式', trans_size: 44, orig_size: 30, trans_color: '#E0E0E0', orig_color: '#888888', trans_bottom_margin: 50, orig_bottom_margin: 8 },
]
function applyPreset(p: any) {
  for (const k of ['trans_size','orig_size','trans_color','orig_color','orig_bottom_margin','trans_bottom_margin']) {
    if (p[k] !== undefined) cfg.value[k] = p[k]
  }
}

// ===== 滚轮 =====
function onSizeWheel(e: WheelEvent, field: string) {
  const v = (cfg.value[field] || 0) + (e.deltaY > 0 ? -1 : 1)
  if (v >= 20 && v <= 100) cfg.value[field] = v
}
function onOrigMarginWheel(e: WheelEvent) {
  const cur = cfg.value.orig_bottom_margin ?? 40
  const v = cur + (e.deltaY > 0 ? -5 : 5)
  if (v >= 0 && v <= 200) cfg.value.orig_bottom_margin = v
}
function onTransMarginWheel(e: WheelEvent) {
  const cur = cfg.value.trans_bottom_margin ?? 10
  const v = cur + (e.deltaY > 0 ? -5 : 5)
  if (v >= 0 && v <= 200) cfg.value.trans_bottom_margin = v
}
function onStrokeWheel(e: WheelEvent, field: string) {
  let v = (cfg.value[field] || 0) + (e.deltaY > 0 ? -0.5 : 0.5)
  v = Math.round(v * 10) / 10
  if (v >= 0.5 && v <= 5) cfg.value[field] = v
}

// ===== 预览计算（独立底边距 + 绝对定位，所见即所得）=====
const previewRatio = computed(() => {
  // 预览区缩放：16:9 容器，模拟 1920x1080 → 预览区宽度 ~700px，高度 ~394px，scale = 394/1080 ≈ 0.365
  const previewScale = 0.365

  function makeStyle(font: string, size: number, color: string, outline: number, outlineColor: string, marginPx: number) {
    const px = Math.round(size * previewScale)
    const o = Math.max(outline * previewScale, 0.5)
    return {
      fontFamily: font || 'Microsoft YaHei',
      fontSize: `${Math.max(px, 9)}px`,
      color,
      textShadow: `-${o}px 0 ${outlineColor}, 0 ${o}px ${outlineColor}, ${o}px 0 ${outlineColor}, 0 -${o}px ${outlineColor}`,
      position: 'absolute' as const,
      bottom: `${marginPx}px`,
      left: '0',
      right: '0',
      textAlign: 'center' as const,
      lineHeight: '1.2',
      pointerEvents: 'none' as const,
    }
  }

  // swap=false: 译文用 trans_margin, 原文用 orig_margin
  // swap=true:  译文用 orig_margin, 原文用 trans_margin
  const tMargin = swapped.value ? (cfg.value.orig_bottom_margin ?? 40) : (cfg.value.trans_bottom_margin ?? 10)
  const oMargin = swapped.value ? (cfg.value.trans_bottom_margin ?? 10) : (cfg.value.orig_bottom_margin ?? 40)

  const tFont = cfg.value.trans_font || 'Microsoft YaHei'
  const oFont = cfg.value.orig_font || 'Microsoft YaHei'
  const tSize = cfg.value.trans_size ?? 45
  const oSize = cfg.value.orig_size ?? 30
  const tColor = cfg.value.trans_color || '#FFFFFF'
  const oColor = cfg.value.orig_color || '#CCCCCC'
  const tOutline = cfg.value.trans_outline_size ?? 2
  const oOutline = cfg.value.orig_outline_size ?? 1.5
  const tOutlineColor = cfg.value.trans_outline_color || '#000000'
  const oOutlineColor = cfg.value.orig_outline_color || '#000000'

  const tMarginPx = Math.round(tMargin * previewScale)
  const oMarginPx = Math.round(oMargin * previewScale)

  return {
    tMargin, oMargin,
    tMarginPx, oMarginPx,
    tLabel: '译文', oLabel: '原文',
    transStyle: makeStyle(tFont, tSize, tColor, tOutline, tOutlineColor, tMarginPx),
    origStyle: makeStyle(oFont, oSize, oColor, oOutline, oOutlineColor, oMarginPx),
    transHigher: tMarginPx > oMarginPx,
    origHigher: oMarginPx > tMarginPx,
    overlapping: Math.abs(tMarginPx - oMarginPx) < 1,
  }
})

function save() {
  emit('save', {
    ...cfg.value,
    mode: displayMode.value,
    swap_order: swapped.value,
  })
}
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
    <div class="w-[1160px] max-h-[92vh] flex flex-col bg-background border border-primary/30 sao-hud overflow-hidden">
      <div class="corner-bl"></div><div class="corner-br"></div>

      <!-- 头部 -->
      <div class="h-10 flex items-center justify-between px-4 border-b border-primary/10 bg-surface/50 shrink-0">
        <span class="text-[10px] font-semibold tracking-wider text-accent">🎨 字幕样式设置</span>
        <button @click="emit('close')" class="text-text-dim/40 hover:text-danger text-sm transition-colors">✕</button>
      </div>

      <!-- 主体：左右分栏 -->
      <div class="flex-1 flex overflow-hidden min-h-0">

        <!-- ====== 左侧：设置面板（可滚动） ====== -->
        <div class="w-[520px] shrink-0 overflow-y-auto p-4 space-y-3 border-r border-primary/10">

          <!-- 预设 -->
          <div>
            <div class="text-[9px] text-text-dim/40 tracking-wider mb-1.5">🔖 快速预设</div>
            <div class="flex flex-wrap gap-1">
              <button v-for="p in presets" :key="p.name" @click="applyPreset(p)"
                class="px-2 py-0.5 text-[9px] border border-primary/20 text-text-dim/70 hover:text-text-primary hover:border-primary/50 transition-all">{{ p.name }}</button>
            </div>
          </div>

          <!-- 译文行 / 原文行 -->
          <div class="grid grid-cols-2 gap-3">
            <!-- 译文 -->
            <div class="border border-primary/10 p-2.5">
              <div class="flex items-center justify-between mb-2 pb-1 border-b border-primary/10">
                <span class="text-[9px] text-accent/60 tracking-wider">译文行</span>
                <span class="text-[7px] bg-accent/10 text-accent/60 px-1 py-0.5">距底 {{ cfg.trans_bottom_margin ?? 10 }}px</span>
              </div>
              <div class="space-y-2 text-[10px]">
                <!-- 字体 -->
                <div>
                  <span class="text-text-dim/60 block mb-0.5">字体</span>
                  <select v-if="!transFontCustom" v-model="cfg.trans_font"
                    class="w-full bg-background/80 border border-primary/30 px-1 py-0.5 text-[10px] text-text-primary outline-none">
                    <option v-if="!fontsLoaded" value="">加载中...</option>
                    <option v-for="f in fontOptions" :key="f" :value="f">{{ f }}</option>
                  </select>
                  <div v-else class="flex gap-1">
                    <input v-model="cfg.trans_font"
                      class="flex-1 bg-background/80 border border-primary/30 px-1 py-0.5 text-[10px] text-text-primary outline-none" placeholder="输入字体名..." />
                    <button @click="transFontCustom = false; cfg.trans_font = fontOptions[0] || 'Microsoft YaHei'" class="text-[8px] px-1 border border-primary/20 text-text-dim/40 hover:text-text-primary">选择</button>
                  </div>
                  <button @click="transFontCustom = !transFontCustom" class="text-[8px] text-text-dim/30 hover:text-accent mt-0.5">
                    {{ transFontCustom ? '从列表选择' : '手动输入' }}
                  </button>
                </div>
                <!-- 字号 -->
                <div>
                  <div class="flex items-center justify-between">
                    <span class="text-text-dim/60">字号</span>
                    <div class="flex items-center gap-0.5">
                      <button @click="cfg.trans_size = Math.max(20, cfg.trans_size - 1)" class="text-[9px] px-1 py-0.5 border border-primary/20 text-text-dim/60">−</button>
                      <input v-model.number="cfg.trans_size" type="number" min="20" max="100"
                        @wheel.prevent="onSizeWheel($event, 'trans_size')"
                        class="w-10 text-center bg-background/80 border border-primary/30 px-1 py-0.5 text-[10px] text-text-primary outline-none" />
                      <button @click="cfg.trans_size = Math.min(100, cfg.trans_size + 1)" class="text-[9px] px-1 py-0.5 border border-primary/20 text-text-dim/60">+</button>
                    </div>
                  </div>
                </div>
                <!-- 描边粗细 -->
                <div class="flex items-center justify-between">
                  <span class="text-text-dim/60">描边</span>
                  <input v-model.number="cfg.trans_outline_size" type="number" min="0.5" max="5" step="0.5"
                    @wheel.prevent="onStrokeWheel($event, 'trans_outline_size')"
                    class="w-10 text-center bg-background/80 border border-primary/30 px-1 py-0.5 text-[10px] text-text-primary outline-none" />
                </div>
                <!-- 颜色 -->
                <div>
                  <div class="flex items-center gap-1.5 mb-1">
                    <span class="text-text-dim/60 text-[9px]">颜色</span>
                    <input v-model="cfg.trans_color" type="color" class="w-6 h-5 border-0 cursor-pointer p-0 bg-transparent" />
                    <span class="text-[8px] font-mono text-text-dim/50">{{ cfg.trans_color }}</span>
                    <button @click="cfg.trans_color = '#FFFFFF'" class="text-[8px] text-text-dim/40 hover:text-accent ml-auto">复位</button>
                  </div>
                  <div class="flex flex-wrap gap-0.5">
                    <button v-for="c in colorPresets" :key="c" @click="cfg.trans_color = c"
                      class="w-3.5 h-3.5 rounded-full border border-white/20 cursor-pointer"
                      :style="{ backgroundColor: c }"
                      :class="cfg.trans_color === c ? 'ring-1 ring-accent' : ''"></button>
                  </div>
                </div>
                <!-- 描边颜色 -->
                <div class="flex items-center gap-1.5">
                  <span class="text-text-dim/60 text-[9px]">描边色</span>
                  <input v-model="cfg.trans_outline_color" type="color" class="w-6 h-5 border-0 cursor-pointer p-0 bg-transparent" />
                  <span class="text-[8px] font-mono text-text-dim/50">{{ cfg.trans_outline_color }}</span>
                </div>
              </div>
            </div>

            <!-- 原文 -->
            <div class="border border-primary/10 p-2.5">
              <div class="flex items-center justify-between mb-2 pb-1 border-b border-primary/10">
                <span class="text-[9px] text-text-dim/60 tracking-wider">原文行</span>
                <span class="text-[7px] bg-primary/10 text-text-dim/60 px-1 py-0.5">距底 {{ cfg.orig_bottom_margin ?? 40 }}px</span>
              </div>
              <div class="space-y-2 text-[10px]">
                <!-- 字体 -->
                <div>
                  <span class="text-text-dim/60 block mb-0.5">字体</span>
                  <select v-if="!origFontCustom" v-model="cfg.orig_font"
                    class="w-full bg-background/80 border border-primary/30 px-1 py-0.5 text-[10px] text-text-primary outline-none">
                    <option v-if="!fontsLoaded" value="">加载中...</option>
                    <option v-for="f in fontOptions" :key="f" :value="f">{{ f }}</option>
                  </select>
                  <div v-else class="flex gap-1">
                    <input v-model="cfg.orig_font"
                      class="flex-1 bg-background/80 border border-primary/30 px-1 py-0.5 text-[10px] text-text-primary outline-none" placeholder="输入字体名..." />
                    <button @click="origFontCustom = false; cfg.orig_font = fontOptions[0] || 'Microsoft YaHei'" class="text-[8px] px-1 border border-primary/20 text-text-dim/40 hover:text-text-primary">选择</button>
                  </div>
                  <button @click="origFontCustom = !origFontCustom" class="text-[8px] text-text-dim/30 hover:text-accent mt-0.5">
                    {{ origFontCustom ? '从列表选择' : '手动输入' }}
                  </button>
                </div>
                <!-- 字号 -->
                <div>
                  <div class="flex items-center justify-between">
                    <span class="text-text-dim/60">字号</span>
                    <div class="flex items-center gap-0.5">
                      <button @click="cfg.orig_size = Math.max(20, cfg.orig_size - 1)" class="text-[9px] px-1 py-0.5 border border-primary/20 text-text-dim/60">−</button>
                      <input v-model.number="cfg.orig_size" type="number" min="20" max="80"
                        @wheel.prevent="onSizeWheel($event, 'orig_size')"
                        class="w-10 text-center bg-background/80 border border-primary/30 px-1 py-0.5 text-[10px] text-text-primary outline-none" />
                      <button @click="cfg.orig_size = Math.min(80, cfg.orig_size + 1)" class="text-[9px] px-1 py-0.5 border border-primary/20 text-text-dim/60">+</button>
                    </div>
                  </div>
                </div>
                <!-- 描边粗细 -->
                <div class="flex items-center justify-between">
                  <span class="text-text-dim/60">描边</span>
                  <input v-model.number="cfg.orig_outline_size" type="number" min="0.5" max="5" step="0.5"
                    @wheel.prevent="onStrokeWheel($event, 'orig_outline_size')"
                    class="w-10 text-center bg-background/80 border border-primary/30 px-1 py-0.5 text-[10px] text-text-primary outline-none" />
                </div>
                <!-- 颜色 -->
                <div>
                  <div class="flex items-center gap-1.5 mb-1">
                    <span class="text-text-dim/60 text-[9px]">颜色</span>
                    <input v-model="cfg.orig_color" type="color" class="w-6 h-5 border-0 cursor-pointer p-0 bg-transparent" />
                    <span class="text-[8px] font-mono text-text-dim/50">{{ cfg.orig_color }}</span>
                    <button @click="cfg.orig_color = '#CCCCCC'" class="text-[8px] text-text-dim/40 hover:text-accent ml-auto">复位</button>
                  </div>
                  <div class="flex flex-wrap gap-0.5">
                    <button v-for="c in colorPresets" :key="c" @click="cfg.orig_color = c"
                      class="w-3.5 h-3.5 rounded-full border border-white/20 cursor-pointer"
                      :style="{ backgroundColor: c }"
                      :class="cfg.orig_color === c ? 'ring-1 ring-accent' : ''"></button>
                  </div>
                </div>
                <!-- 描边颜色 -->
                <div class="flex items-center gap-1.5">
                  <span class="text-text-dim/60 text-[9px]">描边色</span>
                  <input v-model="cfg.orig_outline_color" type="color" class="w-6 h-5 border-0 cursor-pointer p-0 bg-transparent" />
                  <span class="text-[8px] font-mono text-text-dim/50">{{ cfg.orig_outline_color }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 位置（独立底边距） -->
          <div class="border border-accent/20 p-2.5 bg-accent/[0.02]">
            <div class="text-[9px] text-accent-dim/60 tracking-wider mb-2 pb-1 border-b border-primary/10">📏 底边距（距屏幕底部）</div>
            <div class="space-y-2">
              <!-- 译文底边距 -->
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-1.5">
                  <span class="w-3 h-3 rounded-full border border-accent/50 bg-accent/20 inline-block"></span>
                  <span class="text-text-dim/60">译文底边距</span>
                </div>
                <input v-model.number="cfg.trans_bottom_margin" type="number" min="0" max="200"
                  @wheel.prevent="onTransMarginWheel"
                  class="w-14 text-center bg-background/80 border border-accent/30 px-1 py-0.5 text-[10px] text-text-primary outline-none" />
              </div>
              <!-- 原文底边距 -->
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-1.5">
                  <span class="w-3 h-3 rounded-full border border-primary/50 bg-primary/20 inline-block"></span>
                  <span class="text-text-dim/60">原文底边距</span>
                </div>
                <input v-model.number="cfg.orig_bottom_margin" type="number" min="0" max="200"
                  @wheel.prevent="onOrigMarginWheel"
                  class="w-14 text-center bg-background/80 border border-primary/30 px-1 py-0.5 text-[10px] text-text-primary outline-none" />
              </div>
              <span class="text-[7px] text-text-dim/30">0=触底 · 允许重叠 · 滚轮 ±5</span>
            </div>
          </div>

          <!-- 显示模式 + 互换 -->
          <div class="flex items-center justify-between border border-primary/10 p-2.5">
            <div>
              <span class="text-[9px] text-text-dim/40 tracking-wider mr-2">📋 显示</span>
              <label v-for="opt in [{v:'bilingual',l:'双语'},{v:'trans_only',l:'仅译文'},{v:'orig_only',l:'仅原文'}]" :key="opt.v"
                class="inline-flex items-center gap-1 text-[10px] text-text-dim/70 cursor-pointer mr-3"
                :class="displayMode === opt.v ? 'text-accent' : ''">
                <input type="radio" :value="opt.v" v-model="displayMode" class="accent-accent" />
                {{ opt.l }}
              </label>
            </div>
            <button @click="swapped = !swapped"
              class="px-2.5 py-1 text-[9px] border transition-all tracking-wider"
              :class="swapped ? 'border-accent/50 text-accent bg-accent/10' : 'border-primary/30 text-text-dim/70 hover:text-text-primary'">
              ⇅ {{ swapped ? '交换位置' : '正常位置' }}
            </button>
          </div>

          <!-- 预览背景 -->
          <div class="border border-primary/10 p-2.5">
            <span class="text-[9px] text-text-dim/40 mr-2">🖼️ 预览背景</span>
            <button @click="selectBgFile" class="px-2 py-0.5 text-[9px] border border-primary/30 text-primary/70 hover:text-primary transition-all mr-1">选择</button>
            <button v-if="previewBg" @click="clearBg" class="px-2 py-0.5 text-[9px] border border-danger/30 text-danger/70 hover:text-danger transition-all">清除</button>
          </div>

        </div>

        <!-- ====== 右侧：实时预览（固定） ====== -->
        <div class="flex-1 flex flex-col p-4 min-w-0">
          <div class="text-[8px] text-text-dim/40 tracking-wider mb-2">👁️ 实时预览（16:9）</div>
          <div class="relative w-full rounded overflow-hidden border border-primary/20" style="aspect-ratio: 16/9; background: #000;">
            <div class="absolute inset-0 flex flex-col justify-end"
              :style="{
                background: previewBg ? `url(${previewBg}) center/cover no-repeat` : 'linear-gradient(135deg, #0b0813 0%, #1a0a2e 50%, #0b0813 100%)',
              }">
              <div v-if="previewBg" class="absolute inset-0 bg-black/50"></div>

              <!-- 字幕区域 (绝对定位，独立底边距) -->
              <div class="relative z-10 w-full h-full">

                <!-- 双语模式：两条线独立定位 -->
                <template v-if="displayMode === 'bilingual'">
                  <p :style="previewRatio.transStyle">
                    {{ previewRatio.tLabel }} Sample Text 示例
                  </p>
                  <p :style="previewRatio.origStyle">
                    {{ previewRatio.oLabel }} Original Text 原文
                  </p>
                </template>

                <!-- 仅译文 -->
                <p v-else-if="displayMode === 'trans_only'" :style="previewRatio.transStyle">
                  译文 Only — Sample Text
                </p>

                <!-- 仅原文 -->
                <p v-else-if="displayMode === 'orig_only'" :style="previewRatio.origStyle">
                  原文 Only — Original Text
                </p>
              </div>

              <!-- 译文底边距参考线 -->
              <div class="absolute left-0 right-0 h-px bg-accent/50"
                :style="{ bottom: previewRatio.tMarginPx + 'px' }">
                <span class="absolute -top-3 right-2 text-[7px] text-accent/50 font-mono">译文 {{ previewRatio.tMargin }}px</span>
              </div>
              <!-- 原文底边距参考线 -->
              <div class="absolute left-0 right-0 h-px bg-white/50"
                :style="{ bottom: previewRatio.oMarginPx + 'px' }">
                <span class="absolute -top-3 left-2 text-[7px] text-white/40 font-mono">原文 {{ previewRatio.oMargin }}px</span>
              </div>

              <!-- 信息角标 -->
              <div class="absolute top-2 left-3 text-[7px] text-white/15 font-mono tracking-wider select-none">
                {{ previewBg ? '背景图' : '暗色背景' }}
                · {{ previewRatio.transHigher ? '译文更高' : previewRatio.origHigher ? '原文更高' : previewRatio.overlapping ? '两行重叠' : '' }}
              </div>
            </div>
          </div>

          <!-- 底部提示 -->
          <div class="flex items-center justify-between mt-2 text-[8px] text-text-dim/30">
            <span>字号 · 颜色 · 位置 实时反映</span>
            <span>译文距底 {{ previewRatio.tMargin }}px | 原文距底 {{ previewRatio.oMargin }}px</span>
          </div>
        </div>
      </div>

      <!-- 底部按钮 -->
      <div class="h-10 flex items-center justify-end gap-2 px-4 border-t border-primary/10 bg-surface/30 shrink-0">
        <button @click="emit('close')" class="px-4 py-1.5 text-[9px] tracking-wider text-text-dim/60 hover:text-text-primary border border-primary/20 transition-all">取消</button>
        <button @click="save" class="px-5 py-1.5 text-[9px] tracking-wider font-semibold border border-accent/40 text-accent hover:bg-accent/10 hover:shadow-[0_0_12px_rgba(0,245,212,0.15)] transition-all">✓ 应用样式</button>
      </div>
    </div>
  </div>
</template>
