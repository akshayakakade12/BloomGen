# 🌸 BloomGen

BloomGen is an AI-powered academic platform that generates question papers, assignments, and question banks based on syllabus input and aligned with Bloom’s Taxonomy levels.
It helps educators save time while ensuring balanced assessments across cognitive learning objectives.


# ✨ Features

📄 Syllabus Ingestion – paste syllabus text, auto-extract key topics & summaries.
❓ AI Question Generator – create questions aligned with Bloom’s Taxonomy.
🎯 Bloom’s Classification – auto-classify questions into Remember, Understand, Apply, Analyze, Evaluate, Create.
📑 Paper Assembly – build structured question papers or assignments.
📤 Export Options – download in PDF/Word formats.
💻 Frontend (React + Tailwind) for interactive UI (planned).
⚡ Backend (FastAPI + Deep Learning) powering question generation & classification.

## Directory Structure

```bash
BloomGen/
├── app.py
├── requirements.txt
├── LICENSE
├── Logo.png
└── README.md
```

- `app.py`: The main application script that runs the Streamlit app.
- `requirements.txt`: Lists the Python dependencies required to run the application.
- `LICENSE`: Contains the licensing information for the project.
- `Logo.png`: The logo image used in the application.
- `README.md`: Provides an overview and instructions for the project.


## 🔧 Technology Stack
- **Backend**: Python (Streamlit prototype, FastAPI planned), Deep Learning models.
- **Frontend**: React + Tailwind (under development).
- **Libraries**: Hugging Face Transformers, NLTK, ReportLab, Scikit-learn.

## 🎯 Current Status
- ✅ Prototype working in **Streamlit**.
- 🚧 Migration to **FastAPI backend** in progress.
- 🚧 React + Tailwind frontend under development.

## 📌 Usage (Prototype)
Run the Streamlit app:
```bash
streamlit run app.py
>>>>>>> 1df1aea (Initial commit of BloomGen app)
