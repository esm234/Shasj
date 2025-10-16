import os, html
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
import arabic_reshaper
from bidi.algorithm import get_display


# --- إعدادات الخط العربي ---
ARABIC_FONT_NAME = "Amiri-Regular"
ARABIC_FONT_FILE = "Amiri-Regular.ttf"

def register_arabic_font():
    if ARABIC_FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(ARABIC_FONT_NAME, ARABIC_FONT_FILE))


# --- الهيدر والفوتر ---
def draw_header_footer(canvas, doc):
    canvas.saveState()

    header_text = "تجميعات القدرات - بوت هدفك"
    reshaped_header = arabic_reshaper.reshape(header_text)
    bidi_header = get_display(reshaped_header)
    canvas.setFont(ARABIC_FONT_NAME, 12)
    canvas.drawCentredString(A4[0] / 2, A4[1] - 2 * cm, bidi_header)

    canvas.setStrokeColorRGB(0, 0, 0)
    canvas.line(1 * cm, A4[1] - 2.5 * cm, A4[0] - 1 * cm, A4[1] - 2.5 * cm)

    page_num_text = f"صفحة {doc.page}"
    reshaped_footer = arabic_reshaper.reshape(page_num_text)
    bidi_footer = get_display(reshaped_footer)
    canvas.setFont(ARABIC_FONT_NAME, 9)
    canvas.drawCentredString(A4[0] / 2, 1.5 * cm, bidi_footer)

    canvas.restoreState()


# --- دالة تنسيق النص العربي ---
def format_arabic_text(text):
    if not text:
        return ""
    return get_display(arabic_reshaper.reshape(text))


# --- إنشاء ملف PDF ---
def create_questions_pdf(questions_data: dict, file_path: str) -> str:
    register_arabic_font()

    doc = BaseDocTemplate(file_path, pagesize=A4)
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height - 2 * cm, id='normal')
    template = PageTemplate(id='main_template', frames=[frame], onPage=draw_header_footer)
    doc.addPageTemplates([template])

    styles = getSampleStyleSheet()
    question_style = ParagraphStyle(
        'QuestionStyle',
        parent=styles['Normal'],
        fontName=ARABIC_FONT_NAME,
        fontSize=14,
        alignment=TA_RIGHT,
        leading=22,
        spaceAfter=10
    )

    option_style = ParagraphStyle(
        'OptionStyle',
        parent=styles['Normal'],
        fontName=ARABIC_FONT_NAME,
        fontSize=12,
        alignment=TA_CENTER,
        leading=18,
    )

    story = []

    # ألوان المربعات الأربعة (زي الصورة)
    option_colors = [
        colors.HexColor("#E6F0FF"),  # لبني فاتح
        colors.HexColor("#E8F5E9"),  # أخضر فاتح
        colors.HexColor("#F3E5F5"),  # بنفسجي فاتح
        colors.HexColor("#FFFDE7"),  # أصفر باهت
    ]

    sorted_questions = sorted(questions_data.values(), key=lambda x: x['timestamp'])

    for i, q in enumerate(sorted_questions, 1):
        question_text = html.escape(q.get('question_text') or q.get('raw_content') or "(سؤال بدون نص)")
        story.append(Paragraph(format_arabic_text(f"{i}) {question_text}"), question_style))
        story.append(Spacer(1, 5))

        options = q.get('options', [])
        if options:
            option_cells = []
            for j, opt in enumerate(options[:4]):
                safe_opt = html.escape(opt)
                cell = Paragraph(format_arabic_text(safe_opt), option_style)
                option_cells.append(cell)

            # نرتبهم أفقياً داخل جدول
            t = Table([option_cells], colWidths=[doc.width / 4.3] * len(option_cells))
            ts = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), None),
                ('BOX', (0, 0), (-1, 0), 0.5, colors.gray),
                ('INNERGRID', (0, 0), (-1, 0), 0.5, colors.gray),
                ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            ])

            # نضيف لون مختلف لكل خلية
            for c, color in enumerate(option_colors):
                ts.add('BACKGROUND', (c, 0), (c, 0), color)

            t.setStyle(ts)
            story.append(t)

        story.append(Spacer(1, 20))

    doc.build(story)
    return file_path


# --- مثال للتجربة ---
if __name__ == "__main__":
    sample_data = {
        "q1": {
            "question_text": "أي من التالي يعد من خصائص المخلوقات الحية؟",
            "options": ["التكاثر", "الصلابة", "الذوبان", "الخمول"],
            "timestamp": 1
        },
        "q2": {
            "question_text": "ما عاصمة المملكة العربية السعودية؟",
            "options": ["الرياض", "جدة", "مكة", "الدمام"],
            "timestamp": 2
        }
    }

    path = "quiz_output.pdf"
    create_questions_pdf(sample_data, path)
    print("✅ تم إنشاء الملف:", path)

