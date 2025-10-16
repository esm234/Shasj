import os
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_RIGHT
from datetime import datetime
from reportlab.lib.pagesizes import A4

ARABIC_FONT_NAME = "Amiri-Regular"
ARABIC_FONT_FILE = "Amiri-Regular.ttf"

def register_arabic_font():
    """يسجل الخط العربي لكي تتمكن المكتبة من استخدامه."""
    try:
        if ARABIC_FONT_NAME not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(ARABIC_FONT_NAME, ARABIC_FONT_FILE))
    except Exception as e:
        print(f"CRITICAL: Could not register font {ARABIC_FONT_FILE}. Arabic text will not render correctly. Error: {e}")

def get_bidi_text(text):
    """
    للأسف reportlab لا تدعم BIDI تلقائياً، هذه محاولة بسيطة للتعامل مع النصوص المختلطة
    عن طريق عكس الكلمات الإنجليزية للحفاظ على السياق من اليمين لليسار.
    هذه ليست مثالية ولكنها تحسن العرض.
    """
    # Placeholder for a real BIDI algorithm if needed in the future.
    # For now, we rely on the paragraph's right-to-left alignment.
    return text

def create_questions_pdf(questions_data: dict, file_path: str) -> str:
    """
    ينشئ ملف PDF من بيانات الأسئلة المهيكلة.
    """
    register_arabic_font()
    
    doc = SimpleDocTemplate(file_path, pagesize=A4)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('ArabicTitle', parent=styles['h1'], fontName=ARABIC_FONT_NAME, fontSize=20, alignment=TA_RIGHT, spaceAfter=20)
    meta_style = ParagraphStyle('MetaStyle', parent=styles['Normal'], fontName=ARABIC_FONT_NAME, fontSize=10, alignment=TA_RIGHT)
    question_style = ParagraphStyle('QuestionStyle', parent=styles['Normal'], fontName=ARABIC_FONT_NAME, fontSize=14, alignment=TA_RIGHT, spaceBefore=10, spaceAfter=10)
    option_style = ParagraphStyle('OptionStyle', parent=styles['Normal'], fontName=ARABIC_FONT_NAME, fontSize=12, alignment=TA_RIGHT, leftIndent=20)

    story.append(Paragraph("تجميع أسئلة القدرات - بوت هدفك", title_style))
    story.append(Paragraph(f"تاريخ التجميع: {datetime.now().strftime('%Y-%m-%d %H:%M')}", meta_style))
    story.append(Spacer(1, 30))

    sorted_questions = sorted(questions_data.values(), key=lambda x: x['timestamp'])

    for i, q in enumerate(sorted_questions, 1):
        question_text = q.get('question_text', q.get('raw_content', 'لا يوجد نص للسؤال'))
        if not question_text: continue

        story.append(Paragraph(f"<b>{i}. السؤال:</b>", question_style))
        story.append(Paragraph(get_bidi_text(question_text.replace('\n', '<br/>')), question_style))
        
        if q.get('options'):
            story.append(Spacer(1, 10))
            for opt in q['options']:
                story.append(Paragraph(f"- {get_bidi_text(opt)}", option_style))

        story.append(Spacer(1, 25))

    try:
        doc.build(story)
        return file_path
    except Exception as e:
        print(f"Failed to build PDF: {e}")
        return None
