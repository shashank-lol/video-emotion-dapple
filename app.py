import numpy as np
from flask import Flask, request, jsonify
from PIL import Image
from tensorflow.keras.utils import img_to_array
from tensorflow.keras.models import load_model
from flask_cors import CORS  # Add this import
import os
import sqlite3
from collections import Counter
from datetime import datetime
import json
import shutil
import uuid

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes


# Constants
MODEL_PATH = "modelf1.h5"
SESSIONS_DIR = "session_images"
DB_PATH = "sessions.db"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
EMOTIONS = ['Angry', 'Disgust', 'Fear', 'Happy', 'Sad', 'Surprise', 'Neutral']

# Initialize database
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS sessions
                 (session_id TEXT PRIMARY KEY,
                  timestamp_start DATETIME,
                  timestamp_end DATETIME,
                  status TEXT,
                  total_images INTEGER DEFAULT 0,
                  results JSON)''')
    conn.commit()
    conn.close()

# Create necessary directories and initialize DB
os.makedirs(SESSIONS_DIR, exist_ok=True)
init_db()

# Load model
if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"Model file not found: {MODEL_PATH}")
model = load_model(MODEL_PATH)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def analyze_emotion_trend(emotion_counts):
    total = sum(emotion_counts.values())
    if total == 0:
        return "No emotions detected"
        
    positive_emotions = (emotion_counts.get('Happy', 0) + emotion_counts.get('Surprise', 0)) / total
    negative_emotions = (emotion_counts.get('Sad', 0) + emotion_counts.get('Angry', 0) + 
                        emotion_counts.get('Fear', 0) + emotion_counts.get('Disgust', 0)) / total
    
    if positive_emotions > 0.6:
        return "Predominantly positive emotions"
    elif negative_emotions > 0.6:
        return "Predominantly negative emotions"
    else:
        return "Mixed emotional state"

def get_emotion_variability(emotion_counts):
    unique_emotions = len([count for count in emotion_counts.values() if count > 0])
    if unique_emotions >= 5:
        return "High emotional variability"
    elif unique_emotions >= 3:
        return "Moderate mood fluctuations"
    elif unique_emotions > 0:
        return "Stable emotional state"
    else:
        return "No emotions detected"

def update_session_image_count(session_id):
    """Increment the total_images count for a session"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE sessions SET total_images = total_images + 1 WHERE session_id = ?', 
              (session_id,))
    conn.commit()
    conn.close()

def get_session_status(session_id):
    """Check if a session exists and is active"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT status FROM sessions WHERE session_id = ?', (session_id,))
    result = c.fetchone()
    conn.close()
    
    if not result:
        return None
    return result[0]

def save_session_results(session_id, results, status="completed"):
    """Save or update session results"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''UPDATE sessions
                 SET timestamp_end = ?,
                     status = ?,
                     results = ?
                 WHERE session_id = ?''',
              (datetime.now().isoformat(),
               status,
               json.dumps(results),
               session_id))
    conn.commit()
    conn.close()

def get_stored_session_results(session_id):
    """Get stored session results if they exist"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT results FROM sessions WHERE session_id = ? AND results IS NOT NULL', 
              (session_id,))
    result = c.fetchone()
    conn.close()
    return json.loads(result[0]) if result and result[0] else None

@app.route('/start_session', methods=['POST'])
def start_session():
    """Start a new session and return session ID"""
    try:
        # Generate a unique session ID
        session_id = str(uuid.uuid4())
        
        # Create session directory
        session_dir = os.path.join(SESSIONS_DIR, session_id)
        os.makedirs(session_dir, exist_ok=True)
        
        # Record session start in database
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''INSERT INTO sessions 
                     (session_id, timestamp_start, status, total_images)
                     VALUES (?, ?, ?, ?)''',
                  (session_id, 
                   datetime.now().isoformat(),
                   "active",
                   0))
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": "Session started",
            "session_id": session_id
        })
        
    except Exception as e:
        print(f"Error starting session: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/upload_frame', methods=['POST'])
def upload_frame():
    """Process and analyze a single frame"""
    try:
        if 'image' not in request.files:
            return jsonify({"error": "No image provided"}), 400
        
        session_id = request.form.get('session_id')
        if not session_id:
            return jsonify({"error": "No session_id provided"}), 400

        # Check if session exists and is active
        session_status = get_session_status(session_id)
        if not session_status:
            return jsonify({"error": "Session not found"}), 404
        if session_status != "active":
            return jsonify({"error": f"Session is {session_status}, not active"}), 400

        file = request.files['image']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
        
        if not allowed_file(file.filename):
            return jsonify({"error": "File type not allowed"}), 400

        # Create session directory if it doesn't exist (should already exist)
        session_dir = os.path.join(SESSIONS_DIR, session_id)
        os.makedirs(session_dir, exist_ok=True)

        # Process image
        img = Image.open(file.stream)
        img = img.resize((48, 48))
        img = img.convert('L')
        img_array = img_to_array(img)
        img_pixels = np.expand_dims(np.expand_dims(img_array, axis=-1), axis=0) / 255.0
        
        # Get prediction
        prediction = model.predict(img_pixels)
        emotion_index = np.argmax(prediction)
        confidence = float(prediction[0][emotion_index])
        emotion = EMOTIONS[emotion_index]
        
        # Save result
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        result_path = os.path.join(session_dir, f"frame_{timestamp}.json")
        with open(result_path, 'w') as f:
            result_data = {
                "emotion": emotion,
                "confidence": confidence,
                "timestamp": timestamp
            }
            json.dump(result_data, f)

        # Update session image count
        update_session_image_count(session_id)

        return jsonify({
            "status": "success",
            "session_id": session_id,
            "frame_emotion": emotion,
            "confidence": confidence
        })

    except Exception as e:
        print(f"Error processing frame: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/end_session', methods=['POST'])
def end_session():
    """End a session and generate final results"""
    try:
        session_id = request.form.get('session_id')
        if not session_id:
            return jsonify({"error": "No session_id provided"}), 400

        # Check if session exists and is active
        session_status = get_session_status(session_id)
        if not session_status:
            return jsonify({"error": "Session not found"}), 404
        if session_status != "active":
            return jsonify({"error": f"Session is already {session_status}"}), 400
            
        # Process session results
        session_results = process_session_data(session_id)
        if session_results.get("error"):
            return jsonify(session_results), 404
            
        # Mark session as completed and save results
        save_session_results(session_id, session_results, "completed")
        
        # Optional: Clean up session images to save space
        # We'll keep the images for now in case they need to be reviewed
        
        return jsonify({
            "status": "success",
            "message": "Session ended successfully",
            "session_id": session_id,
            "results": session_results
        })

    except Exception as e:
        print(f"Error ending session: {e}")
        return jsonify({"error": str(e)}), 500

def process_session_data(session_id):
    """Process all data for a session and generate statistics"""
    session_dir = os.path.join(SESSIONS_DIR, session_id)
    if not os.path.exists(session_dir):
        return {"error": "Session directory not found"}

    # Collect all emotions from session
    emotions = []
    confidences = []
    
    for filename in os.listdir(session_dir):
        if filename.endswith('.json'):
            try:
                with open(os.path.join(session_dir, filename)) as f:
                    data = json.load(f)
                    emotions.append(data["emotion"])
                    if "confidence" in data:
                        confidences.append(data["confidence"])
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error processing {filename}: {e}")

    if not emotions:
        return {"error": "No frames found in session"}

    # Calculate statistics
    emotion_counts = Counter(emotions)
    
    if emotion_counts:
        most_common = emotion_counts.most_common(1)[0][0]
        least_common = min(emotion_counts.items(), key=lambda x: x[1])[0]
    else:
        most_common = "None"
        least_common = "None"
        
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0

    # Prepare response
    return {
        "session_id": session_id,
        "total_images": len(emotions),
        "average_emotion": most_common,
        "average_confidence": round(avg_confidence, 2),
        "emotion_distribution": dict(emotion_counts),
        "session_summary": {
            "most_common_emotion": most_common,
            "least_common_emotion": least_common,
            "emotion_variability": get_emotion_variability(emotion_counts),
            "overall_trend": analyze_emotion_trend(emotion_counts),
            "notable_observations": [
                f"{most_common} was the dominant emotion.",
                f"Detected {len([e for e in emotion_counts if emotion_counts[e] > 0])} different emotions.",
                f"Average confidence level: {round(avg_confidence * 100, 1)}%"
            ]
        }
    }



@app.route('/get_session_results', methods=['GET'])
def get_session_results():
    """Get results for a completed session or current stats for active session"""
    try:
        session_id = request.args.get('session_id')
        if not session_id:
            return jsonify({"error": "No session_id provided"}), 400

        # Check if session exists
        session_status = get_session_status(session_id)
        if not session_status:
            return jsonify({"error": "Session not found"}), 404

        # If session is completed, get stored results
        if session_status == "completed":
            stored_results = get_stored_session_results(session_id)
            if stored_results:
                return jsonify(stored_results)
                
        # If session is active or we don't have stored results, process current data
        results = process_session_data(session_id)
        if "error" in results:
            return jsonify(results), 404
            
        # Include session status in results
        results["session_status"] = session_status
            
        return jsonify(results)

    except Exception as e:
        print(f"Error getting session results: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/get_all_sessions', methods=['GET'])
def get_all_sessions():
    """Get list of all sessions"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''SELECT 
                       session_id, 
                       timestamp_start, 
                       timestamp_end,
                       status, 
                       total_images 
                     FROM sessions
                     ORDER BY timestamp_start DESC''')
        
        sessions = [{
            "session_id": row[0],
            "start_time": row[1],
            "end_time": row[2],
            "status": row[3],
            "total_images": row[4]
        } for row in c.fetchall()]
        
        conn.close()
        return jsonify({"sessions": sessions})
        
    except Exception as e:
        print(f"Error getting all sessions: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/clear_session', methods=['POST'])
def clear_session():
    """Delete a session and all associated data"""
    try:
        session_id = request.form.get('session_id')
        if not session_id:
            return jsonify({"error": "No session_id provided"}), 400

        # Check if session exists
        session_status = get_session_status(session_id)
        if not session_status:
            return jsonify({"error": "Session not found"}), 404

        # Remove from database
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('DELETE FROM sessions WHERE session_id = ?', (session_id,))
        conn.commit()
        conn.close()

        # Remove session directory if it exists
        session_dir = os.path.join(SESSIONS_DIR, session_id)
        if os.path.exists(session_dir):
            shutil.rmtree(session_dir)

        return jsonify({
            "status": "success", 
            "message": f"Session {session_id} cleared"
        })

    except Exception as e:
        print(f"Error clearing session: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({
        "status": "healthy",
        "model_loaded": True,
        "server_time": datetime.now().isoformat()
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5110)