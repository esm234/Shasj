import os
import html
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

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
        print(f"CRITICAL: Could not register font {ARABIC_FONT_FILE}. Error: {e}")

def draw_header_footer(canvas, doc):
    """
    هذه الدالة ترسم العناصر الثابتة مثل الهيدر والفوتر.
    """
    canvas.saveState()
    reshaped_header = arabic_reshaper.reshape("تجميعات القدرات - بوت هدفك")
    bidi_header = get_display(reshaped_header)
    canvas.setFont(ARABIC_FONT_NAME, 12)
    canvas.drawCentredString(A4[0] / 2, A4[1] - 2 * cm, bidi_header)
    canvas.setStrokeColorRGB(0, 0, 0)
    canvas.line(1 * cm, A4[1] - 2.5 * cm, A4[0] - 1 * cm, A4[1] - 2.5 * cm)
    reshaped_footer = arabic_reshaper.reshape(f"صفحة {doc.page}")
    bidi_footer = get_display(reshaped_footer)
    canvas.setFont(ARABIC_FONT_NAME, 9)
    canvas.drawCentredString(A4[0] / 2, 1.5 * cm, bidi_footer)
    canvas.restoreState()

def create_questions_pdf(questions_data: dict, file_path: str) -> str:
    """
    ينشئ ملف PDF بتصميم مخصص من عمود واحد وخيارات أفقية.
    """
    register_arabic_font()
    doc = BaseDocTemplate(file_path, pagesize=A4)
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height - 2*cm, id='normal')
    template = PageTemplate(id='main_template', frames=[frame], onPage=draw_header_footer)
    doc.addPageTemplates([template])
    story = []
    
    styles = getSampleStyleSheet()
    question_style = ParagraphStyle('QuestionStyle', parent=styles['Normal'], fontName=ARABIC_FONT_NAME, fontSize=14, alignment=TA_RIGHT, spaceBefore=10, spaceAfter=10, leading=22)
    option_style = ParagraphStyle('OptionStyle', parent=styles['Normal'], fontName=ARABIC_FONT_NAME, fontSize=12, alignment=TA_RIGHT, leftIndent=20, leading=18)

    def format_arabic_text(text):
        if not text: return ""
        reshaped_text = arabic_reshaper.reshape(text)
        bidi_text = get_display(reshaped_text)
        return bidi_text

    sorted_questions = sorted(questions_data.values(), key=lambda x: x['timestamp'])

    for i, q in enumerate(sorted_questions, 1):
        raw_question_text = q.get('question_text') or q.get('raw_content') or "(مشاركة وسائط بدون نص)"
        safe_question_text = html.escape(raw_question_text)
        final_paragraph_text = f"<b>{i}) السؤال:</b><br/>{safe_question_text.replace(chr(10), '<br/>')}"
        story.append(Paragraph(format_arabic_text(final_paragraph_text), question_style))
        
        # --- بداية التعديل: منطق الخيارات الأفقية ---
        if q.get('options'):
            story.append(Spacer(1, 8))
            option_letters = ['أ', 'ب', 'ج', 'د', 'هـ', 'و']
            
            horizontal_options = []
            for j, opt in enumerate(q['options']):
                safe_opt = html.escape(opt)
                letter = option_letters[j] if j < len(option_letters) else '•'
                # تنسيق كل خيار على حدة
                formatted_part = f"{letter}) {safe_opt}"
                horizontal_options.append(formatted_part)

            # تجميع كل الخيارات في سطر واحد مع فواصل
            full_options_string = "    -    ".join(horizontal_options)
            
            # إنشاء فقرة واحدة للسطر الأفقي
            story.append(Paragraph(format_arabic_text(full_options_string), option_style))
        # --- نهاية التعديل ---

        story.append(Spacer(1, 20))

    try:
        doc.build(story)
        return file_path
    except Exception as e:
        print(f"Failed to build PDF with custom design: {e}")
        return None
