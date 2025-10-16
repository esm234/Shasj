import os
import html
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, BaseDocTemplate, Frame, PageTemplate, Flowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors

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

def format_arabic_text(text):
    if not isinstance(text, str): text = str(text)
    reshaped_text = arabic_reshaper.reshape(text)
    return get_display(reshaped_text)

class QuestionBox(Flowable):
    """
    Flowable مخصص لرسم صندوق السؤال الكامل بتصميمه الجديد.
    """
    def __init__(self, q_num, question_text, answer_text):
        Flowable.__init__(self)
        self.q_num = q_num
        self.question_text = question_text
        self.answer_text = answer_text
        self.box_height = 0

    def wrap(self, availWidth, availHeight):
        # تحديد الستايلات
        self.styles = getSampleStyleSheet()
        self.question_style = ParagraphStyle('q_style', parent=self.styles['Normal'], fontName=ARABIC_FONT_NAME, fontSize=11, alignment=TA_RIGHT, leading=14)
        self.answer_style = ParagraphStyle('a_style', parent=self.styles['Normal'], fontName=ARABIC_FONT_NAME, fontSize=11, alignment=TA_RIGHT, leading=14)
        
        # إنشاء الفقرات لتحديد ارتفاعها
        self.q_para = Paragraph(format_arabic_text(self.question_text), self.question_style)
        self.a_para = Paragraph(format_arabic_text(self.answer_text), self.answer_style)
        
        # حساب الارتفاع المطلوب للصندوق
        q_h = self.q_para.wrap(availWidth * 0.6, 1000)[1] # السؤال يأخذ 60% من العرض
        a_h = self.a_para.wrap(availWidth * 0.3, 1000)[1] # الإجابة تأخذ 30%
        
        self.box_height = max(q_h, a_h) + 0.8 * cm # الارتفاع هو الأعلى بين الاثنين + padding
        self.width = availWidth
        return (self.width, self.box_height)

    def draw(self):
        canvas = self.canv
        # رسم الصندوق الخلفي باللون الرمادي الفاتح والحواف الدائرية
        canvas.saveState()
        canvas.setFillColor(colors.HexColor('#f0f0f0'))
        canvas.setStrokeColor(colors.HexColor('#f0f0f0'))
        canvas.roundRect(0, 0, self.width, self.box_height, radius=4)
        
        # رسم الخط الفاصل
        separator_x = self.width * 0.75
        canvas.setStrokeColor(colors.lightgrey)
        canvas.line(separator_x, 0.2 * cm, separator_x, self.box_height - 0.2 * cm)

        # رسم رقم السؤال
        num_style = ParagraphStyle('num_style', fontName=ARABIC_FONT_NAME, fontSize=11, alignment=TA_RIGHT)
        num_para = Paragraph(format_arabic_text(f"{self.q_num}."), num_style)
        num_para.wrapOn(canvas, self.width, self.box_height)
        num_para.drawOn(canvas, self.width - 1.2 * cm, self.box_height - 0.7 * cm)

        # رسم الإجابة (الجانب الأيمن)
        self.a_para.drawOn(canvas, self.width - 1.7 * cm, (self.box_height - self.a_para.height) / 2)
        
        # رسم السؤال (الجانب الأيسر)
        self.q_para.drawOn(canvas, 0.5 * cm, (self.box_height - self.q_para.height) / 2)

        canvas.restoreState()

def create_questions_pdf(questions_data: dict, file_path: str) -> str:
    register_arabic_font()
    
    doc = BaseDocTemplate(file_path, pagesize=A4, leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)

    # تحديد إطارين للعمودين
    frame_width = (doc.width) / 2 - 0.5 * cm
    frame_height = doc.height
    
    right_frame = Frame(doc.leftMargin, doc.bottomMargin, frame_width, frame_height, id='right_col')
    left_frame = Frame(doc.leftMargin + frame_width + 1*cm, doc.bottomMargin, frame_width, frame_height, id='left_col')

    doc.addPageTemplates([PageTemplate(id='TwoCols', frames=[right_frame, left_frame])])

    story = []
    
    sorted_questions = sorted(questions_data.values(), key=lambda x: x['timestamp'])

    for i, q in enumerate(sorted_questions, 1):
        # افتراض: السؤال هو "question_text" والإجابة هي أول خيار.
        question_text = q.get('question_text') or q.get('raw_content') or " "
        answer_text = q.get('options')[0] if q.get('options') else " "
        
        safe_q = html.escape(question_text)
        safe_a = html.escape(answer_text)

        story.append(QuestionBox(i, safe_q, safe_a))
        story.append(Spacer(1, 0.2 * cm)) # مسافة صغيرة بين الصناديق

    try:
        doc.build(story)
        return file_path
    except Exception as e:
        print(f"Failed to build PDF with custom design: {e}")
        return None
