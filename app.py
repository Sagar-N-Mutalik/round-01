from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import json
import sqlite3
import time
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'

# Initialize database
def init_db():
    conn = sqlite3.connect('competition.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            current_question INTEGER DEFAULT 0,
            total_score INTEGER DEFAULT 0,
            start_time REAL,
            question_start_time REAL,
            completed BOOLEAN DEFAULT FALSE
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id INTEGER,
            question_id INTEGER,
            answer TEXT,
            correct BOOLEAN,
            submission_time REAL,
            points INTEGER DEFAULT 0,
            FOREIGN KEY (participant_id) REFERENCES participants (id)
        )
    ''')
    conn.commit()
    conn.close()

# Load questions from JSON
def load_questions():
    with open('questions.json', 'r') as f:
        return json.load(f)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start_competition():
    name = request.json.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    
    conn = sqlite3.connect('competition.db')
    c = conn.cursor()
    
    try:
        c.execute('INSERT INTO participants (name, start_time) VALUES (?, ?)', 
                 (name, time.time()))
        participant_id = c.lastrowid
        session['participant_id'] = participant_id
        session['name'] = name
        conn.commit()
        return jsonify({'success': True})
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Name already taken'}), 400
    finally:
        conn.close()

@app.route('/question')
def question_page():
    if 'participant_id' not in session:
        return redirect(url_for('home'))
    
    conn = sqlite3.connect('competition.db')
    c = conn.cursor()
    c.execute('SELECT current_question, completed FROM participants WHERE id = ?', 
              (session['participant_id'],))
    result = c.fetchone()
    conn.close()
    
    if not result:
        return redirect(url_for('home'))
    
    current_question, completed = result
    
    if completed:
        return redirect(url_for('scoreboard'))
    
    questions = load_questions()
    
    if current_question >= len(questions):
        return redirect(url_for('scoreboard'))
    
    question_data = questions[current_question]
    
    return render_template('question.html', 
                         question=question_data, 
                         question_num=current_question + 1,
                         total_questions=len(questions))

@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    if 'participant_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.json
    answer = data.get('answer', '').strip()
    question_id = data.get('question_id')
    
    conn = sqlite3.connect('competition.db')
    c = conn.cursor()
    
    # Get current participant state
    c.execute('SELECT current_question FROM participants WHERE id = ?', 
              (session['participant_id'],))
    current_question = c.fetchone()[0]
    
    if question_id != current_question:
        conn.close()
        return jsonify({'error': 'Invalid question'}), 400
    
    questions = load_questions()
    question_data = questions[current_question]
    
    # Check if answer is correct
    correct_answer = question_data['answer'].lower().strip()
    is_correct = answer.lower() == correct_answer
    
    # Calculate points based on submission order
    points = 0
    if is_correct:
        c.execute('SELECT COUNT(*) FROM answers WHERE question_id = ? AND correct = TRUE', 
                 (question_id,))
        correct_count = c.fetchone()[0]
        
        if correct_count == 0:
            points = 10  # 1st correct
        elif correct_count == 1:
            points = 8   # 2nd correct
        elif correct_count == 2:
            points = 5   # 3rd correct
        elif correct_count == 3:
            points = 2   # 4th correct
        
        # Bonus question (last question) gets 15 points if correct
        if current_question == len(questions) - 1:
            points = 15
    
    # Save answer
    c.execute('''INSERT INTO answers 
                 (participant_id, question_id, answer, correct, submission_time, points) 
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (session['participant_id'], question_id, answer, is_correct, time.time(), points))
    
    # Update participant's current question and score
    c.execute('''UPDATE participants 
                 SET current_question = current_question + 1, 
                     total_score = total_score + ?,
                     question_start_time = ?
                 WHERE id = ?''', 
              (points, time.time(), session['participant_id']))
    
    # Check if this was the last question
    if current_question + 1 >= len(questions):
        c.execute('UPDATE participants SET completed = TRUE WHERE id = ?', 
                 (session['participant_id'],))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'correct': is_correct,
        'points': points,
        'correct_answer': question_data['answer'],
        'explanation': question_data.get('explanation', '')
    })

@app.route('/get_question_time')
def get_question_time():
    if 'participant_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    conn = sqlite3.connect('competition.db')
    c = conn.cursor()
    c.execute('SELECT question_start_time, current_question FROM participants WHERE id = ?', 
              (session['participant_id'],))
    result = c.fetchone()
    conn.close()
    
    if not result:
        return jsonify({'error': 'Participant not found'}), 404
    
    question_start_time, current_question = result
    
    if question_start_time is None:
        # First question, set start time
        question_start_time = time.time()
        conn = sqlite3.connect('competition.db')
        c = conn.cursor()
        c.execute('UPDATE participants SET question_start_time = ? WHERE id = ?',
                 (question_start_time, session['participant_id']))
        conn.commit()
        conn.close()
    
    questions = load_questions()
    time_limit = questions[current_question]['time_limit']
    
    elapsed = time.time() - question_start_time
    remaining = max(0, time_limit - elapsed)
    
    return jsonify({
        'remaining_time': remaining,
        'time_limit': time_limit
    })

@app.route('/scoreboard')
def scoreboard():
    conn = sqlite3.connect('competition.db')
    c = conn.cursor()
    c.execute('''SELECT id, name, total_score, completed, start_time FROM participants ORDER BY total_score DESC, start_time ASC''')
    rows = c.fetchall()
    participants = []
    for row in rows:
        pid, name, total_score, completed, start_time = row
        # Get last answer submission time for this participant
        c.execute('SELECT MAX(submission_time) FROM answers WHERE participant_id = ?', (pid,))
        last_submission = c.fetchone()[0]
        if last_submission and start_time:
            time_taken = last_submission - start_time
        else:
            time_taken = None
        participants.append({
            'name': name,
            'total_score': total_score,
            'completed': completed,
            'time_taken': time_taken
        })
    conn.close()
    return render_template('scoreboard.html', participants=participants)

@app.route('/api/scoreboard')
def api_scoreboard():
    conn = sqlite3.connect('competition.db')
    c = conn.cursor()
    c.execute('''SELECT name, total_score, completed 
                 FROM participants 
                 ORDER BY total_score DESC, start_time ASC''')
    participants = c.fetchall()
    conn.close()
    
    return jsonify([{
        'name': p[0],
        'score': p[1],
        'completed': p[2]
    } for p in participants])

if __name__ == '__main__':
    init_db()
    app.run(debug=True)