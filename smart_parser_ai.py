import os
import json
import google.generativeai as genai
from typing import Dict

# إعداد مفتاح الـ API من ملف .env الذي جهزته
try:
    GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    print(f"Error configuring Gemini API: {e}")

# هذا هو الأمر (الـ Prompt) الذي نعطيه للـ AI ليتبع التعليمات بدقة
PROMPT_TEMPLATE = """
مهمتك هي تحليل النص التالي الذي أرسله مستخدم، واستخراج نص السؤال وأي خيارات متاحة.
يجب أن يكون ردك عبارة عن كائن JSON صالح فقط، بدون أي نص إضافي قبله أو بعده.

استخدم الهيكل التالي بالضبط:
{
  "question_text": "نص السؤال الذي استخرجته هنا",
  "options": ["الخيار الأول", "الخيار الثاني", "الخيار الثالث"]
}

قواعد مهمة:
- إذا لم تجد أي خيارات واضحة، أعد قائمة فارغة في حقل "options".
- نظّف السؤال من أي جمل حوارية مثل "جاني سؤال" أو "للعلم مش متأكدة".
- إذا كان النص لا يبدو كسؤال على الإطلاق، أعد قيمة `null` في حقل "question_text".

الآن، قم بتحليل النص التالي:
---
النص المدخل: "{user_text}"
---
"""

def parse_question_with_ai(text: str) -> Dict[str, any] | None:
    """
    يستخدم Gemini AI لتحليل النص وإعادته كبيانات منظمة.
    """
    if not GOOGLE_API_KEY:
        print("GEMINI_API_KEY is not set. AI parser cannot function.")
        return None

    try:
        model = genai.GenerativeModel('gemini-pro')
        prompt = PROMPT_TEMPLATE.format(user_text=text)
        response = model.generate_content(prompt)
        
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        parsed_json = json.loads(cleaned_response)
        
        return parsed_json

    except json.JSONDecodeError:
        print(f"AI response was not valid JSON: {response.text}")
        return {"question_text": text, "options": []} # كخطة بديلة، نرجع النص الأصلي كسؤال
    except Exception as e:
        print(f"An error occurred with the Gemini API: {e}")
        return None
