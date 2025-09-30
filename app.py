from fastapi import FastAPI
from pydantic import BaseModel
import random, json, os
import google.generativeai as genai
from dotenv import load_dotenv 
from fastapi.responses import FileResponse
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import tempfile
from datetime import datetime

load_dotenv()
# --- Gemini Setup ---
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash")

app = FastAPI()

# Load pre-generated question bank
with open("questions.json", "r") as f:
    QUESTION_BANK = json.load(f)

# In-memory session storage (for PoC)
sessions = {}

class AnswerRequest(BaseModel):
    session_id: str
    answer: str

@app.post("/start_interview")
def start_interview(session_id: str):
    questions = random.sample(QUESTION_BANK, 5)
    sessions[session_id] = {"questions": questions, "current": 0, "answers": [], "score": 0}
    return {"message": "Interview started", "first_question": questions[0]["question"]}

@app.post("/next_question")
def next_question(req: AnswerRequest):
    session = sessions[req.session_id]
    current_q = session["questions"][session["current"]]
    user_answer = req.answer.lower()

    # --- Rule-based evaluation ---
    keyword_score = sum(1 for kw in current_q["keywords"] if kw in user_answer)

    # --- Gemini semantic evaluation ---
    prompt = f"""
    You are an Excel interview evaluator.
    Question: {current_q['question']}
    Candidate Answer: {req.answer}

    Score the answer from 0 to 3 (0=wrong, 1=partial, 2=good, 3=excellent).
    Also give a one-line reasoning.
    Respond in JSON with fields: score, reasoning.
    """
    gemini_resp = model.generate_content(prompt)
    
    # Parse Gemini response safely
    import json as pyjson
    try:
        gemini_eval = pyjson.loads(gemini_resp.text)
        gemini_score = gemini_eval.get("score", 0)
        reasoning = gemini_eval.get("reasoning", "")
    except Exception:
        gemini_score, reasoning = 0, "Could not parse Gemini response"

    # Combine scores (simple sum, max 6 points)
    total_score = gemini_score
    # total_score = keyword_score + gemini_score

    session["score"] += total_score
    session["answers"].append({
        "q": current_q["question"], 
        "a": req.answer, 
        "keyword_score": keyword_score,
        "gemini_score": gemini_score,
        "reasoning": reasoning,
        "level": current_q["level"],  # Store the level
        "total_score": total_score,
    })

    session["current"] += 1
    if session["current"] < len(session["questions"]):
        next_q = session["questions"][session["current"]]["question"]
        return {"next_question": next_q}
    else:
        return {"message": "Interview complete. Call /feedback for report."}

@app.get("/feedback")
def feedback(session_id: str):
    session = sessions[session_id]
    total_possible = len(session["questions"]) * 3  # 3 = max gemini score per Q
    percentage = (session["score"] / total_possible) * 100
    
    # Determine performance level
    if percentage >= 80:
        performance = "Excellent"
        strengths = "Strong conceptual understanding, good practical knowledge"
        weaknesses = "Minor areas for refinement"
    elif percentage >= 60:
        performance = "Good"
        strengths = "Solid foundation, understands key concepts"
        weaknesses = "Needs practice with advanced functions and scenarios"
    elif percentage >= 40:
        performance = "Average"
        strengths = "Basic understanding present"
        weaknesses = "Needs significant practice with formulas and data analysis"
    else:
        performance = "Needs Improvement"
        strengths = "Familiar with basic interface"
        weaknesses = "Requires comprehensive Excel training"

    result = {
        "score": session["score"],
        "total_possible": total_possible,
        "percentage": round(percentage, 1),
        "performance": performance,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendation": "Focus on practical exercises and real-world scenarios to improve Excel proficiency",
        "questions_answered": len(session["answers"])
    }
    return result

@app.get("/download_report")
def download_report(session_id: str):
    """Generate and return a detailed PDF report"""
    if session_id not in sessions:
        return {"error": "Session not found"}
    
    session = sessions[session_id]
    feedback_data = feedback(session_id)
    
    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf_path = temp_file.name
    temp_file.close()
    
    # Create PDF document
    doc = SimpleDocTemplate(pdf_path, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        textColor=colors.darkblue
    )
    story.append(Paragraph("Excel Skills Assessment Report", title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Date and performance summary
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    story.append(Paragraph(f"Assessment Date: {date_str}", styles["Normal"]))
    story.append(Spacer(1, 0.1*inch))
    
    # Performance Summary
    story.append(Paragraph("Performance Summary", styles["Heading2"]))
    summary_data = [
        ["Overall Score", f"{feedback_data['score']}/{feedback_data['total_possible']}"],
        ["Percentage", f"{feedback_data['percentage']}%"],
        ["Performance Level", feedback_data['performance']],
        ["Questions Answered", str(feedback_data['questions_answered'])]
    ]
    summary_table = Table(summary_data, colWidths=[2*inch, 3*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Strengths and Weaknesses
    col_widths = [2.75*inch, 2.75*inch]
    sw_data = [
        ["Strengths", "Areas for Improvement"],
        [feedback_data['strengths'], feedback_data['weaknesses']]
    ]
    sw_table = Table(sw_data, colWidths=col_widths)
    sw_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (0, 1), colors.lightgreen),
        ('BACKGROUND', (1, 1), (1, 1), colors.mistyrose),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP')
    ]))
    story.append(sw_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Detailed Question Analysis
    story.append(Paragraph("Detailed Question Analysis", styles["Heading2"]))
    story.append(Spacer(1, 0.1*inch))
    
    for i, answer in enumerate(session["answers"], 1):
        # Question header
        story.append(Paragraph(f"Question {i} ({answer['level'].title()})", styles["Heading3"]))
        story.append(Paragraph(f"<b>Question:</b> {answer['q']}", styles["Normal"]))
        story.append(Paragraph(f"<b>Your Answer:</b> {answer['a']}", styles["Normal"]))
        
        # Score details
        score_data = [
            ["Evaluation Metric", "Score"],
            ["AI Assessment Score", f"{answer['gemini_score']}/3"],
            ["Keyword Match Score", f"{answer['keyword_score']}/{len(session['questions'][i-1]['keywords'])}"],
            ["Total Score", f"{answer['total_score']}/3"]
        ]
        score_table = Table(score_data, colWidths=[2*inch, 1.5*inch])
        score_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(score_table)
        
        # Reasoning
        story.append(Paragraph(f"<b>Evaluation Reasoning:</b> {answer['reasoning']}", styles["Normal"]))
        story.append(Spacer(1, 0.2*inch))
    
    # Recommendations
    story.append(Paragraph("Recommendations for Improvement", styles["Heading2"]))
    story.append(Paragraph(feedback_data['recommendation'], styles["Normal"]))
    story.append(Spacer(1, 0.1*inch))
    
    # Specific recommendations based on performance
    if feedback_data['percentage'] < 60:
        rec_text = """
        • Practice basic Excel functions daily
        • Work on real-world Excel projects
        • Focus on VLOOKUP, PivotTables, and conditional formatting
        • Consider taking an Excel fundamentals course
        """
    else:
        rec_text = """
        • Explore advanced Excel features like Power Query
        • Practice with complex formulas and array functions
        • Learn data analysis and visualization techniques
        • Work on optimization and automation with macros
        """
    
    story.append(Paragraph(rec_text, styles["Normal"]))
    
    # Build PDF
    doc.build(story)
    
    return FileResponse(
        pdf_path, 
        media_type='application/pdf',
        filename=f"Excel_Assessment_Report_{session_id[:8]}.pdf"
    )
