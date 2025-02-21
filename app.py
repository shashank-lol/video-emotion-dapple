import numpy as np
from flask import Flask, request, jsonify
from PIL import Image
from tensorflow.keras.utils import img_to_array
from tensorflow.keras.models import load_model
from flask_cors import CORS
import os
import redis
from collections import Counter
from datetime import datetime
import json
import shutil
import uuid

app = Flask(__name__)
CORS(app)

# Constants
MODEL_PATH = "modelf1.h5"
SESSIONS_DIR = "session_images"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
EMOTIONS = ['Angry', 'Disgust', 'Fear', 'Happy', 'Sad', 'Surprise', 'Neutral']

# Redis Configuration
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
REDIS_DB = int(os.environ.get('REDIS_DB', 0))
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', None)

# Initialize Redis client
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    decode_responses=True  # Automatically decode responses to strings
)

# Create necessary directories
os.makedirs(SESSIONS_DIR, exist_ok=True)

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

def get_session_status(session_id):
    """Check if a session exists and its status"""
    session_data = redis_client.hget(f"session:{session_id}", "status")
    return session_data

def get_question(question_id):
    """Check if a question exists"""
    session_id = redis_client.hget(f"question:{question_id}", "session_id")
    if session_id:
        return {
            "question_id": question_id,
            "session_id": session_id
        }
    return None

def ensure_question_exists(session_id, question_id):
    """Ensure question exists, create if it doesn't"""
    question = get_question(question_id)
    if not question:
        # Create question in Redis
        redis_client.hset(f"question:{question_id}", mapping={
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "total_frames": 0
        })
        
        # Add to session's question list
        redis_client.sadd(f"session:{session_id}:questions", question_id)
        
        # Create question directory
        question_dir = os.path.join(SESSIONS_DIR, session_id, question_id)
        os.makedirs(question_dir, exist_ok=True)

def update_frame_counts(session_id, question_id):
    """Increment the frame counts for both session and question"""
    redis_client.hincrby(f"session:{session_id}", "total_images", 1)
    redis_client.hincrby(f"question:{question_id}", "total_frames", 1)

def save_session_results(session_id, results, status="completed"):
    """Save or update session results"""
    redis_client.hset(f"session:{session_id}", mapping={
        "timestamp_end": datetime.now().isoformat(),
        "status": status,
        "results": json.dumps(results)
    })

def save_question_results(question_id, results):
    """Save or update question results"""
    redis_client.hset(f"question:{question_id}", "results", json.dumps(results))

def get_stored_session_results(session_id):
    """Get stored session results if they exist"""
    results = redis_client.hget(f"session:{session_id}", "results")
    return json.loads(results) if results else None

def get_stored_question_results(question_id):
    """Get stored question results if they exist"""
    results = redis_client.hget(f"question:{question_id}", "results")
    return json.loads(results) if results else None

def get_session_questions(session_id):
    """Get all questions for a session"""
    # Get list of question IDs for this session
    question_ids = redis_client.smembers(f"session:{session_id}:questions")
    
    questions = []
    for question_id in question_ids:
        # Get question data
        q_data = redis_client.hgetall(f"question:{question_id}")
        if not q_data:
            continue
            
        question = {
            "question_id": question_id,
            "timestamp": q_data.get("timestamp"),
            "total_frames": int(q_data.get("total_frames", 0))
        }
        
        # Add results if they exist
        if "results" in q_data and q_data["results"]:
            try:
                question["results"] = json.loads(q_data["results"])
            except:
                question["results"] = None
                
        questions.append(question)
    
    return questions

def get_question_frames(question_id):
    """Get all frames for a question"""
    # Get list of frame IDs for this question
    frame_ids = redis_client.smembers(f"question:{question_id}:frames")
    
    frames = []
    for frame_id in frame_ids:
        # Get frame data
        f_data = redis_client.hgetall(f"frame:{frame_id}")
        if not f_data:
            continue
            
        frames.append({
            "frame_id": frame_id,
            "timestamp": f_data.get("timestamp"),
            "emotion": f_data.get("emotion"),
            "confidence": float(f_data.get("confidence", 0))
        })
    
    return frames

@app.route('/start_session', methods=['POST'])
def start_session():
    """Start a new session and return session ID"""
    try:
        # Generate a unique session ID
        session_id = str(uuid.uuid4())
        
        # Create session directory
        session_dir = os.path.join(SESSIONS_DIR, session_id)
        os.makedirs(session_dir, exist_ok=True)
        
        # Record session start in Redis
        redis_client.hset(f"session:{session_id}", mapping={
            "timestamp_start": datetime.now().isoformat(),
            "status": "active",
            "total_images": 0
        })
        
        # Add to list of all sessions
        redis_client.zadd("sessions", {session_id: datetime.now().timestamp()})
        
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
    """Process and analyze a single frame for a specific question within a session"""
    try:
        if 'image' not in request.files:
            return jsonify({"error": "No image provided"}), 400
        
        session_id = request.form.get('session_id')
        question_id = request.form.get('question_id')
        
        if not session_id:
            return jsonify({"error": "No session_id provided"}), 400
        if not question_id:
            return jsonify({"error": "No question_id provided"}), 400

        # Check if session exists and is active
        session_status = get_session_status(session_id)
        if not session_status:
            return jsonify({"error": "Session not found"}), 404
        if session_status != "active":
            return jsonify({"error": f"Session is {session_status}, not active"}), 400

        # Ensure question exists (create if it doesn't)
        ensure_question_exists(session_id, question_id)

        file = request.files['image']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
        
        if not allowed_file(file.filename):
            return jsonify({"error": "File type not allowed"}), 400

        # Create question directory if it doesn't exist
        question_dir = os.path.join(SESSIONS_DIR, session_id, question_id)
        os.makedirs(question_dir, exist_ok=True)

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
        
        # Generate frame ID and timestamp
        frame_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        # Save image 
        img_path = os.path.join(question_dir, f"{frame_id}.jpg")
        img.save(img_path)
        
        # Save frame data to Redis
        redis_client.hset(f"frame:{frame_id}", mapping={
            "session_id": session_id,
            "question_id": question_id,
            "timestamp": timestamp,
            "emotion": emotion,
            "confidence": confidence
        })
        
        # Add to question's frame list
        redis_client.sadd(f"question:{question_id}:frames", frame_id)

        # Update frame counts
        update_frame_counts(session_id, question_id)

        return jsonify({
            "status": "success",
            "session_id": session_id,
            "question_id": question_id,
            "frame_id": frame_id,
            "emotion": emotion,
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
            
        # Process each question first
        questions = get_session_questions(session_id)
        for question in questions:
            question_id = question["question_id"]
            question_results = process_question_data(question_id)
            save_question_results(question_id, question_results)
            
        # Process overall session results
        session_results = process_session_data(session_id)
        
        # Mark session as completed and save results
        save_session_results(session_id, session_results, "completed")
        
        return jsonify({
            "status": "success",
            "message": "Session ended successfully",
            "session_id": session_id,
            "results": session_results
        })

    except Exception as e:
        print(f"Error ending session: {e}")
        return jsonify({"error": str(e)}), 500

def process_question_data(question_id):
    """Process all data for a question and generate statistics"""
    # Get all frames for this question
    frames = get_question_frames(question_id)
    
    if not frames:
        return {
            "question_id": question_id,
            "error": "No frames found for this question"
        }

    # Extract emotions and confidences
    emotions = [frame["emotion"] for frame in frames]
    confidences = [frame["confidence"] for frame in frames]
    
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
        "question_id": question_id,
        "total_frames": len(frames),
        "average_emotion": most_common,
        "average_confidence": round(avg_confidence, 2),
        "emotion_distribution": dict(emotion_counts),
        "summary": {
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

def process_session_data(session_id):
    """Process all data for a session and generate aggregate statistics"""
    # Get all questions for this session
    questions = get_session_questions(session_id)
    
    if not questions:
        return {
            "session_id": session_id,
            "error": "No questions found in session"
        }
    
    # Process each question if not already processed
    question_results = []
    all_emotions = []
    all_confidences = []
    
    for question in questions:
        question_id = question["question_id"]
        
        # Get or process question results
        if "results" in question and question["results"]:
            results = question["results"]
        else:
            results = process_question_data(question_id)
            save_question_results(question_id, results)
            
        if "error" in results:
            continue
            
        question_results.append({
            "question_id": question_id,
            "total_frames": results["total_frames"],
            "average_emotion": results["average_emotion"],
            "emotion_distribution": results["emotion_distribution"]
        })
        
        # Collect emotions for overall statistics
        for emotion, count in results["emotion_distribution"].items():
            all_emotions.extend([emotion] * count)
            
        # Get frame confidences
        frames = get_question_frames(question_id)
        frame_confidences = [frame["confidence"] for frame in frames]
        all_confidences.extend(frame_confidences)
    
    if not all_emotions:
        return {
            "session_id": session_id,
            "error": "No emotion data found across questions"
        }
    
    # Calculate overall statistics
    emotion_counts = Counter(all_emotions)
    
    most_common = emotion_counts.most_common(1)[0][0] if emotion_counts else "None"
    least_common = min(emotion_counts.items(), key=lambda x: x[1])[0] if emotion_counts else "None"
    
    avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0
    
    # Prepare overall response
    return {
        "session_id": session_id,
        "total_questions": len(questions),
        "total_frames": len(all_emotions),
        "average_emotion": most_common,
        "average_confidence": round(avg_confidence, 2),
        "emotion_distribution": dict(emotion_counts),
        "questions": question_results,
        "session_summary": {
            "most_common_emotion": most_common,
            "least_common_emotion": least_common,
            "emotion_variability": get_emotion_variability(emotion_counts),
            "overall_trend": analyze_emotion_trend(emotion_counts),
            "notable_observations": [
                f"{most_common} was the dominant emotion across all questions.",
                f"Detected {len([e for e in emotion_counts if emotion_counts[e] > 0])} different emotions across {len(question_results)} questions.",
                f"Average confidence level: {round(avg_confidence * 100, 1)}%"
            ]
        }
    }

@app.route('/get_question_results', methods=['GET'])
def get_question_results():
    """Get results for a specific question"""
    try:
        question_id = request.args.get('question_id')
        
        if not question_id:
            return jsonify({"error": "No question_id provided"}), 400

        # Check if question exists
        question = get_question(question_id)
        if not question:
            return jsonify({"error": "Question not found"}), 404

        # Check for stored results first
        stored_results = get_stored_question_results(question_id)
        if stored_results:
            return jsonify(stored_results)
                
        # If no stored results, process the data
        results = process_question_data(question_id)
        
        # Save the results for future requests
        save_question_results(question_id, results)
            
        return jsonify(results)

    except Exception as e:
        print(f"Error getting question results: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/get_session_results', methods=['GET'])
def get_session_results():
    """Get results for a session"""
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
        # Get all session IDs, ordered by start time (newest first)
        session_ids = redis_client.zrevrange("sessions", 0, -1)
        
        sessions = []
        for session_id in session_ids:
            # Get session data
            session_data = redis_client.hgetall(f"session:{session_id}")
            if not session_data:
                continue
                
            sessions.append({
                "session_id": session_id,
                "start_time": session_data.get("timestamp_start"),
                "end_time": session_data.get("timestamp_end"),
                "status": session_data.get("status"),
                "total_images": int(session_data.get("total_images", 0))
            })
        
        return jsonify({"sessions": sessions})
        
    except Exception as e:
        print(f"Error getting all sessions: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/get_session_questions', methods=['GET'])
def get_session_questions_api():
    """Get all questions for a session"""
    try:
        session_id = request.args.get('session_id')
        if not session_id:
            return jsonify({"error": "No session_id provided"}), 400
            
        questions = get_session_questions(session_id)
        return jsonify({"questions": questions})
        
    except Exception as e:
        print(f"Error getting session questions: {e}")
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

        # Get all questions for this session
        question_ids = redis_client.smembers(f"session:{session_id}:questions")
        
        # For each question, delete its frames and then the question itself
        for question_id in question_ids:
            # Get all frames for this question
            frame_ids = redis_client.smembers(f"question:{question_id}:frames")
            
            # Delete each frame
            for frame_id in frame_ids:
                redis_client.delete(f"frame:{frame_id}")
                
            # Delete question's frame set
            redis_client.delete(f"question:{question_id}:frames")
            
            # Delete question
            redis_client.delete(f"question:{question_id}")
        
        # Delete session's question set
        redis_client.delete(f"session:{session_id}:questions")
        
        # Delete session
        redis_client.delete(f"session:{session_id}")
        
        # Remove from sessions sorted set
        redis_client.zrem("sessions", session_id)

        # Remove session directory if it exists
        session_dir = os.path.join(SESSIONS_DIR, session_id)
        if os.path.exists(session_dir):
            shutil.rmtree(session_dir)

        return jsonify({
            "status": "success", 
            "message": f"Session {session_id} and all associated data cleared"
        })

    except Exception as e:
        print(f"Error clearing session: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    try:
        # Check Redis connection
        redis_status = redis_client.ping()
    except Exception as e:
        redis_status = False
        
    return jsonify({
        "status": "healthy",
        "model_loaded": True,
        "redis_connected": redis_status,
        "server_time": datetime.now().isoformat()
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5110)