# 📊 Excel Interviewer Backend

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg?logo=python)](https://www.python.org/)  
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi)](https://fastapi.tiangolo.com/)  
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-AI-orange?logo=google)](https://ai.google.dev/)  

FastAPI backend for an **AI-powered Excel skills assessment platform**.  
Provides intelligent interview evaluation, session management, and PDF report generation.

---

## 🚀 Features

- ⚡ **FastAPI** with automatic OpenAPI documentation  
- 🤖 **Google Gemini AI** integration for answer evaluation  
- 📊 **Hybrid scoring system** (keyword + semantic analysis)  
- 📄 **PDF report generation** with detailed analytics  
- 💾 **Session management** for interview progression  
- 🎯 **Structured interview flow** with state management  

---

## 🛠️ Tech Stack

- **Framework**: FastAPI  
- **AI/ML**: Google Generative AI (Gemini 2.5 Flash)  
- **PDF Generation**: ReportLab  
- **Validation**: Pydantic  
- **Environment**: python-dotenv  

---

## ⚙️ Installation

### Prerequisites
- Python **3.8+**
- Google Gemini API key

### Setup
```bash
# Clone repository
git clone <repository-url>
cd excel-interviewer-backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Add your GEMINI_API_KEY to .env
GEMINI_API_KEY=your_gemini_api_key_here

```

| Method | Endpoint           | Description                         |
| ------ | ------------------ | ----------------------------------- |
| POST   | `/start_interview` | Initialize new interview session    |
| POST   | `/next_question`   | Submit answer and get next question |
| GET    | `/feedback`        | Get performance summary             |
| GET    | `/download_report` | Generate detailed PDF report        |


## 📋 Request/Response Examples

## ▶️ Start Interview

```bash
curl -X POST "http://localhost:8000/start_interview?session_id=123"
```
```bash
{
  "message": "Interview started",
  "first_question": "What does the SUM function do in Excel?"
}
```
## 📝 Submit Answer
```bash
curl -X POST "http://localhost:8000/next_question" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "123",
    "answer": "SUM adds numbers in a range"
  }'
```
## 📚 Question Bank Structure
Questions are stored in questions.json with the following format:

```bash
[
  {
    "level": "beginner",
    "question": "What does the SUM function do in Excel?",
    "keywords": ["sum", "add", "range", "numbers"]
  }
]
```

## 🎯 Evaluation System
#Hybrid Scoring
Keyword Matching: Rule-based scoring using predefined keywords
Semantic Analysis: AI-powered understanding of answer quality
Combined Score: Weighted combination for final evaluation

##📑 PDF Report Features
* Candidate information section
* Performance summary with scores
* Detailed question analysis
* AI-generated recommendations
* Professional formatting

## 💻 Development
Running Locally
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API Documentation
Swagger UI → [http://localhost:8000/docs](url)
ReDoc → [http://localhost:8000/redoc](url)
