# Mind Mashup - Competition Website

A Flask-powered competition website for a two-round event featuring multiple question categories with real-time scoring and live leaderboards.

## Features

### Round 1: Mind Mashup (6:00 PM – 7:00 PM)
- **Tech Riddle** - 3 minutes
- **Maths Problem** - 5 minutes  
- **Reasoning Puzzle** - 5 minutes
- **Sequence Recall** - 30s viewing + 5 minutes solve
- **Sudoku (4×4)** - 5 minutes
- **Bonus Question** - 10 minutes

### Scoring System
- 1st correct answer: 10 points
- 2nd correct answer: 8 points
- 3rd correct answer: 5 points
- 4th correct answer: 2 points
- Bonus question (full completion): 15 points
- Tie-breaker bonus: 10 points

### Technical Features
- Real-time countdown timers for each question
- Live scoreboard with automatic updates
- Fun distraction sound effects during questions
- Responsive design for all devices
- SQLite database for participant data
- Session management for seamless experience

## Installation & Setup

### Local Development

1. **Install Python 3.7+** (if not already installed)

2. **Install Flask:**
   ```bash
   pip install flask
   ```

3. **Run the application:**
   ```bash
   python app.py
   ```
   
   Or alternatively:
   ```bash
   flask run
   ```

4. **Access the website:**
   - Open your browser to `http://localhost:5000`

### Production Deployment on PythonAnywhere

1. **Upload files** to your PythonAnywhere account

2. **Install Flask** in your virtual environment:
   ```bash
   pip3.10 install flask
   ```

3. **Configure WSGI file** (`/var/www/yourusername_pythonanywhere_com_wsgi.py`):
   ```python
   import sys
   import os

   # Add your project directory to sys.path
   project_home = '/home/yourusername/mindmashup'
   if project_home not in sys.path:
       sys.path = [project_home] + sys.path

   from app import app as application
   ```

4. **Set up database** by running the app once (creates SQLite database automatically)

5. **Restart web app** from PythonAnywhere dashboard

## File Structure

```
/
├── app.py                 # Main Flask application
├── questions.json         # Sample questions data
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── templates/
│   ├── index.html        # Home page
│   ├── question.html     # Question page  
│   └── scoreboard.html   # Scoreboard page
├── static/
│   ├── style.css         # CSS styling
│   ├── script.js         # JavaScript functionality
│   └── sounds/           # Audio files directory
└── competition.db        # SQLite database (auto-created)
```

## Usage

1. **Start Competition:**
   - Enter your name on the home page
   - Click "Start Competition"

2. **Answer Questions:**
   - Each question has a countdown timer
   - Use the 🔊 button for distraction sounds
   - Submit answers before time runs out

3. **View Scoreboard:**
   - Live rankings update automatically
   - See completion status of all participants
   - Points awarded based on submission order

## Customization

### Adding Questions
Edit `questions.json` to modify or add new questions:

```json
{
  "id": 0,
  "category": "Your Category",
  "time_limit": 300,
  "question": "Your question text",
  "answer": "correct answer",
  "explanation": "Optional explanation"
}
```

### Modifying Scoring
Update the scoring logic in `app.py` in the `submit_answer` route.

### Styling Changes
Modify `static/style.css` to customize the visual appearance.

## Security Notes

- Change the `secret_key` in `app.py` for production use
- Consider implementing rate limiting for submissions
- Add input validation for production deployment
- Use environment variables for sensitive configuration

## Browser Support

- Chrome 60+
- Firefox 55+
- Safari 11+
- Edge 79+

Requires JavaScript enabled for full functionality.

## Troubleshooting

**Database Issues:**
- Delete `competition.db` and restart the app to reset all data

**Timer Not Working:**
- Ensure JavaScript is enabled in your browser
- Check browser console for errors

**Audio Issues:**
- Web browsers require user interaction before playing audio
- Click anywhere on the page first, then try the distraction sounds

## Support

For issues or questions, please check that all dependencies are properly installed and that you're using a supported Python version (3.7+).