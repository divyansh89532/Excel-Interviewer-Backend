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
import re

load_dotenv()
# --- Gemini Setup ---
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash")

app = FastAPI()

# Load pre-generated question bank
with open("questions.json", "r") as f:
    QUESTION_BANK = json.load(f)

# In-memory session storage 
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
    
    # print("Gemini Response:", gemini_resp.text)  # Debugging line
    # Parsing Gemini response 
    import json as pyjson
    try:
        cleaned_response = gemini_resp.text.strip()
        
        if cleaned_response.startswith('```json'):
            cleaned_response = cleaned_response[7:]
        if cleaned_response.endswith('```'):
            cleaned_response = cleaned_response[:-3]
        cleaned_response = cleaned_response.strip()
        
        cleaned_response = re.sub(r',\s*}', '}', cleaned_response)
        cleaned_response = re.sub(r',\s*]', ']', cleaned_response)
        
        gemini_eval = pyjson.loads(cleaned_response)
        gemini_score = gemini_eval.get("score", 0)
        reasoning = gemini_eval.get("reasoning", "")
        
        
    except Exception as e:
        print(f"JSON parsing error: {e}")
        
        # Fallback: Try to extract score and reasoning with regex
        try:
            score_match = re.search(r'"score":\s*(\d+)', gemini_resp.text)
            reasoning_match = re.search(r'"reasoning":\s*"([^"]*)"', gemini_resp.text)
            
            gemini_score = int(score_match.group(1)) if score_match else 0
            reasoning = reasoning_match.group(1) if reasoning_match else "Could not parse Gemini response"
            # print(f"Fallback parsing - Score: {gemini_score}, Reasoning: {reasoning}")
        except:
            gemini_score, reasoning = 0, "Could not parse Gemini response"
            # print("Fallback parsing also failed")

    # Combining scores (simple sum, max 6 points)
    total_score = gemini_score + keyword_score

    session["score"] += total_score
    session["answers"].append({
        "q": current_q["question"], 
        "a": req.answer, 
        "keyword_score": keyword_score,
        "gemini_score": gemini_score,
        "reasoning": reasoning,
        "level": current_q["level"],  
        "total_score": total_score,
        "keywords": current_q["keywords"] 
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
    total_possible = len(session["questions"]) * 3  
    percentage = (session["score"] / total_possible) * 100
    
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
def download_report(session_id: str, user_name: str = "", user_email: str = "", user_company: str = "", user_position: str = ""):
    """Generate and return a detailed PDF report"""
    if session_id not in sessions:
        return {"error": "Session not found"}
    
    session = sessions[session_id]
    
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

    # Candidate Details
    story.append(Paragraph("Candidate Information", styles["Heading2"]))
    candidate_data = [
        ["Name", user_name or "Not Provided"],
        ["Email", user_email or "Not Provided"],
        ["Company", user_company or "Not Provided"],
        ["Position", user_position or "Not Provided"]
    ]
    candidate_table = Table(candidate_data, colWidths=[1.5*inch, 4*inch])
    candidate_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(candidate_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Calculate performance metrics
    total_possible = len(session["answers"]) * 3
    percentage = (session["score"] / total_possible) * 100 if total_possible > 0 else 0
    
    # Performance Summary
    story.append(Paragraph("Performance Summary", styles["Heading2"]))
    summary_data = [
        ["Overall Score", f"{session['score']}/{total_possible}"],
        ["Percentage", f"{percentage:.1f}%"],
        ["Questions Answered", str(len(session["answers"]))],
        ["Session ID", session_id[:8]]
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
    
    # Determine performance level for report
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
    
    # Strengths and Weaknesses
    col_widths = [2.75*inch, 2.75*inch]
    sw_data = [
        ["Strengths", "Areas for Improvement"],
        [strengths, weaknesses]
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
        level = answer.get('level', 'Unknown')
        story.append(Paragraph(f"Question {i} ({level.title()})", styles["Heading3"]))
        story.append(Paragraph(f"<b>Question:</b> {answer['q']}", styles["Normal"]))
        story.append(Paragraph(f"<b>Your Answer:</b> {answer['a']}", styles["Normal"]))
        
        # Score details
        keyword_max = len(answer.get('keywords', []))
        score_data = [
            ["Evaluation Metric", "Score"],
            ["AI Assessment Score", f"{answer['gemini_score']}/3"],
            ["Keyword Match Score", f"{answer['keyword_score']}/{keyword_max}"],
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
    
    story.append(Paragraph("AI-Powered Recommendations", styles["Heading2"]))

    try:
        performance_summary = {
            "total_score": session["score"],
            "total_possible": total_possible,
            "percentage": percentage,
            "performance_level": performance,
            "questions_answered": len(session["answers"]),
            "detailed_scores": session["answers"]
        }
        
        recommendations_prompt = f"""
        You are an Excel skills assessment expert. Based on the following performance data, provide personalized recommendations for improvement.

        PERFORMANCE SUMMARY:
        - Overall Score: {session['score']}/{total_possible} ({percentage:.1f}%)
        - Performance Level: {performance}
        - Questions Answered: {len(session['answers'])}
        
        DETAILED PERFORMANCE BREAKDOWN:
        {json.dumps([{'question': ans['q'], 'level': ans.get('level', 'unknown'), 'score': ans['total_score'], 'reasoning': ans['reasoning']} for ans in session['answers']], indent=2)}
        
        Please provide 4-6 specific, actionable recommendations for improvement based on their performance.
        
        FORMATTING REQUIREMENTS:
        - Use ONLY plain text with simple bullet points starting with •
        - NO markdown formatting (no **bold**, no *italics*, no headings)
        - NO nested bullet points
        - Each recommendation should be concise and self-contained
        - Focus on specific Excel functions, features, or practice areas
        - Keep each bullet point to 1-2 sentences maximum
        
        Example format:
        • Practice basic Excel functions like SUM, AVERAGE, and COUNT regularly
        • Focus on understanding VLOOKUP and PivotTables for data analysis
        • Work with real datasets to improve data manipulation skills
        • Learn conditional formatting to enhance data visualization
        
        Respond with only the bullet point recommendations, no additional commentary or explanations.
        """
        
        gemini_recommendations_resp = model.generate_content(recommendations_prompt)
        
        # Parse and clean the response
        recommendations_text = gemini_recommendations_resp.text.strip()
        print("Raw Gemini recommendations:", recommendations_text)  # Debug
        
        if recommendations_text.startswith('```'):
            recommendations_text = recommendations_text.split('```')[1].strip()
            if recommendations_text.startswith('markdown'):
                recommendations_text = recommendations_text[8:].strip()
        
        # Clean the text - remove asterisks and other markdown
        recommendations_text = re.sub(r'\*\*', '', recommendations_text)
        recommendations_text = re.sub(r'\*', '', recommendations_text) 
        recommendations_text = re.sub(r'#+\s*', '', recommendations_text)
        
        
        recommendations_list = []
        for line in recommendations_text.split('\n'):
            line = line.strip()
            
            
            if not line:
                continue
            if line.lower().startswith(('start with', 'focus:', 'resources:', 'example format:', 'formatting requirements:')):
                continue
                
            
            line = re.sub(r'^[•\-*\d.]+\s*', '', line) 
            line = line.strip()
            
            if line and len(line) > 10: 
                if len(line) > 150:
                    
                    sentences = re.split(r'[.:]', line)
                    for sentence in sentences:
                        sentence = sentence.strip()
                        if sentence and len(sentence) > 20:
                            recommendations_list.append(sentence)
                else:
                    recommendations_list.append(line)
        
       
        unique_recommendations = []
        seen = set()
        for rec in recommendations_list:
            
            key = rec[:100].lower()
            if key not in seen and len(rec) > 15:
                seen.add(key)
                unique_recommendations.append(rec)
        
       
        unique_recommendations = unique_recommendations[:6]
        
        
        if unique_recommendations:
            for rec in unique_recommendations:
               
                rec = rec.strip()
                if rec and not rec[0].isupper():
                    rec = rec[0].upper() + rec[1:]
                if not rec.endswith('.'):
                    rec = rec + '.'
                    
                story.append(Paragraph(f"• {rec}", styles["Normal"]))
        else:
           
            raise Exception("No recommendations parsed")
            
    except Exception as e:
        print(f"Error generating AI recommendations: {e}")
        
        story.append(Paragraph("Based on your performance, we recommend:", styles["Normal"]))
        if percentage < 60:
            fallback_recs = [
                "Practice basic Excel functions and formulas regularly with real datasets",
                "Focus on understanding VLOOKUP, PivotTables, and data analysis features",
                "Work on data formatting, sorting, and filtering techniques",
                "Learn conditional formatting and basic data visualization",
                "Practice with Excel Tables and Named Ranges for better data organization",
                "Build confidence with basic calculations and cell referencing"
            ]
        else:
            fallback_recs = [
                "Explore advanced Excel features like Power Query and Power Pivot",
                "Practice with complex formulas, array functions, and dynamic arrays",
                "Learn data analysis and interactive dashboard creation techniques",
                "Study automation with Excel macros and basic VBA programming",
                "Master advanced PivotTable features and data modeling concepts",
                "Practice with data validation and advanced conditional formatting"
            ]
        
        for rec in fallback_recs:
            story.append(Paragraph(f"• {rec}", styles["Normal"]))

    
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("Focus Areas for Development", styles["Heading3"]))

    try:
        
        weak_answers = [ans for ans in session["answers"] if ans['total_score'] < 2]
        if weak_answers:
            weak_topics = list(set([ans.get('level', 'General') for ans in weak_answers]))
            
            focus_prompt = f"""
            The candidate struggled with these Excel topics: {', '.join(weak_topics)}
            
            Suggest 2-3 specific practice exercises for these areas. Be very concrete.
            
            Format as simple bullet points starting with •, no markdown, no explanations.
            Example:
            • Practice creating PivotTables with sample sales data
            • Build formulas using VLOOKUP to match customer data
            
            Respond with only the practice suggestions.
            """
            
            focus_resp = model.generate_content(focus_prompt)
            focus_text = focus_resp.text.strip()
            
            # Clean the response
            focus_text = re.sub(r'[*#]', '', focus_text)  
            if focus_text.startswith('```'):
                focus_text = focus_text.split('```')[1].strip()
            
            focus_points = []
            for line in focus_text.split('\n'):
                line = line.strip()
                if line and len(line) > 15 and not line.lower().startswith('example'):
                    
                    line = re.sub(r'^[•\-*\d.]+\s*', '', line)
                    line = line.strip()
                    if line:
                        focus_points.append(line)
            
           
            for point in focus_points[:3]: 
                if point:
                    story.append(Paragraph(f"• {point}", styles["Normal"]))
        else:
            story.append(Paragraph("Continue building on your strong foundation with advanced Excel projects and complex data analysis.", styles["Normal"]))
            
    except Exception as e:
        print(f"Error generating focus areas: {e}")
        story.append(Paragraph("Focus on practicing the specific Excel functions where you scored lower. Consider working through structured Excel tutorials.", styles["Normal"]))
    
    # Build PDF
    doc.build(story)
    
    return FileResponse(
        pdf_path, 
        media_type='application/pdf',
        filename=f"Excel_Assessment_Report_{user_name.replace(' ', '_') if user_name else 'Candidate'}_{session_id[:8]}.pdf"
    )
