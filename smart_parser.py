import re
from typing import Dict, List

def parse_question_text(text: str) -> Dict[str, any]:
    """
    يحلل النص العادي ويحاول استخراج السؤال والخيارات.
    """
    lines = text.strip().split('\n')
    
    # Regex للتعرف على أنماط الخيارات (أ), أ-, 1., 1-, *, -)
    option_pattern = re.compile(r'^\s*([أ-ي]\s*[.)-]|[\w]\s*[.)-]|[1-9]\d*\s*[.)-]|[*•-]\s+)', re.IGNORECASE)

    question_lines = []
    option_lines = []
    
    is_reading_options = False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if option_pattern.match(line):
            is_reading_options = True
        
        common_intros = ["جاني سؤال", "جالي سؤال", "السؤال كان", "كان فيه سؤال", "سؤال اليوم"]
        if not is_reading_options and any(intro in line.lower() for intro in common_intros) and len(line) < 35:
            continue

        if is_reading_options:
            clean_option = option_pattern.sub('', line).strip()
            if clean_option:
                option_lines.append(clean_option)
        else:
            question_lines.append(line)

    if not option_lines:
        return {
            "question_text": text.strip(),
            "options": []
        }
        
    final_question = " ".join(question_lines).strip()
    final_question = re.sub(r'الخيارات هي:|الخيارات:|الاختيارات هي:|الاختيارات:$', '', final_question, flags=re.IGNORECASE).strip()
    
    return {
        "question_text": final_question,
        "options": option_lines
    }
