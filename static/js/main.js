document.addEventListener("DOMContentLoaded", () => {
    const socket = io();

    // --- PAGE INITIALIZATION based on body class ---
    if (document.body.classList.contains('page-login')) {
        initLoginPage();
    } else if (document.body.classList.contains('page-lobby')) {
        initLobbyPage(socket);
    } else if (document.body.classList.contains('page-question')) {
        initQuestionPage(socket);
    } else if (document.body.classList.contains('page-scoreboard')) {
        initScoreboardPage(socket);
    }
});

// --- LOGIN PAGE LOGIC ---
function initLoginPage() {
    const loginBtn = document.getElementById('loginBtn');
    const nameInput = document.getElementById('participantName');
    const codeInput = document.getElementById('groupCode');
    const errorMessage = document.getElementById('errorMessage');

    const attemptLogin = async () => {
        const name = nameInput.value.trim();
        const code = codeInput.value.trim();

        if (!name || !code) {
            errorMessage.textContent = "Name and Group Code are required.";
            return;
        }

        loginBtn.disabled = true;
        errorMessage.textContent = "";

        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, code })
            });
            const data = await response.json();

            if (data.success) {
                window.location.href = '/lobby';
            } else {
                errorMessage.textContent = data.message;
            }
        } catch (error) {
            errorMessage.textContent = "An error occurred. Please try again.";
        } finally {
            loginBtn.disabled = false;
        }
    };

    loginBtn.addEventListener('click', attemptLogin);
    nameInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') codeInput.focus(); });
    codeInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') attemptLogin(); });
}

// --- LOBBY PAGE LOGIC ---
function initLobbyPage(socket) {
    const lobbyCard = document.querySelector('.lobby-card');
    const groupId = lobbyCard.dataset.groupId;
    const playerList = document.getElementById('playerList');
    const startRoundBtn = document.getElementById('startRoundBtn');

    socket.on('connect', () => {
        socket.emit('join_lobby', { group_id: groupId });
    });

    socket.on('lobby_update', (data) => {
        playerList.innerHTML = '';
        data.players.forEach(player => {
            const li = document.createElement('li');
            li.textContent = player.name;
            if (player.is_proctor) {
                const tag = document.createElement('span');
                tag.className = 'proctor-tag';
                tag.textContent = '(Proctor)';
                li.appendChild(tag);
            }
            playerList.appendChild(li);
        });
    });

    socket.on('round_started', () => {
        // Add round_started to session storage to handle reloads
        sessionStorage.setItem('round_started', 'true');
        window.location.href = '/question';
    });

    if (startRoundBtn) {
        startRoundBtn.addEventListener('click', () => {
            startRoundBtn.disabled = true;
            socket.emit('start_round', { group_id: groupId });
        });
    }
}

// --- QUESTION PAGE LOGIC ---
function initQuestionPage(socket) {
    const questionContainer = document.getElementById('questionContainer');
    const gameOverContainer = document.getElementById('gameOverContainer');
    const progressText = document.getElementById('progressText');
    const categoryText = document.getElementById('categoryText');
    const questionText = document.getElementById('questionText');
    const answerInput = document.getElementById('answerInput');
    const submitBtn = document.getElementById('submitAnswerBtn');

    const timerText = document.getElementById('timerText');
    const timerPath = document.getElementById('timer-path');
    const FULL_DASH_ARRAY = 283;
    let timeLimit = 60;
    let timePassed = 0;
    let timerInterval = null;
    
    const resultModal = document.getElementById('resultModal');
    const resultTitle = document.getElementById('resultTitle');
    const resultPoints = document.getElementById('resultPoints');
    const correctAnswerText = document.getElementById('correctAnswerText');
    const nextQuestionBtn = document.getElementById('nextQuestionBtn');
    
    let currentQuestionIndex = -1;

    socket.on('connect', () => {
        socket.emit('get_question');
    });

    socket.on('current_question', (data) => {
        if (data.q_index === currentQuestionIndex) return;
        currentQuestionIndex = data.q_index;
        displayQuestion(data);
    });
    
    socket.on('answer_result', (data) => {
        clearInterval(timerInterval);
        showResult(data);
    });

    socket.on('game_over', () => {
        questionContainer.style.display = 'none';
        gameOverContainer.style.display = 'block';
        clearInterval(timerInterval);
    });

    function displayQuestion(data) {
        questionContainer.style.display = 'block';
        answerInput.value = '';
        answerInput.disabled = false;
        submitBtn.disabled = false;
        
        const { question, q_index, total_q } = data;
        progressText.textContent = `Question ${q_index + 1} of ${total_q}`;
        categoryText.textContent = question.category;
        questionText.textContent = question.question;
        
        timeLimit = question.time_limit;
        startTimer();
        answerInput.focus();
    }
    
    function submitAnswer() {
        const answer = answerInput.value;
        if (!answer.trim() || submitBtn.disabled) return;

        clearInterval(timerInterval);
        answerInput.disabled = true;
        submitBtn.disabled = true;

        socket.emit('submit_answer', {
            q_index: currentQuestionIndex,
            answer: answer
        });
    }

    submitBtn.addEventListener('click', submitAnswer);
    answerInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') submitAnswer(); });
    
    function showResult(data) {
        resultTitle.textContent = data.correct ? 'Correct!' : 'Incorrect';
        resultTitle.className = data.correct ? 'correct' : 'incorrect';
        resultPoints.textContent = `+${data.points} Points`;
        correctAnswerText.textContent = data.correct ? '' : `Correct Answer: ${data.correct_answer}`;
        resultModal.style.display = 'flex';
    }
    
    nextQuestionBtn.addEventListener('click', () => {
        resultModal.style.display = 'none';
        socket.emit('get_question');
    });

    function startTimer() {
        timePassed = -1;
        clearInterval(timerInterval);
        updateTimerDisplay(timeLimit);
        timerInterval = setInterval(() => {
            timePassed += 1;
            const timeLeft = timeLimit - timePassed;
            if (timeLeft < 0) {
                clearInterval(timerInterval);
                submitAnswer();
                return;
            }
            updateTimerDisplay(timeLeft);
        }, 1000);
    }

    function updateTimerDisplay(timeLeft) {
        const minutes = Math.floor(timeLeft / 60);
        let seconds = timeLeft % 60;
        timerText.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
        const fraction = timeLeft / timeLimit;
        const offset = fraction * FULL_DASH_ARRAY;
        timerPath.style.strokeDashoffset = (1 - fraction) * FULL_DASH_ARRAY;
    }
}

// --- SCOREBOARD PAGE LOGIC ---
function initScoreboardPage(socket) {
    const scoreboardCard = document.querySelector('.scoreboard-card');
    const groupId = scoreboardCard.dataset.groupId;
    const scoreList = document.getElementById('scoreList');

    socket.on('connect', () => {
        socket.emit('join_scoreboard', { group_id: groupId });
    });

    socket.on('scoreboard_update', (data) => {
        renderScores(data.scores);
    });

    function renderScores(scores) {
        scoreList.innerHTML = '';
        if (scores.length === 0) {
            scoreList.innerHTML = '<p>No scores yet. The round may not have started.</p>';
            return;
        }
        scores.forEach((player, index) => {
            const rank = index + 1;
            const row = document.createElement('div');
            row.className = 'score-row';
            row.innerHTML = `
                <span class="score-rank">${rank}</span>
                <span class="score-name">${player.name}</span>
                <span class="score-points">${player.score}</span>
            `;
            scoreList.appendChild(row);
        });
    }
}