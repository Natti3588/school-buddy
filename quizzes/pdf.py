# 印刷用PDFを作る（ReportLab を使用。UI担当から渡された pdf_maker.py を DB のテストで動くようにしたもの）
# 日本語フォント：quizzes/fonts の「BIZ UD明朝／BIZ UDPゴシック」をPDFに埋め込む
#   ・BIZ UD は教育向けに作られた読みやすいフォント（SIL Open Font License・無料）
#   ・埋め込むので、どのパソコン・プリンターでも同じ見た目になる
#   ・フォントファイルが無いときは ReportLab 内蔵のフォントを使う（表示は閲覧ソフトまかせ）

import io
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import QuestionType, circled_number

# 出力できる用紙の種類
SHEETS = {"question": "問題用紙", "answer": "解答用紙", "key": "模範解答"}

FONT_DIR = Path(__file__).resolve().parent / "fonts"
try:
    pdfmetrics.registerFont(TTFont("UDMincho", FONT_DIR / "BIZUDPMincho-Regular.ttf"))  # 本文
    pdfmetrics.registerFont(TTFont("UDGothic", FONT_DIR / "BIZUDPGothic-Bold.ttf"))  # 見出し
    MIN, GOTHIC = "UDMincho", "UDGothic"
except Exception:
    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiMin-W3"))
    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
    MIN, GOTHIC = "HeiseiMin-W3", "HeiseiKakuGo-W5"

RED = colors.HexColor("#c62d3c")
LINE = colors.HexColor("#555555")

ST_TITLE = ParagraphStyle("title", fontName=GOTHIC, fontSize=16, leading=22, alignment=1)
ST_SUB = ParagraphStyle("sub", fontName=MIN, fontSize=10, leading=14, alignment=1)
ST_SEC = ParagraphStyle(
    "sec", fontName=GOTHIC, fontSize=11.5, leading=17, spaceBefore=10, spaceAfter=4, wordWrap="CJK"
)
ST_Q = ParagraphStyle(
    "q", fontName=MIN, fontSize=10.5, leading=17, leftIndent=14, firstLineIndent=-14, wordWrap="CJK"
)
ST_BODY = ParagraphStyle("body", fontName=MIN, fontSize=10.5, leading=17, wordWrap="CJK")
ST_SMALL = ParagraphStyle("small", fontName=MIN, fontSize=9, leading=12, wordWrap="CJK")
ST_ANS = ParagraphStyle("ans", parent=ST_BODY, textColor=RED, fontName=GOTHIC)

def esc(text):
    # Paragraph は簡単なHTMLとして読むので、< > & を変換しておく
    # 全角スペースは詰められてしまうので、詰められない空白（NBSP）に置きかえる
    text = (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return text.replace("　", " " * 4).replace("\r\n", "\n").replace("\n", "<br/>")


def header(quiz, sheet, school_year, total):
    # 上部：タイトル・制限時間・クラス／氏名欄・点数欄
    title = f"{school_year}年度　{quiz.get_subject_display()}　{quiz.title}"
    if sheet != "question":
        title += f"（{SHEETS[sheet]}）"

    name_box = Table(
        [[Paragraph(esc("　　年　　組　　番"), ST_BODY), Paragraph("氏名", ST_BODY), "",
          Paragraph("点数", ST_BODY), Paragraph(f"／{total}", ST_BODY)]],
        colWidths=[50 * mm, 12 * mm, 60 * mm, 14 * mm, 28 * mm], rowHeights=[12 * mm],
    )
    name_box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, LINE),
        ("LINEBEFORE", (1, 0), (1, 0), 0.5, LINE),
        ("LINEBEFORE", (3, 0), (3, 0), 0.8, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (4, 0), (4, 0), "RIGHT"),
    ]))
    story = [Paragraph(esc(title), ST_TITLE), Spacer(1, 2 * mm)]
    # 制限時間は入力しなくてもよいので、あるときだけ出す
    if quiz.minutes:
        story.append(Paragraph(f"制限時間：{quiz.minutes}分", ST_SUB))
    return story + [Spacer(1, 4 * mm), name_box, Spacer(1, 4 * mm)]


def section_title(number, section, questions):
    text = f"{number}　{esc(section.instruction)}"
    if section.words:
        text += f"（{esc(section.words)}）"
    points = sum(q.points for q in questions)
    return Paragraph(f"{text}　<font size=9>（{points}点）</font>", ST_SEC)


def boxed(text, style=ST_BODY):
    # 枠で囲んだ文章（読解の本文・リスニングの注意など）
    box = Table([[Paragraph(text, style)]], colWidths=[170 * mm])
    box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return box


def question_sheet(sections):
    # 問題用紙：問題文・選択肢・本文
    story = []
    for number, section, questions in sections:
        block = [section_title(number, section, questions)]
        if section.qtype == QuestionType.LISTENING:
            block.append(boxed("※ 放送を聞いて答えます。英文は2回読まれます。", ST_SMALL))
            block.append(Spacer(1, 2 * mm))
        if section.qtype == QuestionType.READING and section.passage:
            block.append(boxed(esc(section.passage)))
            block.append(Spacer(1, 2 * mm))
        for n, question in enumerate(questions, start=1):
            if question.text:
                block.append(Paragraph(f"({n})　{esc(question.text)}", ST_Q))
            if section.uses_choices():
                # 選択肢は4列の表で横にならべる
                cells = [
                    Paragraph(f"{symbol}  {esc(choice.text)}", ST_BODY)
                    for symbol, choice in question.symbol_choices()
                ]
                row = Table([cells], colWidths=[40 * mm] * len(cells), hAlign="LEFT")
                row.setStyle(TableStyle([("LEFTPADDING", (0, 0), (0, 0), 14 * mm / 2)]))
                block.append(row)
            block.append(Spacer(1, 2 * mm))
        story.append(KeepTogether(block))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("答えはすべて解答用紙に書きなさい。", ST_SMALL))
    return story


def answer_sheet(sections, show_answer):
    # 解答用紙／模範解答：大問ごとに解答欄の表を作る
    story = []
    for number, section, questions in sections:
        rows = []
        for n, question in enumerate(questions, start=1):
            answer = question.correct_symbol() if section.uses_choices() else question.answer
            rows.append([
                Paragraph(f"({n})", ST_BODY),
                Paragraph(esc(answer), ST_ANS) if show_answer else "",
                Paragraph(f"{question.points}点", ST_SMALL),
            ])
        # 記述式・読解は解答欄を大きくする
        height = (24 if section.is_manual() else 12) * mm
        table = Table(rows, colWidths=[14 * mm, 136 * mm, 20 * mm], rowHeights=[height] * len(rows))
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.6, LINE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (2, 0), (2, -1), "CENTER"),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f2f2f2")),
        ]))
        story.append(KeepTogether([section_title(number, section, questions), table]))
    return story


def make_quiz_pdf(quiz, sheet, school_year):
    """テストを PDF にする。sheet：question（問題用紙）/ answer（解答用紙）/ key（模範解答）"""
    # 大問ごとに小問と選択肢をまとめて取得しておく（小問ごとに SQL を出さない）
    sections = [
        (circled_number(n), section, list(section.questions.all()))
        for n, section in enumerate(quiz.sections.prefetch_related("questions__choices"), start=1)
    ]
    total = sum(q.points for _, _, questions in sections for q in questions)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
        title=f"{quiz.title} {SHEETS[sheet]}", author="放課GO",
    )
    story = header(quiz, sheet, school_year, total)
    if sheet == "question":
        story += question_sheet(sections)
    else:
        story += answer_sheet(sections, show_answer=(sheet == "key"))
    doc.build(story)
    return buf.getvalue()
