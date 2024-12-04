from flask import Flask, render_template, Response, jsonify, request
import cv2
import mediapipe as mp
import time
import random
import threading
import webbrowser

app = Flask(__name__)

# Configuration Mediapipe
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)
mp_drawing = mp.solutions.drawing_utils

# Commandes et instructions
COMMANDS = ["Lever les mains", "Se pencher à gauche", "Se pencher à droite", "Sauter"]
INSTRUCTIONS = {
    "Lever les mains": lambda landmarks: (
        landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].y < landmarks[mp_pose.PoseLandmark.NOSE.value].y and
        landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].y < landmarks[mp_pose.PoseLandmark.NOSE.value].y
    ),
    "Se pencher à gauche": lambda landmarks: (
        landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x < landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].x - 0.05
    ),
    "Se pencher à droite": lambda landmarks: (
        landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x > landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].x + 0.05
    ),
    "Sauter": lambda landmarks, initial_ankle_y: (
        landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].y < initial_ankle_y - 0.1 and
        landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].y < initial_ankle_y - 0.1
    ),
}

# Variables globales
game_state = {
    'current_command': random.choice(COMMANDS),
    'score': 0,
    'last_command_time': time.time(),
    'command_duration': 5,  # secondes
    'start_time': time.time(),
    'game_duration': 60,  # Durée du jeu en secondes
    'command_success': False,
    'initial_left_ankle_y': None,
    'initial_right_ankle_y': None,
    'game_over': False
}

# Verrou pour la gestion des frames
frame_lock = threading.Lock()
current_frame = None

def capture_frames():
    global current_frame, game_state
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    cap.set(cv2.CAP_PROP_FPS, 30)

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.flip(frame, 1)
        with frame_lock:
            current_frame = frame.copy()
            # Capturer la position initiale des chevilles pour améliorer la détection du saut
            if game_state['initial_left_ankle_y'] is None or game_state['initial_right_ankle_y'] is None:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = pose.process(rgb_frame)
                if results.pose_landmarks:
                    landmarks = results.pose_landmarks.landmark
                    game_state['initial_left_ankle_y'] = landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].y
                    game_state['initial_right_ankle_y'] = landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].y

def generate_frames():
    global current_frame, game_state

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    cap.set(cv2.CAP_PROP_FPS, 30)

    while True:
        with frame_lock:
            if current_frame is None:
                continue
            frame = current_frame.copy()

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb_frame)

        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark

            # Dessiner les landmarks en mode minimaliste
            mp_drawing.draw_landmarks(
                frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2),
                mp_drawing.DrawingSpec(color=(0, 0, 255), thickness=2, circle_radius=2)
            )

            # Vérifier si l'utilisateur exécute la commande actuelle
            current_command = game_state['current_command']
            if current_command == "Sauter":
                if INSTRUCTIONS[current_command](landmarks, game_state['initial_left_ankle_y']):
                    game_state['score'] += 1
                    game_state['command_success'] = True
                    game_state['current_command'] = random.choice(COMMANDS)
                    game_state['last_command_time'] = time.time()
            else:
                if INSTRUCTIONS[current_command](landmarks):
                    game_state['score'] += 1
                    game_state['command_success'] = True
                    game_state['current_command'] = random.choice(COMMANDS)
                    game_state['last_command_time'] = time.time()

        # Changer de commande toutes les 'command_duration' secondes
        if time.time() - game_state['last_command_time'] > game_state['command_duration']:
            game_state['current_command'] = random.choice(COMMANDS)
            game_state['last_command_time'] = time.time()

        # Vérifier si la durée du jeu est écoulée
        if time.time() - game_state['start_time'] > game_state['game_duration']:
            game_state['game_over'] = True
            break  # Arrêter le traitement des frames

        # Encoder la frame en format JPEG pour le streaming
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 70]  # Qualité JPEG à 70%
        _, buffer = cv2.imencode('.jpg', frame, encode_param)
        frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    # Arrêter la capture vidéo
    cap.release()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/get_game_data')
def get_game_data():
    global game_state
    remaining_time = max(0, int(game_state['game_duration'] - (time.time() - game_state['start_time'])))
    data = {
        'command': game_state['current_command'],
        'score': game_state['score'],
        'remaining_time': remaining_time,
        'success': game_state['command_success'],
        'game_over': game_state['game_over']
    }
    game_state['command_success'] = False  # Réinitialiser le drapeau de succès
    return jsonify(data)

@app.route('/restart_game', methods=['POST'])
def restart_game():
    global game_state
    # Réinitialiser l'état du jeu
    game_state = {
        'current_command': random.choice(COMMANDS),
        'score': 0,
        'last_command_time': time.time(),
        'command_duration': 5,
        'start_time': time.time(),
        'game_duration': 40,
        'command_success': False,
        'initial_left_ankle_y': None,
        'initial_right_ankle_y': None,
        'game_over': False
    }
    return ('', 204)  # Réponse vide avec code 204 No Content

if __name__ == "__main__":
    # Fonction pour ouvrir le navigateur par défaut (Chrome) sur localhost:5000
    def open_browser():
        webbrowser.open_new("http://localhost:5000")

    # Démarrer le thread de capture vidéo
    capture_thread = threading.Thread(target=capture_frames)
    capture_thread.daemon = True
    capture_thread.start()

    # Lancer un thread pour ouvrir le navigateur
    threading.Thread(target=open_browser).start()

    # Lancer le serveur Flask
    app.run(debug=True)
