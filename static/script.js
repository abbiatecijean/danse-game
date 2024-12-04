// Charger les fichiers sons
var successSound = new Audio(successSoundUrl);
var startSound = new Audio(startSoundUrl);
var endSound = new Audio(endSoundUrl);

var gameOver = false;
var gameStarted = false;

document.getElementById('start-btn').addEventListener('click', function() {
    // Masquer l'écran de démarrage et afficher le jeu
    document.getElementById('start-screen').style.display = 'none';
    document.getElementById('game-container').style.display = 'block';

    // Jouer le son de démarrage
    startSound.play();

    // Démarrer la mise à jour des données du jeu
    gameStarted = true;
    updateGameData(); // Lancer la première mise à jour
    updateInterval = setInterval(updateGameData, 500);
});

var updateInterval;

function updateGameData() {
    if (!gameStarted) return;

    fetch('/get_game_data')
        .then(response => response.json())
        .then(data => {
            // Mise à jour des éléments du DOM
            document.getElementById('command').innerText = 'Commande : ' + data.command;
            document.getElementById('score').innerText = 'Score : ' + data.score;
            document.getElementById('timer').innerText = 'Temps restant : ' + data.remaining_time + 's';

            // Mettre à jour la barre de progression
            const progressElement = document.getElementById('progress');
            const totalTime = 60; // Durée totale du jeu en secondes
            const percentage = (data.remaining_time / totalTime) * 100;
            progressElement.style.width = percentage + '%';

            // Jouer les sons en fonction des événements
            if (data.success) {
                successSound.play();
            }

            if (data.game_over && !gameOver) {
                gameOver = true;
                endSound.play();
                showRestartButton();
                clearInterval(updateInterval); // Arrêter la mise à jour
            }
        })
        .catch(err => console.error('Erreur :', err));
}

function showRestartButton() {
    const restartBtn = document.getElementById('restart-btn');
    restartBtn.style.display = 'inline-block';
    restartBtn.addEventListener('click', restartGame);
}

function restartGame() {
    fetch('/restart_game', { method: 'POST' })
        .then(() => {
            gameOver = false;
            document.getElementById('restart-btn').style.display = 'none';
            startSound.play();

            // Réinitialiser les éléments du DOM
            document.getElementById('command').innerText = 'Commande : ';
            document.getElementById('score').innerText = 'Score : 0';
            document.getElementById('timer').innerText = 'Temps restant : 60s';
            document.getElementById('progress').style.width = '100%';

            // Redémarrer la mise à jour des données du jeu
            gameStarted = true;
            updateGameData(); // Lancer la première mise à jour
            updateInterval = setInterval(updateGameData, 500);
        })
        .catch(err => console.error('Erreur :', err));
}
