import os
import html # <-- استدعاء مكتبة جديدة (مدمجة مع بايثون)
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_RIGHT
from datetime import datetime
from reportlab.lib.pagesizes import A4

import arabic_reshaper
from bidi.algorithm import get_display

# --- الإعدادات ---
ARABIC_FONT_NAME = "Amiri-Regular"
ARABIC_FONT_FILE = "Amiri-Regular.ttf"

def register_arabic_font():
    """يسجل الخط العربي لكي تتمكن المكتبة من استخدامه."""
    try:
        if ARABIC_FONT_NAME not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(ARABIC_FONT_NAME, ARABIC_FONT_FILE))
    except Exception as e:
        print(f"CRITICAL: Could not register font {ARABIC_FONT_FILE}. Arabic text will not render. Error: {e}")

def create_questions_pdf(questions_data: dict, file_path: str) -> str:
    """
    ينشئ ملف PDF من بيانات الأسئلة، مع دعم كامل للعربية ومعالجة آمنة للنصوص.
    """
    register_arabic_font()
    
    doc = SimpleDocTemplate(file_path, pagesize=A4)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('ArabicTitle', parent=styles['h1'], fontName=ARABIC_FONT_NAME, fontSize=20, alignment=TA_RIGHT, spaceAfter=20)
    meta_style = ParagraphStyle('MetaStyle', parent=styles['Normal'], fontName=ARABIC_FONT_NAME, fontSize=10, alignment=TA_RIGHT)
    question_style = ParagraphStyle('QuestionStyle', parent=styles['Normal'], fontName=ARABIC_FONT_NAME, fontSize=14, alignment=TA_RIGHT, spaceBefore=10, spaceAfter=10, leading=20)
    option_style = ParagraphStyle('OptionStyle', parent=styles['Normal'], fontName=ARABIC_FONT_NAME, fontSize=12, alignment=TA_RIGHT, leftIndent=20)

    def format_arabic_text(text):
        if not text: return ""
        reshaped_text = arabic_reshaper.reshape(text)
        bidi_text = get_display(reshaped_text)
        return bidi_text

    story.append(Paragraph(format_arabic_text("تجميع أسئلة القدرات - بوت هدفك"), title_style))
    story.append(Paragraph(format_arabic_text(f"تاريخ التجميع: {datetime.now().strftime('%Y-%m-%d %H:%M')}"), meta_style))
    story.append(Spacer(1, 30))

    sorted_questions = sorted(questions_data.values(), key=lambda x: x['timestamp'])

    for i, q in enumerate(sorted_questions, 1):
        # --- بداية التعديل المهم ---
        # 1. احصل على النص الخام من المستخدم
        raw_question_text = q.get('question_text') or q.get('raw_content') or "(مشاركة وسائط بدون نص)"
        
        # 2. قم بتهريب (escape) النص الخام لتحويل الرموز الخاصة إلى نص آمن
        safe_question_text = html.escape(raw_question_text)
        
        # 3. الآن يمكنك إضافة وسوم HTML الخاصة بك بأمان
        final_paragraph_text = f"<b>{i}. السؤال:</b><br/>{safe_question_text.replace(chr(10), '<br/>')}"
        # --- نهاية التعديل المهم ---

        story.append(Paragraph(format_arabic_text(final_paragraph_text), question_style))
        
        if q.get('options'):
            story.append(Spacer(1, 10))
            option_letters = ['أ', 'ب', 'ج', 'د', 'هـ', 'و', 'ز', 'ح']
            for j, opt in enumerate(q['options']):
                # قم بتهريب الخيارات أيضًا
                safe_opt = html.escape(opt)
                letter = option_letters[j] if j < len(option_letters) else ''
                story.append(Paragraph(format_arabic_text(f"{letter}) {safe_opt}"), option_style))

        story.append(Spacer(1, 25))

    try:
        doc.build(story)
        return file_path
    except Exception as e:
        print(f"Failed to build PDF: {e}")
        return None
