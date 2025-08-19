from flask import Flask, render_template, request, session, jsonify, redirect, url_for
from flask_socketio import SocketIO, join_room, emit
import database as db
import secrets

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
    conn.execute('UPDATE groups SET round_started = TRUE WHERE id = ?', (group_id,))
    conn.commit()
    conn.close()
    
    room = f"group_{group_id}"
    questions = db.get_questions()
    group_questions = questions[group_id - 1]
    first_question = group_questions[0]
    
    socketio.emit('round_started', {
        'first_question': first_question,
        'total_q': len(group_questions)
    }, room=room)

# **FIXED**: Proctor-controlled next question logic
@socketio.on('proctor_next_question')
def handle_proctor_next_question(data):
    if not session.get('is_proctor'): return
    
    group_id = int(data.get('group_id'))
    current_q_index = int(data.get('q_index'))
    next_q_index = current_q_index + 1
    
    room = f"group_{group_id}"
    questions = db.get_questions()
    group_questions = questions[group_id - 1]
    
    if next_q_index < len(group_questions):
        # **NEW**: Advance all participants in the group to the next question
        conn = db.get_db_connection()
        conn.execute('UPDATE participants SET current_question = ? WHERE group_id = ? AND is_proctor = FALSE', (next_q_index, group_id))
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

    questions = db.get_questions()
    correct_answer = questions[group_id - 1][q_index]['answer'].lower()
    is_correct = (answer == correct_answer)
    points = 0

    conn = db.get_db_connection()
    already_answered = conn.execute('SELECT 1 FROM answers WHERE participant_id = ? AND question_index = ?', (participant_id, q_index)).fetchone()

    if not already_answered:
        if is_correct:
            correct_count = conn.execute(
                'SELECT COUNT(*) FROM answers WHERE group_id = ? AND question_index = ? AND points_awarded > 0',
                (group_id, q_index)
            ).fetchone()[0]
            point_values = [10, 8, 5, 2]
            points = point_values[correct_count] if correct_count < len(point_values) else 0
        
        conn.execute('INSERT INTO answers (participant_id, question_index, group_id, points_awarded) VALUES (?, ?, ?, ?)',
                     (participant_id, q_index, group_id, points))
        if points > 0:
            conn.execute('UPDATE participants SET total_score = total_score + ? WHERE id = ?', (points, participant_id))
        
        # NOTE: We no longer advance the question here. The proctor does.
        conn.commit()
    
    conn.close()
    
    emit('answer_result', {'correct': is_correct, 'points': points, 'correct_answer': correct_answer.capitalize()})
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
    scores = conn.execute('SELECT name, total_score FROM participants WHERE group_id = ? AND is_proctor = FALSE ORDER BY total_score DESC, id ASC', (group_id,)).fetchall()
    conn.close()
    score_list = [{'name': s['name'], 'score': s['total_score']} for s in scores]
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