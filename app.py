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
    # Question Generator (TPM-safe)
    # =========================
    def generate_questions(subject, syllabus, count):
        # 1) Split large syllabus
        chunks = split_syllabus(syllabus, chunk_size=2400, chunk_overlap=200)

        # 2) Summarize chunks to reduce tokens
        summaries = []
        for ch in chunks[:6]:  # cap to control cost/TPM
            summaries.append(summary_chain.invoke({"syllabus": ch}))

        syllabus_summary = safe_join(summaries)

        # 3) Question generation chain (concise output)
        prompt = ChatPromptTemplate.from_template("""
You are an academic question paper setter.

Generate exactly {count} university-level descriptive questions.

Subject: {subject}

STRICT OUTPUT RULES (must follow):
- Output ONLY questions.
- One question per line.
- No numbering (no Q1/Q2), no bullets, no headings.
- No blank lines.
- Each question should start with an action verb like: Explain/Describe/Analyze/Evaluate/Compare/Design/Implement.

Syllabus Summary:
{syllabus}
""")

        chain = prompt | llm | StrOutputParser()

        # 4) Generate in batches to avoid large requests
        batch_size = 6
        rounds = math.ceil(count / batch_size)

        outputs = []
        for i in range(rounds):
            this_batch = batch_size if i < rounds - 1 else (count - batch_size * i)
            out = chain.invoke({
                "subject": subject,
                "syllabus": syllabus_summary,
                "count": this_batch
            })
            outputs.append(out)

        return safe_join(outputs, sep="\n")

    # =========================
    # Bloom Classifier
    # =========================
    def classify_blooms(question):
        keywords = {
            "Remember": ["define", "list", "state", "name"],
            "Understand": ["explain", "describe", "summarize"],
            "Apply": ["solve", "demonstrate", "implement"],
            "Analyze": ["analyze", "compare", "differentiate"],
            "Evaluate": ["evaluate", "justify", "argue"],
            "Create": ["design", "develop", "construct"]
        }

        q_lower = question.lower()
        for level, words in keywords.items():
            if any(word in q_lower for word in words):
                return level

        return "Understand"

    # =========================
    # DOCX Generator
    # =========================
    def generate_university_docx(data_dict, questions_list):

        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(BASE_DIR, "templates", "assignment_template.docx")

        doc = Document(template_path)

        # Replace placeholders in paragraphs
        for paragraph in doc.paragraphs:
            for key, value in data_dict.items():
                paragraph.text = paragraph.text.replace(key, str(value))

        # Find question table
        question_table = None
        for table in doc.tables:
            if table.rows and "Question No." in table.rows[0].cells[0].text:
                question_table = table
                break

        if question_table:
            q_no = 1
            for q in questions_list:
                q = q.strip()
                if not q:
                    continue

                row = question_table.add_row().cells
                row[0].text = f"Q{q_no}"
                row[1].text = q
                row[2].text = "3"
                row[3].text = "1,2"
                row[4].text = classify_blooms(q)
                row[5].text = "05"
                q_no += 1

        output_path = os.path.join(BASE_DIR, "University_Assignment.docx")
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
    question_count = st.sidebar.slider("Number of Questions", 1, 20, 5)

    uploaded_file = st.file_uploader("Upload Syllabus (PDF/DOCX)")

    # =========================
    # Generate Button
    # =========================
    if uploaded_file and st.button("🚀 Generate & Format Assignment"):

        syllabus_text = extract_text(uploaded_file)

        if not subject:
            st.error("Please enter subject name")
            st.stop()

        with st.spinner("Generating questions..."):
            questions_raw = generate_questions(
                subject,
                syllabus_text,
                question_count
            )

        # Clean and parse questions (remove bullets if any)
        questions_list = []
        for line in questions_raw.split("\n"):
            q = line.strip().lstrip("-•").strip()
            if q:
                questions_list.append(q)

        today = datetime.date.today()
        # Ensure exact number of questions
questions_list = questions_list[:question_count]
while len(questions_list) < question_count:
    questions_list.append("Explain a relevant concept from the given syllabus.")
        
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
            "{{SUBMISSION_DATE}}": today
        }

        file_path = generate_university_docx(data, questions_list)

        with open(file_path, "rb") as f:
            st.download_button(
                label="⬇ Download University Assignment",
                data=f,
                file_name="University_Assignment.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )