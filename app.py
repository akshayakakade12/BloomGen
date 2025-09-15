import streamlit as st
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
import os
import docx
import PyPDF2
import pandas as pd
from io import BytesIO

# =========================
# --- LOGIN / LOGOUT SYSTEM
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
# --- LOGIN PAGE
# =========================
if not st.session_state.logged_in:
    st.title("🌸 BloomGen - Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username in users and users[username]["password"] == password:
            st.session_state.logged_in = True
            st.session_state.role = users[username]["role"]
            st.success(f"✅ Logged in as {st.session_state.role}")
            st.stop()
        else:
            st.error("❌ Invalid username or password")

# =========================
# --- DASHBOARD
# =========================
else:
    st.sidebar.success(f"Logged in as {st.session_state.role}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.role = None
        st.stop()

    # --- Admin Dashboard ---
    if st.session_state.role == "Admin":
        st.header("👑 Admin Dashboard")
        st.write("Manage users, monitor activity, etc.")

    # --- Educator & Student Dashboard ---
    else:
        st.title("🌸 BloomGen - Intelligent Question & Assignment Generator")

        # ------------------------
        # Initialize LLM
        # ------------------------
        llm = ChatGroq(
            temperature=0.5,
            GROQ_API_KEY = os.getenv("GROQ_API_KEY"),  # Replace with your key
            model_name="llama3-8b-8192"
        )

        # ------------------------
        # Helper: Extract Text
        # ------------------------
        def extract_text_from_file(uploaded_file):
            text = ""
            if uploaded_file.name.endswith(".pdf"):
                reader = PyPDF2.PdfReader(uploaded_file)
                for page in reader.pages:
                    if page.extract_text():
                        text += page.extract_text() + "\n"
            elif uploaded_file.name.endswith(".docx"):
                doc = docx.Document(uploaded_file)
                for para in doc.paragraphs:
                    text += para.text + "\n"
            elif uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
                text = "\n".join(df.astype(str).values.flatten())
            elif uploaded_file.name.endswith(".txt"):
                text = uploaded_file.read().decode("utf-8")
            return text.strip()

        # ------------------------
        # Bloom’s Taxonomy Classifier
        # ------------------------
        def classify_blooms(question: str) -> str:
            keywords = {
                "Remember": ["define", "list", "state", "recall"],
                "Understand": ["explain", "summarize", "describe"],
                "Apply": ["solve", "use", "demonstrate"],
                "Analyze": ["compare", "differentiate", "examine"],
                "Evaluate": ["assess", "justify", "criticize"],
                "Create": ["design", "formulate", "construct"]
            }
            for level, words in keywords.items():
                if any(word in question.lower() for word in words):
                    return level
            return "Unclassified"

        # ------------------------
        # Generation Functions
        # ------------------------
        def generate_mcq_questions(subject, syllabus, num, example):
            prompt = ChatPromptTemplate.from_template(
                f"Generate {num} multiple-choice questions for subject {subject} based on this syllabus:\n{syllabus}\n"
                f"Use this as an example format: {example}\n"
            )
            chain = prompt | llm | StrOutputParser()
            return chain.invoke({})

        def generate_short_questions(subject, syllabus, num, example):
            prompt = ChatPromptTemplate.from_template(
                f"Generate {num} short answer questions for subject {subject} based on this syllabus:\n{syllabus}\n"
                f"Use this as an example format: {example}\n"
            )
            chain = prompt | llm | StrOutputParser()
            return chain.invoke({})

        def generate_long_questions(subject, syllabus, num, example):
            prompt = ChatPromptTemplate.from_template(
                f"Generate {num} long answer questions for subject {subject} based on this syllabus:\n{syllabus}\n"
                f"Use this as an example format: {example}\n"
            )
            chain = prompt | llm | StrOutputParser()
            return chain.invoke({})

        def generate_assignments(subject, syllabus, num, example):
            prompt = ChatPromptTemplate.from_template(
                f"Generate {num} assignments/tasks for subject {subject} based on this syllabus:\n{syllabus}\n"
                f"Use this as an example format: {example}\n"
            )
            chain = prompt | llm | StrOutputParser()
            return chain.invoke({})

        # ------------------------
        # Session State
        # ------------------------
        for key in ["mcq_questions", "short_questions", "long_questions", "assignments"]:
            if key not in st.session_state:
                st.session_state[key] = ""

        # ------------------------
        # Sidebar Layout
        # ------------------------
        logo_path = "bloomgen-high-resolution-logo.png"
        if os.path.exists(logo_path):
            st.sidebar.image(logo_path, use_container_width=True)
        else:
            st.sidebar.write("🌸 BloomGen")
        st.sidebar.header("Input Details")

        subject_name = st.sidebar.text_input("Enter Subject Name")

        uploaded_file = st.sidebar.file_uploader("Upload Syllabus (PDF/DOCX)", type=["pdf", "docx"])
        syllabus_text = ""
        if uploaded_file is not None:
            syllabus_text = extract_text_from_file(uploaded_file)
            st.sidebar.text_area("Extracted Syllabus", syllabus_text, height=200)

        # Sections
        num_mcq = st.sidebar.slider("Number of MCQs", 0, 50, 5)
        example_mcq = st.sidebar.text_area("Example MCQ format")
        mcq_file = st.file_uploader("Or upload MCQ file", type=["txt", "csv", "docx", "pdf"], key="mcq")

        num_short = st.sidebar.slider("Number of Short Questions", 0, 50, 5)
        example_short = st.sidebar.text_area("Example Short Question")
        short_file = st.file_uploader("Or upload Short Question file", type=["txt", "csv", "docx", "pdf"], key="short")

        num_long = st.sidebar.slider("Number of Long Questions", 0, 50, 3)
        example_long = st.sidebar.text_area("Example Long Question")
        long_file = st.file_uploader("Or upload Long Question file", type=["txt", "csv", "docx", "pdf"], key="long")

        num_assignments = st.sidebar.slider("Number of Assignments", 0, 20, 3)
        example_assignment = st.sidebar.text_area("Example Assignment format")
        assignment_file = st.file_uploader("Or upload Assignment file", type=["txt", "csv", "docx", "pdf"], key="assignment")

        # ------------------------
        # Generate Sections
        # ------------------------
        if st.sidebar.button("Generate MCQ Questions"):
            if mcq_file:
                st.session_state.mcq_questions = extract_text_from_file(mcq_file)
            elif subject_name and syllabus_text and example_mcq:
                st.session_state.mcq_questions = generate_mcq_questions(subject_name, syllabus_text, num_mcq, example_mcq)

            if st.session_state.mcq_questions:
                st.header("Generated MCQ Questions")
                for q in st.session_state.mcq_questions.split("\n"):
                    if q.strip():
                        st.write(f"**{q}** → {classify_blooms(q)}")
            else:
                st.sidebar.warning("❗ Provide MCQ file or details to generate")

        if st.sidebar.button("Generate Short Answer Questions"):
            if short_file:
                st.session_state.short_questions = extract_text_from_file(short_file)
            elif subject_name and syllabus_text and example_short:
                st.session_state.short_questions = generate_short_questions(subject_name, syllabus_text, num_short, example_short)

            if st.session_state.short_questions:
                st.header("Generated Short Answer Questions")
                for q in st.session_state.short_questions.split("\n"):
                    if q.strip():
                        st.write(f"**{q}** → {classify_blooms(q)}")
            else:
                st.sidebar.warning("❗ Provide Short Answer file or details to generate")

        if st.sidebar.button("Generate Long Answer Questions"):
            if long_file:
                st.session_state.long_questions = extract_text_from_file(long_file)
            elif subject_name and syllabus_text and example_long:
                st.session_state.long_questions = generate_long_questions(subject_name, syllabus_text, num_long, example_long)

            if st.session_state.long_questions:
                st.header("Generated Long Answer Questions")
                for q in st.session_state.long_questions.split("\n"):
                    if q.strip():
                        st.write(f"**{q}** → {classify_blooms(q)}")
            else:
                st.sidebar.warning("❗ Provide Long Answer file or details to generate")

        if st.sidebar.button("Generate Assignments"):
            if assignment_file:
                st.session_state.assignments = extract_text_from_file(assignment_file)
            elif subject_name and syllabus_text and example_assignment:
                st.session_state.assignments = generate_assignments(subject_name, syllabus_text, num_assignments, example_assignment)

            if st.session_state.assignments:
                st.header("Generated Assignments")
                for a in st.session_state.assignments.split("\n"):
                    if a.strip():
                        st.write(f"**{a}**")
            else:
                st.sidebar.warning("❗ Provide Assignment file or details to generate")

        # ------------------------
        # Download as DOCX
        # ------------------------
        if st.session_state.mcq_questions or st.session_state.short_questions or st.session_state.long_questions or st.session_state.assignments:
            doc = docx.Document()
            doc.add_heading("Generated Questions & Assignments", 0)

            if st.session_state.mcq_questions:
                doc.add_heading("MCQs", level=1)
                for q in st.session_state.mcq_questions.split("\n"):
                    if q.strip():
                        doc.add_paragraph(f"{q} → {classify_blooms(q)}")

            if st.session_state.short_questions:
                doc.add_heading("Short Answer Questions", level=1)
                for q in st.session_state.short_questions.split("\n"):
                    if q.strip():
                        doc.add_paragraph(f"{q} → {classify_blooms(q)}")

            if st.session_state.long_questions:
                doc.add_heading("Long Answer Questions", level=1)
                for q in st.session_state.long_questions.split("\n"):
                    if q.strip():
                        doc.add_paragraph(f"{q} → {classify_blooms(q)}")

            if st.session_state.assignments:
                doc.add_heading("Assignments", level=1)
                for a in st.session_state.assignments.split("\n"):
                    if a.strip():
                        doc.add_paragraph(a)

            buffer = BytesIO()
            doc.save(buffer)
            buffer.seek(0)

            st.download_button(
                label="📥 Download Questions & Assignments as DOCX",
                data=buffer,
                file_name="generated_content.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
