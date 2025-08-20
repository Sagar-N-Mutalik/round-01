from flask import Flask, render_template, request, session, jsonify, redirect, url_for
from flask_socketio import SocketIO, join_room, emit
import database as db
import secrets
import time

# --- APP SETUP ---
app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(24)
app.config['SESSION_TYPE'] = 'filesystem'
socketio = SocketIO(app)

# --- WEB ROUTES ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))
    
@app.route('/lobby')
def lobby():
    if 'participant_id' not in session:
        return redirect(url_for('index'))
    return render_template('lobby.html', session=session)

@app.route('/question')
def question():
    if 'participant_id' not in session:
        return redirect(url_for('index'))
    
    conn = db.get_db_connection()
    group = conn.execute('SELECT round_started FROM groups WHERE id = ?', (session['group_id'],)).fetchone()
    conn.close()
    if not group or not group['round_started']:
        return redirect(url_for('lobby'))

    return render_template('question.html', session=session)
    
@app.route('/scoreboard/<int:group_id>')
def scoreboard(group_id):
    conn = db.get_db_connection()
    group = conn.execute('SELECT name FROM groups WHERE id = ?', (group_id,)).fetchone()
    conn.close()
    if not group:
        return "Group not found", 404
    return render_template('scoreboard.html', group_name=group['name'], group_id=group_id)

# --- SOCKETIO EVENTS ---
@socketio.on('join_lobby')
def handle_join_lobby(data):
    group_id = data.get('group_id')
    if not group_id: return
    join_room(f"group_{group_id}")
    update_lobby_players(int(group_id))

@socketio.on('join_scoreboard')
def handle_join_scoreboard(data):
    group_id = data.get('group_id')
    if not group_id: return
    join_room(f"group_{group_id}")
    update_scoreboard(int(group_id))

@socketio.on('start_round')
def handle_start_round(data):
    group_id_str = data.get('group_id')
    if not group_id_str or not session.get('is_proctor'): return
    group_id = int(group_id_str)

    conn = db.get_db_connection()
    conn.execute('UPDATE groups SET round_started = TRUE, current_question_index = 0 WHERE id = ?', (group_id,))
    conn.commit()
    conn.close()
    
    room = f"group_{group_id}"
    questions = db.get_questions()
    group_questions = questions[group_id - 1]
    first_question = group_questions[0]
    
    socketio.emit('round_started', {
        'first_question': first_question,
        'q_index': 0,
        'total_q': len(group_questions)
    }, room=room)


# **THIS IS THE CORRECTED FUNCTION**
@socketio.on('proctor_next_question')
def handle_proctor_next_question(data):
    if not session.get('is_proctor'): 
        return

    group_id = int(data.get('group_id'))
    current_q_index = int(data.get('q_index'))
    next_q_index = current_q_index + 1
    
    room = f"group_{group_id}"
    questions = db.get_questions()
    group_questions = questions[group_id - 1]
    
    if next_q_index < len(group_questions):
        conn = db.get_db_connection()
        conn.execute('UPDATE groups SET current_question_index = ? WHERE id = ?', (next_q_index, group_id))
        conn.commit()
        conn.close()
        
        question_data = group_questions[next_q_index]
        socketio.emit('current_question', {
            'question': question_data, 
            'q_index': next_q_index, 
            'total_q': len(group_questions)
        }, room=room)
    else:
        socketio.emit('game_over', {'message': 'The round has ended!'}, room=room)

@socketio.on('submit_answer')
def handle_submit_answer(data):
    if 'participant_id' not in session or session.get('is_proctor'): return

    participant_id, group_id = session['participant_id'], session['group_id']
    q_index = data.get('q_index')
    answer = data.get('answer', '').strip().lower()
    time_taken = data.get('time_taken')

    conn = db.get_db_connection()
    already_answered = conn.execute('SELECT 1 FROM answers WHERE participant_id = ? AND question_index = ?', (participant_id, q_index)).fetchone()

    if not already_answered:
        questions = db.get_questions()
        correct_answer = questions[group_id - 1][q_index]['answer'].lower()
        is_correct = (answer == correct_answer)
        
        conn.execute(
            'INSERT INTO answers (participant_id, question_index, group_id, time_taken, points_awarded) VALUES (?, ?, ?, ?, ?)',
            (participant_id, q_index, group_id, time_taken, 0)
        )
        conn.commit()
        
        if is_correct:
            correct_answers = conn.execute(
                'SELECT id, participant_id FROM answers WHERE group_id = ? AND question_index = ? AND time_taken IS NOT NULL ORDER BY time_taken ASC',
                (group_id, q_index)
            ).fetchall()
            
            point_values = [10, 8, 5, 2]
            for i, ans in enumerate(correct_answers):
                points = point_values[i] if i < len(point_values) else 0
                conn.execute('UPDATE answers SET points_awarded = ? WHERE id = ?', (points, ans['id']))
            conn.commit()

        participants = conn.execute('SELECT id FROM participants WHERE group_id = ? AND is_proctor = FALSE', (group_id,)).fetchall()
        for p in participants:
            total_score = conn.execute('SELECT SUM(points_awarded) FROM answers WHERE participant_id = ?', (p['id'],)).fetchone()[0] or 0
            conn.execute('UPDATE participants SET total_score = ? WHERE id = ?', (total_score, p['id']))
        conn.commit()

        emit('answer_result', {'correct': is_correct, 'message': 'Your answer has been recorded!'})
    
    conn.close()
    update_scoreboard(group_id)

@socketio.on('get_final_scores')
def handle_get_final_scores(data):
    group_id = data.get('group_id')
    if not group_id: return
    conn = db.get_db_connection()
    scores = conn.execute('SELECT name, total_score FROM participants WHERE group_id = ? AND is_proctor = FALSE ORDER BY total_score DESC, id ASC', (group_id,)).fetchall()
    conn.close()
    score_list = [{'name': s['name'], 'score': s['total_score']} for s in scores]
    emit('final_scores', {'scores': score_list})

def update_lobby_players(group_id):
    conn = db.get_db_connection()
    players = conn.execute('SELECT name, is_proctor FROM participants WHERE group_id = ?', (group_id,)).fetchall()
    conn.close()
    player_list = [{'name': p['name'], 'is_proctor': p['is_proctor']} for p in players]
    socketio.emit('lobby_update', {'players': player_list}, room=f"group_{group_id}")

def update_scoreboard(group_id):
    conn = db.get_db_connection()
    current_q_index_row = conn.execute('SELECT current_question_index FROM groups WHERE id = ?', (group_id,)).fetchone()
    current_q_index = current_q_index_row['current_question_index'] if current_q_index_row else 0
    
    scores = conn.execute('''
        SELECT p.name, p.total_score, a.time_taken
        FROM participants p
        LEFT JOIN answers a ON p.id = a.participant_id AND a.question_index = ?
        WHERE p.group_id = ? AND p.is_proctor = FALSE 
        ORDER BY p.total_score DESC, a.time_taken ASC
    ''', (current_q_index, group_id)).fetchall()
    conn.close()
    score_list = [{'name': s['name'], 'score': s['total_score'], 'time_taken': s['time_taken']} for s in scores]
    socketio.emit('scoreboard_update', {'scores': score_list}, room=f"group_{group_id}")

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    name, code = data.get('name', '').strip(), data.get('code', '').strip().upper()
    if not name or not code: return jsonify({'success': False, 'message': 'Name and Group Code are required.'})

    is_proctor = (name.upper() == 'PROCTOR')
    conn = db.get_db_connection()
    group = conn.execute('SELECT id, name, round_started FROM groups WHERE code = ?', (code,)).fetchone()

    if not group:
        conn.close()
        return jsonify({'success': False, 'message': 'Invalid Group Code.'})
    
    group_id, group_name, round_started = group['id'], group['name'], group['round_started']

    if round_started and not is_proctor:
        participant = conn.execute('SELECT id FROM participants WHERE name = ? AND group_id = ?', (name, group_id)).fetchone()
        if not participant:
            conn.close()
            return jsonify({'success': False, 'message': 'This round has already started.'})
    
    if not is_proctor:
        player_count = conn.execute('SELECT COUNT(*) FROM participants WHERE group_id = ? AND is_proctor = FALSE', (group_id,)).fetchone()[0]
        if player_count >= 4:
             participant = conn.execute('SELECT id FROM participants WHERE name = ? AND group_id = ?', (name, group_id)).fetchone()
             if not participant:
                conn.close()
                return jsonify({'success': False, 'message': 'This group is full.'})

    session_id = secrets.token_hex(16)
    
    try:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO participants (name, group_id, session_id, is_proctor) VALUES (?, ?, ?, ?)', (name, group_id, session_id, is_proctor))
        participant_id = cursor.lastrowid
        conn.commit()
    except conn.IntegrityError:
        cursor = conn.cursor()
        cursor.execute('UPDATE participants SET session_id = ? WHERE name = ? AND group_id = ?', (session_id, name, group_id))
        participant_id = cursor.execute('SELECT id FROM participants WHERE name = ? AND group_id = ?', (name, group_id)).fetchone()['id']
        conn.commit()
    
    conn.close()
    
    session.clear()
    session['participant_id'] = participant_id
    session['name'] = name
    session['group_id'] = group_id
    session['group_name'] = group_name
    session['is_proctor'] = is_proctor
    session['round_started'] = round_started

    return jsonify({'success': True, 'is_proctor': is_proctor})

if __name__ == '__main__':
    print("-> Starting Flask server at http://127.0.0.1:5000")
    print("-> To stop the server, press CTRL+C")
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)