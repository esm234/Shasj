import os
import json
import google.generativeai as genai
from typing import List, Dict, Any

# إعداد مفتاح الـ API
try:
    GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    print(f"Error configuring Gemini API: {e}")

# --- PROMPT ذكي مطوّر ---
PROMPT_TEMPLATE = """
مهمتك هي استخراج جميع الأسئلة الموجودة في النص التالي (قد يحتوي على أكثر من سؤال واحد).

لكل سؤال استخرج:
- "question_number": رقم السؤال في الترتيب داخل النص (ابدأ من 1)
- "question_text": نص السؤال بعد تنظيفه من أي زيادات أو مقدّمات
- "options": قائمة بالخيارات الموجودة (بترتيبها المنطقي)

🔹 شكل الإخراج المطلوب بدقة:
[
  {
    "question_number": 1,
    "question_text": "نص السؤال الأول هنا",
    "options": ["الخيار الأول", "الخيار الثاني", "الخيار الثالث"]
  },
  {
    "question_number": 2,
    "question_text": "نص السؤال الثاني هنا",
    "options": []
  }
]

📜 القواعد الذكية:
1. تجاهل تمامًا أي بيانات تعريفية مثل (الاسم، اليوزر، ID، الوقت، مشاركة جديدة، سؤال جديد).
2. السؤال هو أي جملة تحتوي على:
   - علامة استفهام (؟)
   - أو تبدأ بكلمات مثل: "ما"، "من"، "أين"، "كم"، "هل"، "اختر"، "أكمل"، "العلاقة"، "الغرض"، "المقصود"، "يفيد"، "يدل"، "مرادف".
3. الخيارات يمكن أن تكون:
   - في سطر واحد (مفصولة بمسافات أو شرطات)
   - أو في أسطر منفصلة (تبدأ بـ A. أو 1- أو 🔹 أو • أو بدون رموز)
   - أو بعد كلمة "الاختيارات" أو "الخيارات".
4. إذا لم يوجد خيارات، أعد قائمة فارغة.
5. لا تضف أي نص أو شرح خارج JSON.
6. أعد فقط JSON صحيح بالكامل.

الآن حلّل النص التالي:
---
{text}
---
"""

def parse_question_with_ai(text: str) -> List[Dict[str, Any]]:
    """
    تحليل نصوص طويلة تحتوي على عدة أسئلة، مع اكتشاف رقم السؤال والخيارات بدقة.
    """
    if not GOOGLE_API_KEY:
        print("❌ GEMINI_API_KEY is not set. AI parser cannot function.")
        return []

    try:
        model = genai.GenerativeModel('gemini-pro')
        prompt = PROMPT_TEMPLATE.format(text=text)
        response = model.generate_content(prompt)

        cleaned = response.text.strip().replace("```json", "").replace("```", "")
        data = json.loads(cleaned)

        # تأكيد أن الناتج List
        if isinstance(data, dict):
            data = [data]

        # إضافة fallback في حال بعض القيم ناقصة
        for i, q in enumerate(data, start=1):
            q.setdefault("question_number", i)
            q.setdefault("question_text", "")
            q.setdefault("options", [])
        return data

    except json.JSONDecodeError:
        print(f"⚠️ AI response was not valid JSON:\n{response.text}")
        return [{"question_number": 1, "question_text": text, "options": []}]
    except Exception as e:
        print(f"❌ Error with Gemini API: {e}")
        return []
