import pandas as pd
import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.colors import black, blue, red
import io
import os
import random
import sqlite3
import streamlit as st  # Add this import statement

def load_questions(file_path):
    df = pd.read_excel(file_path)
    df.columns = df.columns.str.strip().str.lower()
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].str.strip()
    questions = df.to_dict('records')
    return random.sample(questions, min(10, len(questions)))

def save_results(results):
    db_path = 'results.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create table if it doesn't exist
    cursor.execute('''CREATE TABLE IF NOT EXISTS results
               (date TEXT, start_time TEXT, end_time TEXT, total_time_spent REAL, email_id TEXT, 
               no_qns_attempted INTEGER, qns_answered_correctly INTEGER, score REAL)''')
    
    # Insert results into the database
    for result in results:
        cursor.execute('''INSERT INTO results VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                       (result['date'], result['start_time'], result['end_time'], result['total_time_spent'], 
                        result['email_id'], result['no_qns_attempted'], result['qns_answered_correctly'], result['score']))
    
    conn.commit()
    conn.close()

def generate_certificate(email, score, total_questions, start_time, end_time, background_path):
    buffer = io.BytesIO()
    width, height = 12 * inch, 8.5 * inch
    c = canvas.Canvas(buffer, pagesize=(width, height))
    
    c.drawImage(background_path, 0, 0, width=width, height=height)
    
    c.setFillColor("black")
    c.setFont("Helvetica", 16)
    c.drawCentredString(width / 2, height - 300, f" ")
    
    c.setFont("Helvetica-Bold", 24)  
    c.drawCentredString(width / 2, height - 330, f"{email}")
    
    c.setFont("Helvetica", 16)
    c.drawCentredString(width / 2, height - 360, f"has completed the compliance training quiz")
    c.drawCentredString(width / 2, height - 390, f"with a score of {score}/{total_questions}")
    c.drawCentredString(width / 2, height - 420, f"Date: {start_time.date()}")
    c.drawCentredString(width / 2, height - 450, f"Start Time: {start_time.time()}")
    c.drawCentredString(width / 2, height - 480, f"End Time: {end_time.time()}")
    
    c.setFillColor("blue")
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width / 2, height - 510, "Congratulations on your achievement!")
    
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

def main():
    st.title("Compliance Training Quiz")
    
    if 'pdf_buffer' not in st.session_state:
        st.session_state.pdf_buffer = None

    if 'questions' not in st.session_state:
        st.session_state.questions = load_questions('questions.xlsx')
    
    if not st.session_state.questions:
        st.error("No questions loaded. Please check your Excel file.")
        return
    
    if 'stage' not in st.session_state:
        st.session_state.stage = 'email'
        st.session_state.email = ''
        st.session_state.question_index = 0
        st.session_state.questions_attempted = 0
        st.session_state.questions_correct = 0
        st.session_state.start_time = None
        st.session_state.end_time = None
        st.session_state.submitted_answers = {}
    
    if st.session_state.stage == 'email':
        st.session_state.email = st.text_input("Enter your name (to be displayed on the certificate):")
        if st.button("Start Quiz"):
            if st.session_state.email:
                st.session_state.stage = 'quiz'
                st.session_state.start_time = datetime.datetime.now()
                st.rerun()
            else:
                st.error("Please enter your email ID.")
    
    elif st.session_state.stage == 'quiz':
        current_index = st.session_state.question_index
        questions = st.session_state.questions
        
        if current_index < len(questions):
            question = questions[current_index]
            
            st.write(f"Question {current_index + 1} of {len(questions)}")
            st.write(question['question'])
            options = [question[f'option {opt}'] for opt in ['a', 'b', 'c', 'd']]
            user_answer = st.radio("Select your answer:", options, key=f"radio_{current_index}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if (st.button("Submit", key=f"submit_{current_index}") and 
                    current_index not in st.session_state.submitted_answers):
                    st.session_state.questions_attempted += 1
                    correct_answer = question['correctans'].strip().lower()
                    if user_answer.strip().lower() == correct_answer:
                        st.success("Correct!")
                        st.session_state.questions_correct += 1
                    else:
                        st.error(f"Wrong! The correct answer was: {correct_answer}")
                    st.session_state.submitted_answers[current_index] = user_answer
            
            with col2:
                if st.button("Next Question", key=f"next_{current_index}"):
                    if current_index < len(questions) - 1:
                        st.session_state.question_index += 1
                    else:
                        st.session_state.stage = 'complete'
                        st.session_state.end_time = datetime.datetime.now()
                    st.rerun()
        
        else:
            st.session_state.stage = 'complete'
            st.session_state.end_time = datetime.datetime.now()
            st.rerun()
    
    elif st.session_state.stage == 'complete':
        if not hasattr(st.session_state, 'results_saved') or not st.session_state.results_saved:
            results = {
                "date": str(st.session_state.start_time.date()),
                "start_time": str(st.session_state.start_time.time()),
                "end_time": str(st.session_state.end_time.time()),
                "total_time_spent": (st.session_state.end_time - 
                                     st.session_state.start_time).total_seconds(),
                "email_id": st.session_state.email,
                "no_qns_attempted": st.session_state.questions_attempted,
                "qns_answered_correctly": st.session_state.questions_correct,
                "score": (st.session_state.questions_correct / len(st.session_state.questions) * 
                          100) if len(st.session_state.questions) > 0 else 0
            }
            
            save_results([results])
            st.session_state.results_saved = True
        
        score = (st.session_state.questions_correct / len(st.session_state.questions) * 100 
                 if len(st.session_state.questions) > 0 else 0)
        
        if score >= 80:
            st.success(f"Congratulations! You passed the quiz with a score of {score:.2f}%")
            if st.button("Generate and Download Certificate"):
                pdf_buffer = generate_certificate(
                    email=st.session_state.email,
                    score=st.session_state.questions_correct,
                    total_questions=len(st.session_state.questions),
                    start_time=st.session_state.start_time,
                    end_time=st.session_state.end_time,
                    background_path='kristal_outline_2.png'
                )
                st.download_button(
                    label="Download Certificate",
                    data=pdf_buffer,
                    file_name=f"certificate_{st.session_state.email}.pdf",
                    mime="application/pdf"
                )
        else:
            st.error(f"Sorry, you did not pass the quiz. Your score: {score:.2f}%")
            if st.button("Retake Quiz"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

def complete_quiz():
    if not hasattr(st.session_state, 'results_saved') or not st.session_state.results_saved:
        # Ensure end_time is set
        if st.session_state.end_time is None:
            st.session_state.end_time = datetime.datetime.now()
        
        results = {
            "date": str(st.session_state.start_time.date()),
            "start_time": str(st.session_state.start_time.time()),
            "end_time": str(st.session_state.end_time.time()) if st.session_state.end_time else "",
            "total_time_spent": (st.session_state.end_time - 
                                 st.session_state.start_time).total_seconds() if st.session_state.end_time else 0,
            "email_id": st.session_state.email,
            "no_qns_attempted": st.session_state.questions_attempted,
            "qns_answered_correctly": st.session_state.questions_correct,
            "score": (st.session_state.questions_correct / len(st.session_state.questions) * 
                      100) if len(st.session_state.questions) > 0 else 0
        }
        
        save_results([results])
        # Mark results as saved to prevent duplicate entries
        st.session_state.results_saved = True

def display_results():
     score_percentage= (st_session.questions_correct / len(st_session.questions)) *100

     if score_percentage >=80:
         # Passed message and certificate generation option.
         with open(f"certificate_{st_session.email}.pdf", "wb") as f:
             f.write(st_session.pdf_buffer.getbuffer())
         with open(f"certificate_{st_session.email}.pdf", "rb") as f:
             btn_download_certifcate_pdf(f)

     else:
         # Failed message and option to retake.
         retake_quiz()

def retake_quiz():
     # Reset session state for retaking the quiz.
     for key in list(st_session.keys()):
         delattr(st_session,key)
     main()

if __name__ == "__main__":
   main()
