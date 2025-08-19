// Question page functionality
let questionData, questionId, timeRemaining;
let timerInterval, sequenceTimerInterval;
let isTimerStarted = false;

// Initialize question data (called from template)
function initializeQuestionData(data, id, timeLimit) {
    questionData = data;
    questionId = id;
    timeRemaining = timeLimit;
}

document.addEventListener('DOMContentLoaded', function() {
    // Initialize timer from server
    initializeTimer();

    // Set up event listeners
    document.getElementById('submitBtn').addEventListener('click', submitAnswer);
    document.getElementById('answerInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            submitAnswer();
        }
    });
   
    // Disable next button initially
    const nextBtn = document.getElementById('nextBtn');
    nextBtn.disabled = true;
    nextBtn.addEventListener('click', goToNext);
    document.getElementById('timeUpNextBtn').addEventListener('click', goToNext);

    // Focus on answer input if not sequence question
    if (!questionData.sequence_view_time) {
        document.getElementById('answerInput').focus();
    }
});

async function initializeTimer() {
    try {
        const response = await fetch('/get_question_time');
        const data = await response.json();
        
        if (data.remaining_time !== undefined) {
            timeRemaining = Math.max(0, data.remaining_time);
            updateTimerDisplay();
            
            // Handle sequence viewing for sequence recall questions
            if (questionData.sequence_view_time) {
                startSequenceTimer();
            } else {
                startMainTimer();
            }
        }
    } catch (error) {
        console.error('Failed to initialize timer:', error);
        // Fallback to default behavior
        if (questionData.sequence_view_time) {
            startSequenceTimer();
        } else {
            startMainTimer();
        }
    }
}

function startSequenceTimer() {
    let sequenceTime = questionData.sequence_view_time || 0;
    document.getElementById('sequenceTimeRemaining').textContent = sequenceTime;

    sequenceTimerInterval = setInterval(function() {
        sequenceTime--;
        document.getElementById('sequenceTimeRemaining').textContent = sequenceTime;

        if (sequenceTime <= 0) {
            clearInterval(sequenceTimerInterval);
            document.getElementById('sequenceView').style.display = 'none';
            document.getElementById('questionContent').style.display = 'block';
            document.getElementById('answerInput').focus();
            startMainTimer();
        }
    }, 1000);
}

function startMainTimer() {
    if (isTimerStarted) return;
    isTimerStarted = true;
    
    updateTimerDisplay();
    
    timerInterval = setInterval(function() {
        timeRemaining--;
        updateTimerDisplay();

        if (timeRemaining <= 0) {
            clearInterval(timerInterval);
            timeUp();
        }
    }, 1000);
}

function updateTimerDisplay() {
    const minutes = Math.floor(timeRemaining / 60);
    const seconds = Math.floor(timeRemaining % 60);
    const display = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    document.getElementById('timeRemaining').textContent = display;
    
    // Add warning class when time is low
    const timer = document.getElementById('timer');
    timer.classList.remove('timer-warning', 'timer-danger');
    
    if (timeRemaining <= 30) {
        timer.classList.add('timer-warning');
    }
    if (timeRemaining <= 10) {
        timer.classList.add('timer-danger');
    }
}

function submitAnswer() {
    const answer = document.getElementById('answerInput').value.trim();
    if (!answer) {
        alert('Please enter an answer');
        return;
    }

    // Disable submit button and input
    document.getElementById('submitBtn').disabled = true;
    document.getElementById('answerInput').disabled = true;
    clearInterval(timerInterval);

    fetch('/submit_answer', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            answer: answer,
            question_id: questionId
        })
    })
    .then(response => response.json())
    .then(data => {
        showResult(data);
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Failed to submit answer. Please try again.');
        document.getElementById('submitBtn').disabled = false;
        document.getElementById('answerInput').disabled = false;
    });
}

function showResult(data) {
    const modal = document.getElementById('resultModal');
    const title = document.getElementById('resultTitle');
    const message = document.getElementById('resultMessage');
    const explanation = document.getElementById('explanation');
    const scoreInfo = document.getElementById('scoreInfo');

    if (data.correct) {
        title.textContent = '🎉 Correct!';
        title.className = 'result-correct';
        message.textContent = 'Well done! You got it right.';
    } else {
        title.textContent = '❌ Incorrect';
        title.className = 'result-incorrect';
        message.textContent = `The correct answer was: ${data.correct_answer}`;
    }

    if (data.explanation) {
        explanation.innerHTML = `<strong>Explanation:</strong> ${data.explanation}`;
        explanation.style.display = 'block';
    } else {
        explanation.style.display = 'none';
    }

    scoreInfo.textContent = `Points earned: ${data.points}`;

    modal.style.display = 'flex';
    modal.setAttribute('aria-hidden', 'false');
    // Enable and focus next button after answer is submitted and result shown
    const nextBtn = document.getElementById('nextBtn');
    if (nextBtn) {
        nextBtn.disabled = false;
        nextBtn.focus();
    }
}

function timeUp() {
    document.getElementById('submitBtn').disabled = true;
    document.getElementById('answerInput').disabled = true;
    const modal = document.getElementById('timeUpModal');
    modal.style.display = 'flex';
    modal.setAttribute('aria-hidden', 'false');
}

function goToNext() {
    window.location.href = '/question';
}

function playDistraction() {
    try {
        // Play a beep sound or distraction
    // ...audio context creation removed...
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        oscillator.frequency.value = 800;
        oscillator.type = 'sine';
        
        gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
        
        oscillator.start();
        oscillator.stop(audioContext.currentTime + 0.5);
    } catch (error) {
        console.error('Failed to play distraction sound:', error);
        // Fallback: show a visual indicator
        const btn = document.getElementById('distractionBtn');
        btn.style.backgroundColor = '#28a745';
        setTimeout(() => {
            btn.style.backgroundColor = '';
        }, 200);
    }
}
