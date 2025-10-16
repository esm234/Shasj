import re
from typing import Dict, List

def parse_question_text(text: str) -> Dict[str, any]:
    """
    يحلل النص باستخدام الكلمات المفتاحية والأنماط لفصل السؤال عن الخيارات.
    """
    # 1. البحث باستخدام الكلمات المفتاحية (الطريقة الأساسية)
    option_keywords = ['الاختيارات', 'الخيارات']
    question_text = text
    options_text = ''
    
    for keyword in option_keywords:
        # البحث عن الكلمة المفتاحية مع تجاهل حالة الأحرف
        match = re.search(r'\b' + keyword + r'\b.*', text, re.IGNORECASE | re.DOTALL)
        if match:
            # كل ما قبل الكلمة المفتاحية هو السؤال
            question_text = text[:match.start()].strip()
            # كل ما بعدها هو الخيارات
            options_text = text[match.start():].strip()
            # إزالة الكلمة المفتاحية نفسها من بداية نص الخيارات
            options_text = re.sub(r'^\s*' + keyword + r'\s*[:\n]*', '', options_text, flags=re.IGNORECASE).strip()
            break

    # 2. تنظيف السؤال من الجمل الحوارية
    common_intros = [
        "يا جماعة", "جاني سؤال", "جالي سؤال", "السؤال كان", "كان فيه سؤال", "سؤال اليوم",
        "للعلم مش متاكده", "للعلم اخترت", "اعتقد صيغه دقيقه", "اللفظي كان في قطعه"
    ]
    for intro in common_intros:
        question_text = re.sub(r'.*' + intro + r'.*[\n:]*', '', question_text, flags=re.IGNORECASE).strip()
    
    # 3. استخراج الخيارات من نص الخيارات
    options = []
    if options_text:
        # تقسيم الخيارات حسب الأسطر الجديدة
        options = [line.strip() for line in options_text.split('\n') if line.strip()]
        # تنظيف إضافي للخيارات (إزالة الترقيم إن وجد)
        option_pattern = re.compile(r'^\s*([أ-ي]\s*[.)-]|[\w]\s*[.)-]|[1-9]\d*\s*[.)-]|[*•-]\s+)', re.IGNORECASE)
        options = [option_pattern.sub('', opt).strip() for opt in options]
    
    # 4. إذا لم يتم العثور على خيارات عبر الكلمات المفتاحية، نستخدم الطريقة القديمة كخطة بديلة
    if not options and not options_text:
        lines = text.strip().split('\n')
        option_pattern = re.compile(r'^\s*([أ-ي]\s*[.)-]|[\w]\s*[.)-]|[1-9]\d*\s*[.)-]|[*•-]\s+)', re.IGNORECASE)
        question_lines = []
        option_lines = []
        is_reading_options = False

        for line in lines:
            if option_pattern.match(line.strip()):
                is_reading_options = True
            if is_reading_options:
                clean_option = option_pattern.sub('', line.strip()).strip()
                if clean_option: option_lines.append(clean_option)
            else:
                question_lines.append(line)
        
        if option_lines:
            question_text = "\n".join(question_lines).strip()
            options = option_lines

    # التأكد من أن السؤال ليس فارغًا
    if not question_text.strip():
        question_text = text # إذا فشل كل شيء، اعتبر النص كله سؤال

    return {
        "question_text": question_text.strip(),
        "options": [opt for opt in options if opt] # إزالة الخيارات الفارغة
    }
