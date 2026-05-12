import uuid
from dataclasses import dataclass
from typing import List, Optional
import re

@dataclass
class SubtitleItem:
    id: str                 
    start_time: float       
    end_time: float         
    original_text: str      # UI显示和压制用（去除了标点，用空格代替）
    reference_text: str     # 隐藏变量（带完美标点，喂给AI提供语境）
    translated_text: str    
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

class SubtitleManager:
    def __init__(self):
        self.subtitles: List[SubtitleItem] =[]
    
    def add_from_asr(self, start: float, end: float, text: str):
        # 1. 存入带标点的完整参考文本给 AI
        ref_text = text.strip()
        # 2. 正则表达式：把所有中英文标点符号替换为空格
        display_text = re.sub(r'[，。？！,?!;；、:：]', ' ', ref_text)
        # 把多余的连续空格压缩成一个空格，并去除首尾空格
        display_text = re.sub(r'\s+', ' ', display_text).strip()
        
        item = SubtitleItem(
            id=str(uuid.uuid4()), start_time=start, end_time=end,
            original_text=display_text, reference_text=ref_text, translated_text=""
        )
        self.subtitles.append(item)
    
    def update_translation(self, item_id: str, new_trans: str):
        for sub in self.subtitles:
            if sub.id == item_id:
                sub.translated_text = new_trans
                break

    def update_original(self, item_id: str, new_orig: str):
        for sub in self.subtitles:
            if sub.id == item_id:
                sub.original_text = new_orig
                # 如果用户手动修改了UI上的文字，同步更新参考文本
                sub.reference_text = new_orig 
                break
                
    # ... delete_item, insert_item_after 等其余函数保持不变 ...

    def get_all_for_ai(self) -> List[dict]:
        """打包发送给大模型（优先发送带有标点的参考文本，让AI懂语境）"""
        return[{"id": sub.id, "text": sub.reference_text or sub.original_text} for sub in self.subtitles]

    def delete_item(self, item_id: str):
        """删除某一句（UI上点击删除时直接调用）"""
        self.subtitles =[sub for sub in self.subtitles if sub.id != item_id]

    def insert_item_after(self, target_id: str):
        """在某一句后面插入一条空字幕"""
        target_index = -1
        for i, sub in enumerate(self.subtitles):
            if sub.id == target_id:
                target_index = i
                break
                
        if target_index != -1:
            target_sub = self.subtitles[target_index]
            new_item = SubtitleItem(
                id=str(uuid.uuid4()),
                start_time=target_sub.end_time + 0.01,
                end_time=target_sub.end_time + 2.01, # 默认给2秒长度
                original_text="[新建字幕]",
                translated_text="[New Subtitle]"
            )
            self.subtitles.insert(target_index + 1, new_item)

    def get_all_for_translation(self) -> List[dict]:
        """打包成 DeepSeek 需要的格式进行批量翻译"""
        return[{"id": sub.id, "text": sub.original_text} for sub in self.subtitles]

    def debug_print(self):
        """测试用的打印"""
        print(f"当前字幕数量: {len(self.subtitles)}")
        for sub in self.subtitles:
            print(f"[{sub.start_time:.2f} -> {sub.end_time:.2f}] {sub.original_text} | {sub.translated_text}")
    def merge_with_next(self, item_id: str):
        """将当前字幕与下一条合并"""
        target_index = -1
        for i, sub in enumerate(self.subtitles):
            if sub.id == item_id:
                target_index = i
                break
                
        # 如果找到了，且它不是最后一条
        if target_index != -1 and target_index < len(self.subtitles) - 1:
            current_sub = self.subtitles[target_index]
            next_sub = self.subtitles[target_index + 1]
            
            # 1. 文本合并（中间加个空格）
            current_sub.original_text += " " + next_sub.original_text
            if current_sub.translated_text and next_sub.translated_text:
                current_sub.translated_text += " " + next_sub.translated_text
            elif next_sub.translated_text:
                current_sub.translated_text = next_sub.translated_text
                
            # 2. 结束时间延长到下一条的结束时间
            current_sub.end_time = next_sub.end_time
            
            # 3. 销毁下一条
            self.subtitles.pop(target_index + 1)
    def merge_selected(self, id_list: list):
        """将选中的多个 ID 的字幕合并为一条"""
        if len(id_list) < 2: return
        
        # 提取需要合并的字幕对象，并按时间排序确保顺序正确
        subs_to_merge =[s for s in self.subtitles if s.id in id_list]
        subs_to_merge.sort(key=lambda x: x.start_time)
        
        if not subs_to_merge: return

        first_sub = subs_to_merge[0]
        for i in range(1, len(subs_to_merge)):
            # 拼合原文
            first_sub.original_text += " " + subs_to_merge[i].original_text
            # 拼合译文
            if first_sub.translated_text and subs_to_merge[i].translated_text:
                first_sub.translated_text += " " + subs_to_merge[i].translated_text
            elif subs_to_merge[i].translated_text:
                first_sub.translated_text = subs_to_merge[i].translated_text
            
            # 延长结束时间
            first_sub.end_time = max(first_sub.end_time, subs_to_merge[i].end_time)
            
            # 从主列表中销毁被合并的条目
            self.subtitles.remove(subs_to_merge[i])