import streamlit as st
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os
import math
import docx
import PyPDF2
from docx import Document
import datetime
from dotenv import load_dotenv

# DOCX formatting helpers
from docx.shared import Pt
from docx.enum.text import WD_LINE_SPACING
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

import pandas as pd

load_dotenv()

# =========================
# LOGIN SYSTEM
# =========================
users = {
    "admin": {"password": "admin123", "role": "Admin"},
    "educator": {"password": "edu123", "role": "Educator"},
    "student": {"password": "stu123", "role": "Student"}
}

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "role" not in st.session_state:
    st.session_state.role = None

# Preview cache
if "preview_rows" not in st.session_state:
    st.session_state.preview_rows = None
if "generated_docx_path" not in st.session_state:
    st.session_state.generated_docx_path = None

# =========================
# LOGIN PAGE
# =========================
if not st.session_state.logged_in:

    st.title("🌸 BloomGen - Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username in users and users[username]["password"] == password:
            st.session_state.logged_in = True
            st.session_state.role = users[username]["role"]
            st.success(f"Logged in as {st.session_state.role}")
            st.rerun()
        else:
            st.error("Invalid credentials")

# =========================
# DASHBOARD
# =========================
else:
    st.title("🌸 BloomGen - AI University Assignment Generator")
    st.sidebar.success(f"Logged in as {st.session_state.role}")

    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.role = None
        st.session_state.preview_rows = None
        st.session_state.generated_docx_path = None
        st.rerun()

    # =========================
    # LLM Setup (TPM-safe)
    # =========================
    llm = ChatGroq(
        groq_api_key=os.getenv("GROQ_API_KEY"),
        model_name="openai/gpt-oss-120b",
        temperature=0.4,
        max_tokens=1200
    )

    # =========================
    # File Text Extraction
    # =========================
    def extract_text(uploaded_file):
        text = ""
        if uploaded_file is None:
            return text

        filename = uploaded_file.name.lower()

        if filename.endswith(".pdf"):
            reader = PyPDF2.PdfReader(uploaded_file)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

        elif filename.endswith(".docx"):
            doc = docx.Document(uploaded_file)
            for para in doc.paragraphs:
                text += para.text + "\n"

        return text

    # =========================
    # Syllabus Chunking Helpers
    # =========================
    def split_syllabus(text: str, chunk_size: int = 2400, chunk_overlap: int = 200):
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        return splitter.split_text(text or "")

    def safe_join(parts, sep="\n\n"):
        return sep.join([p for p in parts if p and p.strip()])

    # =========================
    # Summary Chain (compress syllabus)
    # =========================
    summary_prompt = ChatPromptTemplate.from_template("""
You are helping create university exam/assignment questions.

Summarize the syllabus into compact bullet points (max 350 words).
Keep only exam-relevant units/topics/subtopics/keywords.
No extra explanation.

SYLLABUS:
{syllabus}
""")
    summary_chain = summary_prompt | llm | StrOutputParser()

    # =========================
    # Bloom Count Helper
    # =========================
    def compute_bloom_counts(total_questions: int, pct_u: int, pct_a: int, pct_ae: int):
        u = round(total_questions * pct_u / 100)
        a = round(total_questions * pct_a / 100)
        ae = total_questions - u - a
        return {
            "Understand": max(0, u),
            "Apply": max(0, a),
            "Analyze/Evaluate": max(0, ae)
        }

    # =========================
    # Question Generator (Bloom-distributed, TPM-safe)
    # Returns: list of tuples [(question, bloom_label), ...]
    # =========================
    def generate_questions(subject, syllabus, count, pct_u, pct_a, pct_ae):
        chunks = split_syllabus(syllabus, chunk_size=2400, chunk_overlap=200)

        summaries = []
        for ch in chunks[:6]:
            summaries.append(summary_chain.invoke({"syllabus": ch}))
        syllabus_summary = safe_join(summaries)

        bloom_counts = compute_bloom_counts(count, pct_u, pct_a, pct_ae)

        bloom_prompt = ChatPromptTemplate.from_template("""
You are an academic question paper setter.

Generate exactly {count} university-level descriptive questions.

Subject: {subject}
Bloom Bucket: {bloom_bucket}

STRICT OUTPUT RULES:
- Output ONLY questions.
- One question per line.
- No numbering, no bullets, no headings, no blank lines.
- Keep questions exam-oriented and concise.
- Use action verbs that match the Bloom bucket:
  - Understand: Explain, Describe, Illustrate, Summarize
  - Apply: Solve, Demonstrate, Implement, Apply
  - Analyze/Evaluate: Analyze, Compare, Differentiate, Evaluate, Justify

Syllabus Summary (use ONLY this):
{syllabus}
""")
        bloom_chain = bloom_prompt | llm | StrOutputParser()

        batch_size = 6
        final_pairs = []

        for bloom_bucket, bucket_count in bloom_counts.items():
            if bucket_count <= 0:
                continue

            rounds = math.ceil(bucket_count / batch_size)

            for i in range(rounds):
                this_batch = batch_size if i < rounds - 1 else (bucket_count - batch_size * i)

                out = bloom_chain.invoke({
                    "subject": subject,
                    "syllabus": syllabus_summary,
                    "count": this_batch,
                    "bloom_bucket": bloom_bucket
                })

                for line in out.split("\n"):
                    q = line.strip().lstrip("-•").strip()
                    if q:
                        final_pairs.append((q, bloom_bucket))

        return final_pairs[:count]

    # =========================
    # CO / PO / Marks Helpers
    # =========================
    def assign_co(index: int, total_cos: int) -> str:
        return f"CO{(index % total_cos) + 1}" if total_cos > 0 else ""

    def assign_po(index: int, total_pos: int) -> str:
        return f"PO{(index % total_pos) + 1}" if total_pos > 0 else ""

    def marks_for_bloom(bloom_label: str, m_u: int, m_a: int, m_ae: int) -> str:
        if bloom_label == "Understand":
            return str(m_u)
        if bloom_label == "Apply":
            return str(m_a)
        return str(m_ae)

    # =========================
    # DOCX Formatting Helpers
    # =========================
    DOC_FONT_NAME = "Calibri"
    DOC_FONT_SIZE_PT = 11
    ROW_HEIGHT_PT = 24

    def set_cell_text(cell, text: str, bold: bool = False):
        cell.text = ""
        p = cell.paragraphs[0]

        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
        p.paragraph_format.line_spacing = 1.0

        run = p.add_run(text)
        run.bold = bold
        run.font.name = DOC_FONT_NAME
        run.font.size = Pt(DOC_FONT_SIZE_PT)

        rPr = run._element.get_or_add_rPr()
        rFonts = rPr.find(qn("w:rFonts"))
        if rFonts is None:
            rFonts = OxmlElement("w:rFonts")
            rPr.append(rFonts)
        rFonts.set(qn("w:ascii"), DOC_FONT_NAME)
        rFonts.set(qn("w:hAnsi"), DOC_FONT_NAME)

        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

    def set_row_height(row, height_pt: int):
        tr = row._tr
        trPr = tr.get_or_add_trPr()
        trHeight = OxmlElement("w:trHeight")
        trHeight.set(qn("w:val"), str(int(height_pt * 20)))  # twips
        trHeight.set(qn("w:hRule"), "exact")
        trPr.append(trHeight)

    # =========================
    # DOCX Generator (PCU mapping)
    # Columns: QNo | Statement | CO | PO | Bloom | Marks
    # =========================
    def generate_university_docx(
        data_dict,
        questions_list,
        bloom_labels,
        total_cos,
        total_pos,
        m_u,
        m_a,
        m_ae
    ):
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(BASE_DIR, "templates", "assignment_template.docx")

        doc = Document(template_path)

        # Replace placeholders in paragraphs
        for paragraph in doc.paragraphs:
            for key, value in data_dict.items():
                if key in paragraph.text:
                    paragraph.text = paragraph.text.replace(key, str(value))

        # Find question table
        question_table = None
        for table in doc.tables:
            if table.rows and "Question No." in table.rows[0].cells[0].text:
                question_table = table
                break

        if question_table:
            q_no = 1
            for idx, q in enumerate(questions_list):
                q = q.strip()
                if not q:
                    continue

                bloom_label = bloom_labels[idx] if idx < len(bloom_labels) else "Understand"

                new_row = question_table.add_row()
                set_row_height(new_row, ROW_HEIGHT_PT)
                cells = new_row.cells

                set_cell_text(cells[0], f"Q{q_no}")
                set_cell_text(cells[1], q)
                set_cell_text(cells[2], assign_co(idx, total_cos))
                set_cell_text(cells[3], assign_po(idx, total_pos))
                set_cell_text(cells[4], bloom_label)
                set_cell_text(cells[5], marks_for_bloom(bloom_label, m_u, m_a, m_ae))

                q_no += 1

        # Output doc name (do NOT overwrite template)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        safe_subject = "".join([c for c in (data_dict.get("{{SUBJECT}}", "") or "Subject") if c.isalnum() or c in (" ", "_", "-")]).strip()
        safe_subject = safe_subject.replace(" ", "_")[:40] or "Subject"

        output_path = os.path.join(BASE_DIR, f"University_Assignment_{safe_subject}_{timestamp}.docx")
        doc.save(output_path)
        return output_path

    # =========================
    # Sidebar Inputs
    # =========================
    st.sidebar.header("Assignment Details")

    subject = st.sidebar.text_input("Subject")
    department = st.sidebar.text_input("Department", "CSE")
    semester = st.sidebar.text_input("Semester", "VIII")
    academic_year = st.sidebar.text_input("Academic Year", "2025-26")
    year_div = st.sidebar.text_input("Year & Div", "B.TECH")
    assignment_no = st.sidebar.text_input("Assignment No", "03")
    teacher_name = st.sidebar.text_input("Teacher Name")
    max_marks = st.sidebar.text_input("Max Marks", "60")

    subject_incharge = st.sidebar.text_input("Subject Incharge (optional)")
    academic_coordinator = st.sidebar.text_input("Academic Coordinator (optional)")
    hod_name = st.sidebar.text_input("HOD Name (optional)")

    question_count = st.sidebar.slider("Number of Questions", 1, 20, 5)

    st.sidebar.subheader("Bloom Distribution (%)")
    pct_understand = st.sidebar.slider("Understand %", 0, 100, 30)
    pct_apply = st.sidebar.slider("Apply %", 0, 100, 30)
    pct_analyze_eval = st.sidebar.slider("Analyze/Evaluate %", 0, 100, 40)

    total_pct = pct_understand + pct_apply + pct_analyze_eval
    if total_pct == 0:
        pct_understand, pct_apply, pct_analyze_eval = 30, 30, 40
        total_pct = 100

    pct_understand = round((pct_understand / total_pct) * 100)
    pct_apply = round((pct_apply / total_pct) * 100)
    pct_analyze_eval = 100 - pct_understand - pct_apply

    st.sidebar.caption(
        f"Final split: Understand {pct_understand}%, Apply {pct_apply}%, Analyze/Evaluate {pct_analyze_eval}%"
    )

    st.sidebar.subheader("CO / PO / Marks")
    total_cos = st.sidebar.number_input("Total COs", min_value=1, max_value=20, value=6, step=1)
    total_pos = st.sidebar.number_input("Total POs", min_value=1, max_value=20, value=12, step=1)

    m_understand = st.sidebar.number_input("Marks for Understand", min_value=1, max_value=20, value=3, step=1)
    m_apply = st.sidebar.number_input("Marks for Apply", min_value=1, max_value=20, value=5, step=1)
    m_analyze_eval = st.sidebar.number_input("Marks for Analyze/Evaluate", min_value=1, max_value=20, value=7, step=1)

    st.sidebar.subheader("PCU Formatting")
    DOC_FONT_NAME = st.sidebar.selectbox("Font", ["Calibri", "Times New Roman", "Arial"], index=0)
    DOC_FONT_SIZE_PT = st.sidebar.slider("Font Size", 9, 14, 11)
    ROW_HEIGHT_PT = st.sidebar.slider("Row Height (pt)", 16, 40, 24)

    uploaded_file = st.file_uploader("Upload Syllabus (PDF/DOCX)")

    # =========================
    # MAIN UI: Preview + Download
    # =========================
    col1, col2 = st.columns(2)

    with col1:
        generate_preview = st.button("👀 Generate Preview")
    with col2:
        clear_preview = st.button("🧹 Clear Preview")

    if clear_preview:
        st.session_state.preview_rows = None
        st.session_state.generated_docx_path = None
        st.rerun()

    if uploaded_file and generate_preview:
        syllabus_text = extract_text(uploaded_file)

        if not subject:
            st.error("Please enter subject name")
            st.stop()

        with st.spinner("Generating preview..."):
            pairs = generate_questions(
                subject,
                syllabus_text,
                question_count,
                pct_understand,
                pct_apply,
                pct_analyze_eval
            )

        questions_list = [q for (q, b) in pairs][:question_count]
        bloom_labels = [b for (q, b) in pairs][:question_count]

        while len(questions_list) < question_count:
            questions_list.append("Explain a relevant concept from the given syllabus.")
            bloom_labels.append("Understand")

        # Build preview rows (PCU table columns)
        rows = []
        for i, q in enumerate(questions_list, start=1):
            bloom = bloom_labels[i - 1]
            rows.append({
                "Question No.": f"Q{i}",
                "Question Statement": q,
                "CO": assign_co(i - 1, int(total_cos)),
                "PO": assign_po(i - 1, int(total_pos)),
                "Bloom’s Level": bloom,
                "Marks": marks_for_bloom(bloom, int(m_understand), int(m_apply), int(m_analyze_eval))
            })

        st.session_state.preview_rows = rows

        # Also generate DOCX now so download is instant
        today = datetime.date.today()
        data = {
            "{{DEPARTMENT}}": department,
            "{{SEMESTER}}": semester,
            "{{ACADEMIC_YEAR}}": academic_year,
            "{{YEAR_DIV}}": year_div,
            "{{MAX_MARKS}}": max_marks,
            "{{SUBJECT}}": subject,
            "{{ASSIGNMENT_NO}}": assignment_no,
            "{{TEACHER_NAME}}": teacher_name,
            "{{DATE}}": today,
            "{{SUBMISSION_DATE}}": today,
            "{{SUBJECT_INCHARGE}}": subject_incharge,
            "{{ACADEMIC_COORDINATOR}}": academic_coordinator,
            "{{HOD_NAME}}": hod_name
        }

        docx_path = generate_university_docx(
            data,
            questions_list,
            bloom_labels,
            int(total_cos),
            int(total_pos),
            int(m_understand),
            int(m_apply),
            int(m_analyze_eval)
        )
        st.session_state.generated_docx_path = docx_path

    # Show preview if available
    if st.session_state.preview_rows:
        st.subheader("📋 Preview (PCU Table)")
        df = pd.DataFrame(st.session_state.preview_rows)
        st.dataframe(df, use_container_width=True)

        st.success("Preview ready. If it looks good, download below 👇")

        if st.session_state.generated_docx_path:
            with open(st.session_state.generated_docx_path, "rb") as f:
                st.download_button(
                    label="⬇ Download University Assignment DOCX",
                    data=f,
                    file_name=os.path.basename(st.session_state.generated_docx_path),
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
    else:
        st.info("Upload a syllabus and click **Generate Preview** to see the table before downloading.")