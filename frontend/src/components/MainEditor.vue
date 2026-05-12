<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import StyleDialog from './StyleDialog.vue'

const apiBase = 'http://127.0.0.1:8712'

// ===== 类型 =====
interface Subtitle {
  id: string
  start_time: number
  end_time: number
  original_text: string
  reference_text: string
  translated_text: string
}

// ===== 项目列表 =====
interface Project {
  path: string
  manager: { subtitles: Subtitle[] }
}
const projects = ref<Record<string, Project>>({})
const currentVideoPath = ref('')
const videoQueue = ref<string[]>([])
const processing = ref(false)

// ===== 字幕数据 =====
const subtitles = ref<Subtitle[]>([])
const selectedRows = ref<Set<number>>(new Set())
const highlightId = ref<string | null>(null)

// ===== 引擎状态 =====
const engineStatus = ref('starting')
const gpuInfo = ref('')
const error = ref('')
const statusMsg = ref('就绪')

// ===== 打赏功能 =====
const donateThanks = ref(false)
let donateTimer: ReturnType<typeof setTimeout> | null = null
async function openDonate() {
  const url = 'https://www.ifdian.net/a/jinshui1987?utm_source=copylink&utm_medium=link'
  try {
    const { open } = await import('@tauri-apps/plugin-shell')
    await open(url)
  } catch {
    // 浏览器模式回退
    window.open(url, '_blank')
  }
  donateThanks.value = true
  if (donateTimer) clearTimeout(donateTimer)
  donateTimer = setTimeout(() => { donateThanks.value = false }, 10 * 60 * 1000)
}

// ===== 拖放 =====
const dragging = ref(false)
const isTauriEnv = ref(false)
let dragCounter = 0

// ===== 翻译引擎配置 =====
const engineType = ref('deepseek')
const targetLang = ref('英文')
const apiKey = ref('')
const apiBaseUrl = ref('https://api.deepseek.com')
const modelName = ref('deepseek-chat')
const glossary = ref('')
const maxChars = ref(25)

// ===== 样式设置 =====
const showStyleDialog = ref(false)
const styleConfig = ref({
  mode: 'bilingual',
  swap_order: false,  // false=正常(译文用trans_margin,原文用orig_margin), true=交换
  trans_font: 'Microsoft YaHei', trans_size: 45, trans_color: '#FFFFFF',
  trans_outline_color: '#000000', trans_outline_size: 2,
  orig_font: 'Microsoft YaHei', orig_size: 30, orig_color: '#CCCCCC',
  orig_outline_color: '#000000', orig_outline_size: 1.5,
  trans_bottom_margin: 60,  // 译文距屏幕底边
  orig_bottom_margin: 10,   // 原文距屏幕底边
  preview_bg: '',
})

// ===== ASR 进度 =====
const asrProgress = ref(0)
const asrProgressText = ref('')

// ===== Toast 通知 =====
const toast = ref<{ show: boolean; message: string; path: string }>({ show: false, message: '', path: '' })
let toastTimer: ReturnType<typeof setTimeout> | null = null
function showToast(message: string, path: string = '') {
  if (toastTimer) clearTimeout(toastTimer)
  toast.value = { show: true, message, path }
  toastTimer = setTimeout(() => { toast.value.show = false }, 6000)
}
function closeToast() {
  if (toastTimer) clearTimeout(toastTimer)
  toast.value.show = false
}

// ===== 隐藏的文件输入 =====
const fileInputRef = ref<HTMLInputElement | null>(null)
function triggerFilePicker() {
  fileInputRef.value?.click()
}
async function onFilesSelected(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files) {
    for (const f of input.files) {
      if (!/\.(mp4|mkv|mov|avi)$/i.test(f.name)) continue
      const nativePath = (f as any).path || (f as any).webkitRelativePath
      if (nativePath) {
        addToProject(nativePath)
      } else {
        // 浏览器模式 → 上传到后端，用原始文件名做 key
        const uploaded = await uploadFile(f)
        if (uploaded) addToProject(uploaded, f.name)
      }
    }
    processNextInQueue()
  }
  input.value = ''
}

// ===== 浏览器模式上传文件到后端 =====
async function uploadFile(file: File): Promise<string | null> {
  const formData = new FormData()
  formData.append('file', file)
  try {
    const res = await fetch(`${apiBase}/api/upload`, { method: 'POST', body: formData })
    const data = await res.json()
    if (data.success) {
      statusMsg.value = `📤 已上传: ${file.name}`
      return data.path
    }
    error.value = `❌ 上传失败: ${data.message}`
  } catch {
    error.value = `❌ 上传失败：后端服务未连接，请先启动 API 服务`
  }
  return null
}

// ===== 活跃行编辑 =====
const editingRow = ref<number | null>(null)
const editingCol = ref<number | null>(null)
const editText = ref('')

// ===== 当前视频文件列表 =====
const currentSubtitles = computed(() => {
  if (currentVideoPath.value && projects.value[currentVideoPath.value]) {
    return projects.value[currentVideoPath.value].manager.subtitles
  }
  return subtitles.value
})

// ===== 选中的项目路径 =====
const projectList = computed(() => Object.keys(projects.value))

function formatTime(sec: number): string {
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${pad2(Math.floor(s))}.${pad3(Math.floor((s - Math.floor(s)) * 1000))}`
}
function pad2(n: number) { return String(n).padStart(2, '0') }
function pad3(n: number) { return String(n).padStart(3, '0') }

// ===== 引擎管理 =====
onMounted(async () => {
  subtitles.value = [
    { id: 's1', start_time: 0.5, end_time: 3.2, original_text: 'Welcome to Jinshui Subtitle Pro.', reference_text: '', translated_text: '欢迎使用金水字幕 Pro。' },
    { id: 's2', start_time: 4.0, end_time: 7.8, original_text: 'This is a professional AI-powered subtitling tool.', reference_text: '', translated_text: '这是一款专业的 AI 驱动字幕工具。' },
    { id: 's3', start_time: 8.5, end_time: 12.1, original_text: 'It supports automatic speech recognition and translation.', reference_text: '', translated_text: '它支持自动语音识别和翻译。' },
    { id: 's4', start_time: 13.0, end_time: 16.5, original_text: 'Simply drag and drop your video file to get started.', reference_text: '', translated_text: '只需拖放视频文件即可开始使用。' },
    { id: 's5', start_time: 17.2, end_time: 21.0, original_text: 'The AI engine will process audio and generate subtitles.', reference_text: '', translated_text: 'AI 引擎将处理音频并生成字幕。' },
    { id: 's6', start_time: 22.0, end_time: 25.8, original_text: 'You can edit, merge, split, or delete any subtitle entry.', reference_text: '', translated_text: '您可以编辑、合并、拆分或删除任何字幕条目。' },
    { id: 's7', start_time: 26.5, end_time: 30.2, original_text: 'Export your work in SRT or ASS format with custom styles.', reference_text: '', translated_text: '以 SRT 或 ASS 格式导出您的工作成果。' },
    { id: 's8', start_time: 31.0, end_time: 34.5, original_text: 'This tool is based on the QwenASR 1.7B model, licensed under Apache 2.0.', reference_text: '', translated_text: '本工具基于 QwenASR 1.7B 模型，遵循 Apache 2.0 协议。' },
    { id: 's9', start_time: 35.2, end_time: 38.0, original_text: 'Free and open to all users.', reference_text: '', translated_text: '免费向所有用户开放。' },
    { id: 's10', start_time: 39.0, end_time: 42.0, original_text: 'Made with love by B站 金水1987.', reference_text: '', translated_text: '由 B站 金水1987 用心打造。' },
  ]

  // 尝试设置 Tauri 原生拖放（桌面端）
  try {
    const { getCurrentWebview } = await import('@tauri-apps/api/webview')
    await getCurrentWebview().onDragDropEvent((event) => {
      if (event.payload.type === 'enter' || event.payload.type === 'over') {
        dragCounter = 0
        dragging.value = true
      } else if (event.payload.type === 'leave') {
        dragging.value = false
      } else if (event.payload.type === 'drop') {
        dragging.value = false
        for (const path of event.payload.paths) {
          if (/\.(mp4|mkv|mov|avi)$/i.test(path)) {
            addToProject(path)
          }
        }
        processNextInQueue()
      }
    })
    isTauriEnv.value = true
  } catch { /* 浏览器模式，使用 HTML5 拖放 */ }

  setTimeout(waitForEngine, 500)
})

async function waitForEngine() {
  for (let i = 0; i < 30; i++) {
    try {
      const res = await fetch(`${apiBase}/api/health`)
      const data = await res.json()
      if (data.status === 'ok') {
        engineStatus.value = 'ready'
        gpuInfo.value = data.gpu_available ? 'GPU 就绪' : 'CPU 模式'
        if (!data.models_ready) error.value = '⚠️ 未找到模型文件，请检查 models/ 目录'
        return
      }
    } catch { /* wait */ }
    await new Promise(r => setTimeout(r, 1000))
  }
  statusMsg.value = '浏览器预览模式 — 假数据显示中'
  engineStatus.value = 'preview'
}

// ===== 拖放视频（支持批量 + 浏览器/桌面双模式）=====
function onDragOver(e: DragEvent) {
  if (isTauriEnv.value) return
  e.preventDefault()
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy'
  dragging.value = true
}
function onDragEnter(e: DragEvent) {
  if (isTauriEnv.value) return
  e.preventDefault()
  dragCounter++
  dragging.value = true
}
function onDragLeave(_e: DragEvent) {
  if (isTauriEnv.value) return
  dragCounter--
  if (dragCounter <= 0) {
    dragCounter = 0
    dragging.value = false
  }
}
async function onDrop(e: DragEvent) {
  if (isTauriEnv.value) return
  e.preventDefault()
  dragCounter = 0
  dragging.value = false
  if (e.dataTransfer?.files) {
    for (const f of e.dataTransfer.files) {
      if (!/\.(mp4|mkv|mov|avi)$/i.test(f.name)) continue
      // 浏览器模式：上传到后端
      const uploaded = await uploadFile(f)
      if (uploaded) addToProject(uploaded)
    }
    processNextInQueue()
  }
}

async function importVideo() {
  try {
    const { open } = await import('@tauri-apps/plugin-dialog')
    const selected = await open({
      multiple: true,
      filters: [{ name: 'Video', extensions: ['mp4', 'mkv', 'mov', 'avi'] }]
    })
    if (selected) {
      const paths = Array.isArray(selected) ? selected : [selected]
      for (const p of paths) addToProject(p)
      processNextInQueue()
    }
  } catch {
    triggerFilePicker()
  }
}

function addToProject(filePath: string, displayName?: string) {
  if (!projects.value[filePath]) {
    projects.value[filePath] = {
      path: filePath,
      manager: { subtitles: [] as Subtitle[] }
    }
    if (displayName) {
      ;(projects.value[filePath] as any)._displayName = displayName
    }
  }
  if (!currentVideoPath.value) {
    currentVideoPath.value = filePath
  }
  if (!videoQueue.value.includes(filePath)) {
    videoQueue.value.push(filePath)
  }
}

function removeProject(path: string) {
  delete projects.value[path]
  videoQueue.value = videoQueue.value.filter(p => p !== path)
  if (currentVideoPath.value === path) {
    const remaining = Object.keys(projects.value)
    currentVideoPath.value = remaining.length > 0 ? remaining[0] : ''
    if (currentVideoPath.value) {
      const p = projects.value[currentVideoPath.value]
      subtitles.value = p.manager.subtitles.length > 0 ? p.manager.subtitles : []
    } else {
      subtitles.value = []
    }
  }
}

function selectProject(path: string) {
  currentVideoPath.value = path
  if (projects.value[path]) {
    subtitles.value = projects.value[path].manager.subtitles
  }
  statusMsg.value = `已切换至: ${(projects.value[path] as any)._displayName || path.split('\\').pop()?.split('/').pop()}`
}

async function processNextInQueue() {
  if (processing.value || videoQueue.value.length === 0) return
  processing.value = true
  asrProgress.value = 0
  asrProgressText.value = '正在打轴...'
  const path = videoQueue.value.shift()!
  statusMsg.value = `🎯 正在打轴: ${path.split('\\').pop()?.split('/').pop()}`
  error.value = ''

  try {
    const res = await fetch(`${apiBase}/api/asr`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ video_path: path, max_chars: maxChars.value }),
    })
    const data = await res.json()
    if (data.success) {
      if (projects.value[path]) {
        projects.value[path].manager.subtitles = data.subtitles
      }
      if (currentVideoPath.value === path) {
        subtitles.value = data.subtitles
      }
      asrProgress.value = 100
      asrProgressText.value = '打轴完成'
      statusMsg.value = `✅ 打轴完成: ${data.subtitles.length} 条字幕`
      setTimeout(() => { asrProgress.value = 0 }, 2000)
    } else {
      error.value = `❌ 识别失败: ${data.message}`
      asrProgress.value = 0
    }
  } catch (e) {
    statusMsg.value = '浏览器预览模式 — 使用假数据'
    subtitles.value = [
      { id: 's1', start_time: 0.5, end_time: 3.2, original_text: 'Welcome to Jinshui Subtitle Pro.', reference_text: '', translated_text: '欢迎使用金水字幕 Pro。' },
      { id: 's2', start_time: 4.0, end_time: 7.8, original_text: 'This is a professional AI-powered subtitling tool.', reference_text: '', translated_text: '这是一款专业的 AI 驱动字幕工具。' },
      { id: 's3', start_time: 8.5, end_time: 12.1, original_text: 'It supports automatic speech recognition and translation.', reference_text: '', translated_text: '它支持自动语音识别和翻译。' },
      { id: 's4', start_time: 13.0, end_time: 16.5, original_text: 'Simply drag and drop your video file to get started.', reference_text: '', translated_text: '只需拖放视频文件即可开始使用。' },
      { id: 's5', start_time: 17.2, end_time: 21.0, original_text: 'The AI engine will process audio and generate subtitles.', reference_text: '', translated_text: 'AI 引擎将处理音频并生成字幕。' },
      { id: 's6', start_time: 22.0, end_time: 25.8, original_text: 'You can edit, merge, split, or delete any subtitle entry.', reference_text: '', translated_text: '您可以编辑、合并、拆分或删除任何字幕条目。' },
      { id: 's7', start_time: 26.5, end_time: 30.2, original_text: 'Export your work in SRT or ASS format with custom styles.', reference_text: '', translated_text: '以 SRT 或 ASS 格式导出您的工作成果。' },
      { id: 's8', start_time: 31.0, end_time: 34.5, original_text: 'This tool is based on the QwenASR 1.7B model, licensed under Apache 2.0.', reference_text: '', translated_text: '本工具基于 QwenASR 1.7B 模型，遵循 Apache 2.0 协议。' },
      { id: 's9', start_time: 35.2, end_time: 38.0, original_text: 'Free and open to all users.', reference_text: '', translated_text: '免费向所有用户开放。' },
      { id: 's10', start_time: 39.0, end_time: 42.0, original_text: 'Made with love by B站 金水1987.', reference_text: '', translated_text: '由 B站 金水1987 用心打造。' },
    ]
    asrProgress.value = 100
    asrProgressText.value = '预览数据就绪'
    setTimeout(() => { asrProgress.value = 0 }, 1500)
  }
  processing.value = false
  processNextInQueue()
}

// ===== 表格操作 =====
function toggleRow(idx: number) {
  const s = new Set(selectedRows.value)
  s.has(idx) ? s.delete(idx) : s.add(idx)
  selectedRows.value = s
}

function startEdit(row: number, col: number, text: string) {
  editingRow.value = row
  editingCol.value = col
  editText.value = text
}

function saveEdit() {
  if (editingRow.value === null || editingCol.value === null) return
  const sub = currentSubtitles.value[editingRow.value]
  if (!sub) return
  if (editingCol.value === 2) sub.original_text = editText.value
  else if (editingCol.value === 3) sub.translated_text = editText.value
  editingRow.value = null
  editingCol.value = null
}

function deleteSub(idx: number) {
  currentSubtitles.value.splice(idx, 1)
  // 重建 selectedRows，修复删除行后索引偏移
  const updated = new Set<number>()
  for (const i of selectedRows.value) {
    if (i < idx) updated.add(i)
    else if (i > idx) updated.add(i - 1)
  }
  selectedRows.value = updated
}

function insertAfter(idx: number) {
  const sub = currentSubtitles.value[idx]
  const newSub: Subtitle = {
    id: `new-${Date.now()}`,
    start_time: sub.end_time + 0.01,
    end_time: sub.end_time + 2.01,
    original_text: '[新建字幕]',
    reference_text: '',
    translated_text: '[New Subtitle]',
  }
  currentSubtitles.value.splice(idx + 1, 0, newSub)
  // 重建 selectedRows，修复插入行后索引偏移
  const updated = new Set<number>()
  for (const i of selectedRows.value) {
    updated.add(i > idx ? i + 1 : i)
  }
  selectedRows.value = updated
}

function mergeSelected() {
  const rows = Array.from(selectedRows.value).sort((a, b) => a - b)
  if (rows.length < 2) return
  const subs = rows.map(i => currentSubtitles.value[i])
  const first = subs[0]
  for (let i = 1; i < subs.length; i++) {
    first.original_text += ' ' + subs[i].original_text
    if (first.translated_text && subs[i].translated_text) {
      first.translated_text += ' ' + subs[i].translated_text
    } else if (subs[i].translated_text) {
      first.translated_text = subs[i].translated_text
    }
    first.end_time = Math.max(first.end_time, subs[i].end_time)
  }
  for (let i = rows.length - 1; i > 0; i--) {
    currentSubtitles.value.splice(rows[i], 1)
  }
  selectedRows.value = new Set()
  highlightId.value = first.id
}

// ===== 单句重译 =====
async function singleTranslate(sub: Subtitle) {
  if (!apiKey.value && engineType.value === 'deepseek') {
    error.value = '⚠️ 使用 DeepSeek 需要填写 API Key'
    return
  }
  try {
    const res = await fetch(`${apiBase}/api/translate/single`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: sub.original_text,
        api_key: apiKey.value,
        api_base: apiBaseUrl.value,
        model: modelName.value,
        target_lang: targetLang.value,
        engine_type: engineType.value,
      }),
    })
    const data = await res.json()
    if (data.success) {
      error.value = ''
      sub.translated_text = data.translated_text
      statusMsg.value = '✅ 单句重译完成'
    } else {
      error.value = `❌ 翻译失败: ${data.message}`
    }
  } catch (e) {
    sub.translated_text = `[模拟翻译] ${sub.original_text}`
    statusMsg.value = '✅ 单句重译完成（预览模式）'
  }
}

// ===== 批量翻译 =====
async function batchTranslate() {
  if (currentSubtitles.value.length === 0) return
  if (!apiKey.value && engineType.value === 'deepseek') {
    error.value = '⚠️ 使用 DeepSeek 需要填写 API Key'
    return
  }
  statusMsg.value = '🌐 正在批量翻译...'
  try {
    const subsForApi = currentSubtitles.value.map(s => ({
      id: s.id,
      start_time: s.start_time,
      end_time: s.end_time,
      original_text: s.original_text,
      reference_text: s.reference_text || s.original_text,
      translated_text: s.translated_text,
    }))
    const res = await fetch(`${apiBase}/api/translate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        subtitles: subsForApi,
        api_key: apiKey.value,
        api_base: apiBaseUrl.value,
        model: modelName.value,
        target_lang: targetLang.value,
        engine_type: engineType.value,
        glossary: glossary.value,
      }),
    })
    const data = await res.json()
    if (data.success) {
      error.value = ''
      for (const item of data.translated) {
        const sub = currentSubtitles.value.find(s => s.id === item.id)
        if (sub) sub.translated_text = item.translated_text
      }
      statusMsg.value = '✅ 批量翻译完成'
    } else {
      error.value = `❌ 翻译失败: ${data.message}`
    }
  } catch (e) {
    for (const sub of currentSubtitles.value) {
      sub.translated_text = `[模拟翻译] ${sub.original_text}`
    }
    statusMsg.value = '✅ 批量翻译完成（预览模式）'
  }
}

// ===== 润色原文 =====
async function batchOptimize() {
  if (currentSubtitles.value.length === 0) return
  if (!apiKey.value && engineType.value === 'deepseek') {
    error.value = '⚠️ 润色需要 DeepSeek API Key'
    return
  }
  statusMsg.value = '✨ 正在润色原文...'
  try {
    const subsForApi = currentSubtitles.value.map(s => ({
      id: s.id,
      start_time: s.start_time,
      end_time: s.end_time,
      original_text: s.original_text,
      reference_text: s.reference_text || s.original_text,
      translated_text: s.translated_text,
    }))
    const res = await fetch(`${apiBase}/api/optimize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        subtitles: subsForApi,
        api_key: apiKey.value,
        api_base: apiBaseUrl.value,
        model: modelName.value,
        engine_type: engineType.value,
        glossary: glossary.value,
        max_chars: maxChars.value,
      }),
    })
    const data = await res.json()
    if (data.success) {
      error.value = ''
      // 构建当前字幕 ID 集合
      const existingIds = new Set(currentSubtitles.value.map(s => s.id))
      for (const item of data.optimized) {
        const sub = currentSubtitles.value.find(s => s.id === item.id)
        if (sub) {
          sub.original_text = item.original_text
          if (item.start_time !== undefined) sub.start_time = item.start_time
          if (item.end_time !== undefined) sub.end_time = item.end_time
        } else if (!existingIds.has(item.id)) {
          // 拆分产生的新字幕条
          currentSubtitles.value.push({
            id: item.id,
            start_time: item.start_time || 0,
            end_time: item.end_time || 0,
            original_text: item.original_text || '',
            reference_text: item.original_text || '',
            translated_text: item.translated_text || '',
          })
        }
      }
      statusMsg.value = '✅ 润色完成'
    } else {
      error.value = `❌ 润色失败: ${data.message}`
    }
  } catch {
    statusMsg.value = '✅ 润色完成（预览模式）'
  }
}

// ===== 导出 =====
async function exportSRT() {
  if (currentSubtitles.value.length === 0) return
  const outPath = currentVideoPath.value
    ? currentVideoPath.value.replace(/\.[^.]+$/, '.srt')
    : 'output.srt'
  try {
    await fetch(`${apiBase}/api/export/srt`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        subtitles: currentSubtitles.value,
        mode: 'srt',
        output_path: outPath,
        style_config: { mode: styleConfig.value.mode },
      }),
    })
    statusMsg.value = `✅ SRT 导出成功: ${outPath}`
    showToast('✅ SRT 导出成功！', outPath)
  } catch {
    statusMsg.value = '✅ SRT 导出成功（预览模式）'
    showToast('✅ SRT 导出成功（预览模式）')
  }
}

async function exportASS() {
  if (currentSubtitles.value.length === 0) return
  const outPath = currentVideoPath.value
    ? currentVideoPath.value.replace(/\.[^.]+$/, '.ass')
    : 'output.ass'
  try {
    await fetch(`${apiBase}/api/export/ass`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        subtitles: currentSubtitles.value,
        mode: 'ass',
        output_path: outPath,
        style_config: {
          ...styleConfig.value,
          trans_font: styleConfig.value.trans_font,
          orig_font: styleConfig.value.orig_font,
        },
      }),
    })
    statusMsg.value = `✅ ASS 导出成功: ${outPath}`
    showToast('✅ ASS 导出成功！', outPath)
  } catch {
    statusMsg.value = '✅ ASS 导出成功（预览模式）'
    showToast('✅ ASS 导出成功（预览模式）')
  }
}

async function exportVideo() {
  if (currentSubtitles.value.length === 0 || !currentVideoPath.value) return
  const baseName = currentVideoPath.value.replace(/^.*[\\/]/, '')
  const dirPath = currentVideoPath.value.replace(/[^\\/]+$/, '')
  const outPath = dirPath + '[金水1987]' + baseName
  try {
    await fetch(`${apiBase}/api/export/video`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        subtitles: currentSubtitles.value,
        mode: 'video',
        output_path: outPath,
        video_path: currentVideoPath.value,
        style_config: styleConfig.value,
      }),
    })
    statusMsg.value = `✅ 视频导出成功: ${outPath}`
    showToast('✅ 视频导出成功！', outPath)
  } catch {
    statusMsg.value = '✅ 视频导出成功（预览模式）'
    showToast('✅ 视频导出成功（预览模式）')
  }
}

function onStyleSaved(cfg: any) {
  styleConfig.value = { ...styleConfig.value, ...cfg }
  showStyleDialog.value = false
}
</script>

<!-- ============================================================= -->
<template>
  <div
    class="h-full w-full sao-grid sao-crt flex flex-col overflow-hidden"
    @dragover.prevent="onDragOver"
    @dragenter.prevent="onDragEnter"
    @dragleave.prevent="onDragLeave"
    @drop.prevent="onDrop"
  >

    <!-- ========== 顶部状态栏 ========== -->
    <header class="h-10 flex items-center justify-between px-4 border-b border-primary/10 bg-surface/50 backdrop-blur-xl shrink-0">
      <div class="flex items-center gap-3">
        <div class="w-5 h-5 flex items-center justify-center border border-accent/40 text-accent text-[8px] font-bold tracking-widest">金</div>
        <span class="text-[11px] font-bold tracking-[0.15em] text-primary">金水字幕 Pro</span>
        <span class="text-[9px] text-text-dim/40">v2.0</span>
        <span class="flex items-center gap-1.5 ml-2">
          <span class="w-1.5 h-1.5 rounded-full"
            :class="{
              'bg-accent': engineStatus === 'ready',
              'bg-yellow-400 animate-pulse': engineStatus === 'starting',
              'bg-accent animate-pulse': engineStatus === 'preview',
              'bg-danger animate-pulse': engineStatus === 'error',
            }"
          ></span>
          <span class="text-[10px] text-text-dim tracking-wider">
            {{ engineStatus === 'ready' ? '系统就绪' : engineStatus === 'preview' ? '预览模式' : engineStatus === 'starting' ? '启动中...' : '错误' }}
          </span>
          <span v-if="gpuInfo" class="text-[9px] text-text-dim/50 ml-1">| {{ gpuInfo }}</span>
        </span>
      </div>
      <div class="flex items-center gap-3">
        <span v-if="donateThanks" class="text-[10px] text-accent tracking-wider animate-pulse">🧡 感谢您的支持，祝您康健，暴富！</span>
        <span v-else class="text-[9px] text-text-dim/30 tracking-wider">由 <span class="text-accent/60">B站 金水1987</span> 制作</span>
      </div>
    </header>

    <!-- ========== 错误栏 ========== -->
    <div v-if="error" class="h-7 flex items-center px-4 bg-danger/10 border-b border-danger/20 text-[10px] text-danger tracking-wider shrink-0">
      ⚠ {{ error }}
    </div>

    <!-- ========== 主体 ========== -->
    <div class="flex-1 flex overflow-hidden">

      <!-- ====== 左侧：项目列表 ====== -->
      <div class="w-52 shrink-0 flex flex-col border-r border-primary/10 bg-surface/30">
        <div class="h-9 flex items-center px-3 border-b border-primary/10 bg-surface/20 shrink-0">
          <span class="text-[9px] tracking-wider text-text-dim/60">📁 项目文件</span>
        </div>
        <div class="flex-1 overflow-y-auto p-2 space-y-1">
          <div
            v-for="path in projectList"
            :key="path"
            @click="selectProject(path)"
            class="px-2 py-1.5 text-[10px] cursor-pointer border border-transparent transition-all group flex items-center justify-between"
            :class="currentVideoPath === path ? 'bg-primary/20 border-primary/30 text-text-primary' : 'text-text-dim/60 hover:bg-primary/10'"
          >
            <span class="truncate flex-1">{{ (projects[path] as any)._displayName || path.split('\\').pop()?.split('/').pop() }}</span>
            <button @click.stop="removeProject(path)" class="text-text-dim/20 hover:text-danger text-xs ml-1 opacity-0 group-hover:opacity-100 transition-opacity" title="移除">✕</button>
          </div>
          <div v-if="!projectList.length" class="text-[9px] text-text-dim/30 text-center py-4 tracking-wider">
            拖拽视频到此处<br>或点击导入
          </div>
        </div>

        <!-- 导入按钮 -->
        <div class="p-2 border-t border-primary/10">
          <button
            @click="importVideo"
            class="w-full py-1.5 text-[9px] tracking-wider border border-primary/30 text-primary/70 hover:text-primary hover:border-primary/60 transition-all"
            :class="{ 'animate-pulse': dragging }"
          >
            + 导入视频
          </button>
          <div
            class="mt-2 h-16 rounded border border-dashed border-primary/20 flex items-center justify-center text-[8px] text-text-dim/30 tracking-wider cursor-pointer transition-all"
            :class="dragging ? 'border-accent/50 bg-accent/5 text-accent/60' : 'hover:border-primary/40'"
            @dragover.prevent="onDragOver" @dragenter.prevent="onDragEnter" @dragleave.prevent="onDragLeave" @drop.prevent="onDrop"
          >
            {{ dragging ? '释放以添加' : '拖拽视频至此' }}
          </div>
        </div>
      </div>

      <!-- ====== 中间：字幕表格 ====== -->
      <div class="flex-1 flex flex-col min-w-0">

        <!-- 工具栏 -->
        <div class="h-9 flex items-center gap-1 px-2 border-b border-primary/10 bg-surface/20 shrink-0">
          <button @click="batchTranslate" class="px-2.5 py-1 text-[9px] tracking-wider border border-primary/30 text-primary/70 hover:text-primary hover:border-primary/60 transition-all">🌐 翻译</button>
          <button @click="batchOptimize" class="px-2.5 py-1 text-[9px] tracking-wider border border-primary/30 text-primary/70 hover:text-primary hover:border-primary/60 transition-all">✨ 润色</button>
          <button @click="showStyleDialog = true" class="px-2.5 py-1 text-[9px] tracking-wider border border-primary/30 text-primary/70 hover:text-primary hover:border-primary/60 transition-all">🎨 样式</button>
          <div class="w-px h-4 bg-primary/20 mx-1"></div>
          <button @click="mergeSelected" :disabled="selectedRows.size < 2" class="px-2 py-1 text-[9px] tracking-wider border border-primary/20 text-primary/50 hover:text-primary disabled:opacity-20 disabled:cursor-not-allowed transition-all">合并行</button>
          <div class="flex-1"></div>
          <span class="text-[9px] text-text-dim/40 tracking-wider mr-2">共 {{ currentSubtitles.length }} 条</span>
          <button @click="exportSRT" class="px-2 py-1 text-[9px] tracking-wider border border-primary/20 text-primary/50 hover:text-primary transition-all">.SRT</button>
          <button @click="exportASS" class="px-2 py-1 text-[9px] tracking-wider border border-primary/20 text-primary/50 hover:text-primary transition-all">.ASS</button>
          <button v-if="currentVideoPath" @click="exportVideo" class="px-2 py-1 text-[9px] tracking-wider border border-accent/30 text-accent/70 hover:text-accent transition-all">压制视频</button>
        </div>

        <!-- 打轴进度条 -->
        <div v-if="asrProgress > 0 && asrProgress < 100" class="h-1.5 bg-primary/10 overflow-hidden shrink-0">
          <div class="h-full bg-gradient-to-r from-primary to-accent transition-all duration-500 animate-pulse" :style="{ width: asrProgress + '%' }"></div>
        </div>

        <!-- 字幕表格 -->
        <div class="flex-1 overflow-auto">
          <table class="w-full text-[10px] border-collapse">
            <thead class="sticky top-0 z-10">
              <tr class="bg-surface/40 border-b border-primary/15">
                <th class="w-6 px-1 py-1.5 text-text-dim/40 text-[9px]"></th>
                <th class="w-14 px-1 py-1.5 text-text-dim/40 text-[9px] tracking-wider font-normal">开始</th>
                <th class="w-14 px-1 py-1.5 text-text-dim/40 text-[9px] tracking-wider font-normal">结束</th>
                <th class="px-2 py-1.5 text-text-dim/40 text-[9px] tracking-wider font-normal text-left">原文</th>
                <th class="px-2 py-1.5 text-text-dim/40 text-[9px] tracking-wider font-normal text-left">译文</th>
                <th class="w-7 px-1 py-1.5 text-text-dim/40 text-[9px] font-normal">重译</th>
                <th class="w-7 px-1 py-1.5 text-text-dim/40 text-[9px] font-normal">插入</th>
                <th class="w-7 px-1 py-1.5 text-text-dim/40 text-[9px] font-normal">删除</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(sub, i) in currentSubtitles"
                :key="sub.id"
                @click="highlightId = sub.id"
                class="border-b border-primary/5 transition-colors"
                :class="highlightId === sub.id ? 'bg-accent/5 border-l-0' : 'hover:bg-primary/5'"
              >
                <td class="px-1 py-1 text-center">
                  <input type="checkbox" :checked="selectedRows.has(i)" @click.stop="toggleRow(i)" class="accent-accent w-2.5 h-2.5 cursor-pointer" />
                </td>
                <td class="px-1 py-1 font-mono text-[9px]" :class="highlightId === sub.id ? 'text-accent/60' : 'text-text-dim/30'">{{ formatTime(sub.start_time) }}</td>
                <td class="px-1 py-1 font-mono text-[9px]" :class="highlightId === sub.id ? 'text-accent/60' : 'text-text-dim/30'">{{ formatTime(sub.end_time) }}</td>
                <td class="px-2 py-1 min-w-0 max-w-[200px]" @dblclick="startEdit(i, 2, sub.original_text)">
                  <input v-if="editingRow === i && editingCol === 2" v-model="editText" @blur="saveEdit" @keyup.enter="saveEdit"
                    class="w-full bg-black/60 border border-primary/50 px-1 py-0.5 text-[10px] text-white outline-none" autofocus />
                  <span v-else class="truncate block text-text-primary/90">{{ sub.original_text }}</span>
                </td>
                <td class="px-2 py-1 min-w-0 max-w-[200px]" @dblclick="startEdit(i, 3, sub.translated_text)">
                  <input v-if="editingRow === i && editingCol === 3" v-model="editText" @blur="saveEdit" @keyup.enter="saveEdit"
                    class="w-full bg-black/60 border border-primary/50 px-1 py-0.5 text-[10px] text-accent outline-none" autofocus />
                  <span v-else class="truncate block text-accent/80">{{ sub.translated_text }}</span>
                </td>
                <td class="px-1 py-1 text-center">
                  <button @click.stop="singleTranslate(sub)" class="text-[11px] text-text-dim/30 hover:text-accent transition-colors" title="重新翻译此句">🔄</button>
                </td>
                <td class="px-1 py-1 text-center">
                  <button @click.stop="insertAfter(i)" class="text-[11px] text-text-dim/30 hover:text-accent transition-colors" title="在下方插入新句">➕</button>
                </td>
                <td class="px-1 py-1 text-center">
                  <button @click.stop="deleteSub(i)" class="text-[11px] text-text-dim/30 hover:text-danger transition-colors" title="删除此句">✕</button>
                </td>
              </tr>
              <tr v-if="!currentSubtitles.length">
                <td colspan="8" class="text-center py-12 text-[10px] text-text-dim/30 tracking-wider">
                  {{ processing ? '▌ 正在处理音频... ▌' : '▌ 拖拽视频文件开始 ▌' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 底部状态 -->
        <div class="h-6 flex items-center px-3 border-t border-primary/10 bg-surface/30 shrink-0">
          <span class="text-[8px] text-text-dim/40 tracking-wider">{{ statusMsg }}</span>
          <span v-if="asrProgress > 0" class="text-[8px] text-accent/60 ml-2">{{ asrProgressText }}</span>
          <div class="flex-1"></div>
          <span class="text-[8px] text-text-dim/20">{{ currentSubtitles.length }} 条字幕</span>
        </div>
      </div>

      <!-- ====== 右侧：配置面板 ====== -->
      <div class="w-72 shrink-0 flex flex-col border-l border-primary/10 bg-surface/30 backdrop-blur-xl">
        <div class="h-9 flex items-center px-3 border-b border-primary/10 bg-surface/20 shrink-0">
          <span class="text-[9px] tracking-wider text-text-dim/60">⚙️ 配置面板</span>
        </div>

        <div class="flex-1 overflow-y-auto p-3 space-y-3">

          <!-- 翻译引擎 -->
          <div class="border border-primary/10 p-2.5">
            <div class="text-[9px] text-accent-dim/60 tracking-wider mb-2 pb-1 border-b border-primary/10">🤖 翻译引擎</div>
            <div class="space-y-2 text-[10px]">
              <div class="flex items-center justify-between">
                <span class="text-text-dim/60">引擎</span>
                <select v-model="engineType" class="w-32 bg-background/80 border border-primary/30 px-1 py-0.5 text-[10px] text-text-primary outline-none">
                  <option value="deepseek">DeepSeek</option>
                  <option value="google">Google</option>
                  <option value="baidu">Baidu</option>
                </select>
              </div>
              <div class="flex items-center justify-between">
                <span class="text-text-dim/60">目标语言</span>
                <select v-model="targetLang" class="w-32 bg-background/80 border border-primary/30 px-1 py-0.5 text-[10px] text-text-primary outline-none">
                  <option>英文</option><option>日文</option><option>韩文</option><option>繁体中文</option>
                  <option>法文</option><option>俄文</option><option>西班牙文</option>
                </select>
              </div>
              <div>
                <span class="text-text-dim/60 block mb-0.5">API Key</span>
                <input v-model="apiKey" type="password" placeholder="sk-..." class="w-full bg-background/80 border border-primary/30 px-1.5 py-1 text-[10px] text-text-primary outline-none placeholder-text-dim/20" />
              </div>
              <div>
                <span class="text-text-dim/60 block mb-0.5">Base URL</span>
                <input v-model="apiBaseUrl" class="w-full bg-background/80 border border-primary/30 px-1.5 py-1 text-[10px] text-text-primary outline-none" />
              </div>
              <div>
                <span class="text-text-dim/60 block mb-0.5">Model</span>
                <input v-model="modelName" class="w-full bg-background/80 border border-primary/30 px-1.5 py-1 text-[10px] text-text-primary outline-none" />
              </div>
            </div>
          </div>

          <!-- 术语库 -->
          <div class="border border-primary/10 p-2.5">
            <div class="text-[9px] text-accent-dim/60 tracking-wider mb-2 pb-1 border-b border-primary/10">📖 术语库与参考文稿</div>
            <textarea v-model="glossary" placeholder="输入术语或参考文本..."
              class="w-full h-16 bg-background/80 border border-primary/30 px-1.5 py-1 text-[10px] text-text-primary outline-none placeholder-text-dim/20 resize-none"></textarea>
            <div class="flex items-center justify-between mt-1.5">
              <span class="text-[9px] text-text-dim/40">单行最大字数</span>
              <input v-model.number="maxChars" type="number" min="10" max="60" class="w-14 bg-background/80 border border-primary/30 px-1 py-0.5 text-[10px] text-text-primary outline-none text-center" />
            </div>
          </div>

          <!-- 操作按钮 -->
          <div class="space-y-1.5">
            <button @click="batchTranslate" class="w-full py-1.5 text-[9px] tracking-wider border border-primary/30 text-primary/70 hover:text-primary hover:border-primary/60 transition-all bg-primary/5">
              🌐 批量翻译
            </button>
            <button @click="batchOptimize" class="w-full py-1.5 text-[9px] tracking-wider border border-primary/30 text-primary/70 hover:text-primary hover:border-primary/60 transition-all">
              ✨ 润色原文
            </button>
            <button @click="showStyleDialog = true" class="w-full py-1.5 text-[9px] tracking-wider border border-accent/30 text-accent/70 hover:text-accent hover:border-accent/60 transition-all">
              🎨 字幕样式设置
            </button>
            <div class="border-t border-primary/10 pt-1.5 mt-1.5">
              <button @click="exportSRT" class="w-full py-1.5 text-[9px] tracking-wider border border-primary/30 text-primary/70 hover:text-primary hover:border-primary/60 transition-all mb-1">
                📤 导出 SRT
              </button>
              <button @click="exportASS" class="w-full py-1.5 text-[9px] tracking-wider border border-primary/30 text-primary/70 hover:text-primary hover:border-primary/60 transition-all mb-1">
                📤 导出 ASS
              </button>
              <button v-if="currentVideoPath" @click="exportVideo" class="w-full py-1.5 text-[9px] tracking-wider border border-accent/30 text-accent/70 hover:text-accent hover:border-accent/60 transition-all">
                🎬 压制硬字幕视频
              </button>
            </div>

            <!-- 打赏按钮 -->
            <div class="mt-4 pt-3">
              <button @click="openDonate"
                class="w-full py-2 text-[10px] tracking-wider font-semibold border border-amber-400/40 text-amber-300/80 hover:text-amber-200 hover:border-amber-300/60 hover:bg-amber-400/5 transition-all shadow-[0_0_12px_rgba(251,191,36,0.08)]">
                🥤 请作者喝可乐
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- ====== 全屏拖拽覆盖层 ====== -->
  <Teleport to="body">
    <div
      v-if="dragging"
      @dragover.prevent="onDragOver"
      @dragenter.prevent="onDragEnter"
      @dragleave.prevent="onDragLeave"
      @drop.prevent="onDrop"
      class="fixed inset-0 z-[9998] bg-accent/10 backdrop-blur-sm flex items-center justify-center"
    >
      <div class="text-center pointer-events-none">
        <div class="text-5xl mb-4">🎯</div>
        <div class="text-xl font-bold text-accent tracking-wider">释放鼠标以导入视频</div>
        <div class="text-sm text-text-dim/60 mt-2">支持 mp4 / mkv / mov / avi</div>
      </div>
    </div>
  </Teleport>

  <!-- 隐藏的文件输入 -->
  <input
    ref="fileInputRef"
    type="file"
    accept="video/mp4,video/x-matroska,video/quicktime,video/avi"
    multiple
    class="hidden"
    @change="onFilesSelected"
  />

  <!-- 样式设置弹窗 -->
  <StyleDialog
    v-if="showStyleDialog"
    :config="styleConfig"
    @close="showStyleDialog = false"
    @save="onStyleSaved"
  />

  <!-- 导出成功 Toast（居中） -->
  <Teleport to="body">
    <div
      v-if="toast.show"
      class="fixed inset-0 z-[9999] flex items-center justify-center pointer-events-none"
    >
      <div class="pointer-events-auto w-96 bg-surface border border-accent/30 sao-hud shadow-[0_0_40px_rgba(0,245,212,0.18)] transition-all duration-300">
        <div class="p-5">
          <div class="flex items-start justify-between">
            <span class="text-[12px] font-semibold text-accent tracking-wider">{{ toast.message }}</span>
            <button @click="closeToast" class="text-text-dim/40 hover:text-danger text-sm ml-3">✕</button>
          </div>
          <div v-if="toast.path" class="mt-2 text-[9px] text-text-dim/50 break-all select-all font-mono">{{ toast.path }}</div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
