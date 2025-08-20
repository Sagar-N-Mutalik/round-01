import sqlite3
import os
import secrets
import json
import time

# --- DATABASE CONFIG ---
INSTANCE_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
DATABASE_PATH = os.path.join(INSTANCE_FOLDER, 'gauntlet.db')

def get_db_connection():
    """Establishes a connection to the database."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def setup_database():
    """Creates the database tables and populates it with 25 groups."""
    if os.path.exists(DATABASE_PATH):
        print("Database already exists. If you want to reset, delete the 'instance' folder and run this script again.")
        return

    print("Creating new database...")
    os.makedirs(INSTANCE_FOLDER, exist_ok=True)
    
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create tables
    cursor.execute('''
        CREATE TABLE groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            code TEXT NOT NULL UNIQUE,
            round_started BOOLEAN DEFAULT FALSE,
            current_question_index INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            group_id INTEGER NOT NULL,
            session_id TEXT NOT NULL UNIQUE,
            total_score INTEGER DEFAULT 0,
            is_proctor BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (group_id) REFERENCES groups(id),
            UNIQUE(name, group_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id INTEGER NOT NULL,
            question_index INTEGER NOT NULL,
            group_id INTEGER NOT NULL,
            points_awarded INTEGER DEFAULT 0,
            time_taken REAL,
            FOREIGN KEY (participant_id) REFERENCES participants(id),
            FOREIGN KEY (group_id) REFERENCES groups(id),
            UNIQUE(participant_id, question_index)
        )
    ''')

    # Populate 25 groups with unique codes
    group_codes = []
    for i in range(1, 26):
        code = secrets.token_hex(3).upper()
        cursor.execute('INSERT INTO groups (name, code) VALUES (?, ?)', (f'Group {i}', code))
        group_codes.append({'group_name': f'Group {i}', 'code': code})

    conn.commit()
    conn.close()

    with open('group_codes.json', 'w') as f:
        json.dump(group_codes, f, indent=4)
        
    print("Database setup complete. 25 groups created.")
    print("IMPORTANT: Group access codes have been saved to 'group_codes.json'.")


def get_questions():
    """Loads questions from the JSON file."""
    try:
        with open('questions.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        print(f"FATAL ERROR: Could not load or parse questions.json: {e}")
        return []

if __name__ == '__main__':
    setup_database()