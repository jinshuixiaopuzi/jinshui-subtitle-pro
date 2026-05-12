import json
import concurrent.futures
from openai import OpenAI
from deep_translator import GoogleTranslator
from core.subtitle_model import SubtitleManager

class TranslatorEngine:
    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com", model: str = "deepseek-chat", engine_type: str = "deepseek"):
        self.engine_type = engine_type
        safe_api_key = api_key if api_key else "EMPTY_KEY"
        self.client = OpenAI(api_key=safe_api_key, base_url=base_url)
        self.model = model

    def _translate_chunk_deepseek(self, chunk, glossary, target_lang):
        payload_data =[{"id": s["id"], "text": s["text"]} for s in chunk]
        payload_str = json.dumps(payload_data, ensure_ascii=False)
        sys_prompt = f"你是一个专业影视字幕翻译。请严格将以下 JSON 数组的 'text' 字段翻译为【{target_lang}】。\n"
        sys_prompt += "必须返回 {'subtitles':[{'id': '..', 'translated_text': '..'}]} 格式，绝不遗漏ID。\n"
        
        if glossary: 
            sys_prompt += f"【警告】遇到以下术语，必须100%强制替换为指定词汇，否则扣除工资：\n{glossary}"

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": payload_str}],
            response_format={"type": "json_object"}, temperature=0.2 
        )
        res_json = json.loads(response.choices[0].message.content)
        return res_json.get("subtitles",[]) or res_json

    def _translate_chunk_free(self, chunk, vendor, target_lang):
        """使用免费翻译引擎，支持 google 和 baidu"""
        lang_map = {"英文": "en", "日文": "ja", "韩文": "ko", "繁体中文": "zh-TW", "法文": "fr", "俄文": "ru", "西班牙文": "es"}
        to_code = lang_map.get(target_lang, "en")
        
        texts_to_trans = "\n".join([s["text"] for s in chunk])
        
        if vendor == "google":
            try:
                # deep-translator 用 zh-CN 而不是 zh
                translated_texts = GoogleTranslator(source='zh-CN', target=to_code).translate(texts_to_trans)
                trans_list = translated_texts.split("\n")
            except Exception as e:
                # Google 降级到百度
                print(f"  [Translator] Google 翻译失败({e})，降级到 Baidu...")
                return self._translate_chunk_free(chunk, "baidu", target_lang)
        elif vendor == "baidu":
            import translators as ts
            translated_texts = ts.translate_text(texts_to_trans, translator='baidu', from_language='zh', to_language=to_code)
            trans_list = translated_texts.split("\n")
        else:
            raise ValueError(f"不支持的免费引擎: {vendor}")
        
        results =[]
        for i, s in enumerate(chunk):
            t_text = trans_list[i] if i < len(trans_list) else ""
            results.append({"id": s["id"], "translated_text": t_text})
        return results

    def batch_translate(self, subtitle_manager: SubtitleManager, glossary: str = "", target_lang: str = "英文"):
        subs = subtitle_manager.get_all_for_ai()
        if not subs: return

        batch_size = 50
        chunks = [subs[i:i + batch_size] for i in range(0, len(subs), batch_size)]
        total_batches = len(chunks)
        print(f"\n[Translator] 共 {total_batches} 批数据。目标语言: {target_lang}。当前引擎: {self.engine_type}")
        
        success_count = 0

        if self.engine_type == "deepseek":
            print("[Translator] 🚀 启用 DeepSeek 多线程高并发加速！")
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                future_to_chunk = {executor.submit(self._translate_chunk_deepseek, chunk, glossary, target_lang): chunk for chunk in chunks}
                for future in concurrent.futures.as_completed(future_to_chunk):
                    try:
                        translated_list = future.result()
                        for item in translated_list:
                            if "id" in item and "translated_text" in item:
                                subtitle_manager.update_translation(item["id"], item["translated_text"])
                                success_count += 1
                        print(f"[Translator] ✅ 某批次并发翻译完成！")
                    except Exception as e:
                        print(f"[Translator] ❌ 某批次并发报错: {e}")
        else:
            vendor = "baidu" if self.engine_type == "baidu" else "google"
            print(f"[Translator] 🐢 免费引擎 ({vendor})，单线程匀速翻译...")
            for i, chunk in enumerate(chunks):
                try:
                    translated_list = self._translate_chunk_free(chunk, vendor=vendor, target_lang=target_lang)
                    for item in translated_list:
                        if "id" in item and "translated_text" in item:
                            subtitle_manager.update_translation(item["id"], item["translated_text"])
                            success_count += 1
                    print(f"[Translator] ✅ 第 {i+1}/{total_batches} 批完成。")
                except Exception as e:
                    print(f"[Translator] ❌ 第 {i+1} 批报错: {e}")
                    
        print(f"\n[Translator] 🎉 翻译结束！成功更新 {success_count}/{len(subs)} 句。")

    def batch_optimize(self, subtitle_manager: SubtitleManager, glossary: str = ""):
        if self.engine_type != "deepseek":
            raise ValueError("免费翻译引擎不支持上下文润色，请切换至 DeepSeek API！")
            
        subs = subtitle_manager.get_all_for_ai()
        if not subs: return
        
        batch_size = 50
        chunks = [subs[i:i + batch_size] for i in range(0, len(subs), batch_size)]
        success_count = 0

        print(f"\n[Optimizer] 启动中文润色，共 {len(chunks)} 批并发进行中...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            def _opt_task(chunk):
                payload = json.dumps([{"id": s["id"], "text": s["text"]} for s in chunk], ensure_ascii=False)
                prompt = (
                    "你是一个专业的字幕校对员。请修改发给你的 JSON 文本。\n"
                    "任务：修正错别字、音频识别错误(如把'的得地'弄错)、去掉无意义的语气词。保持语意不变。\n"
                    "返回格式：{'subtitles':[{'id': '..', 'corrected_text': '..'}]}\n"
                )
                if glossary: prompt += f"强制术语库(必须替换)：\n{glossary}"
                
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "system", "content": prompt}, {"role": "user", "content": payload}],
                    response_format={"type": "json_object"}, temperature=0.1
                )
                res_json = json.loads(resp.choices[0].message.content)
                return res_json.get("subtitles",[]) or res_json

            future_to_chunk = {executor.submit(_opt_task, chunk): chunk for chunk in chunks}
            for future in concurrent.futures.as_completed(future_to_chunk):
                try:
                    for item in future.result():
                        if "id" in item and "corrected_text" in item:
                            subtitle_manager.update_original(item["id"], item["corrected_text"])
                            success_count += 1
                except Exception as e:
                    print(f"[Optimizer] ❌ 润色批次报错: {e}")
                    
        print(f"\n[Optimizer] 🎉 润色结束！成功优化 {success_count} 句。")
