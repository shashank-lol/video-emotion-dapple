# Emotion Analysis API Documentation

## Overview
This API allows you to analyze emotions in images through a hierarchical system of sessions, questions, and frames. Each session can contain multiple questions, and each question can contain multiple frames (images).

## Base URL
```
http://your-server:5110
```

## Authentication
No authentication is currently required.

## Endpoints

### Session Management

#### Start a New Session
```
POST /start_session
```

Creates a new session for emotion analysis.

**Request Body:** None

**Response:**
```json
{
  "status": "success",
  "message": "Session started",
  "session_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ab"
}
```

#### End a Session
```
POST /end_session
```

Ends a session, processes all data, and generates final results.

**Request Body (form-data):**
- `session_id` (required): ID of the session to end

**Response:**
```json
{
  "status": "success",
  "message": "Session ended successfully",
  "session_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
  "results": {
    "session_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
    "total_questions": 3,
    "total_frames": 25,
    "average_emotion": "Happy",
    "average_confidence": 0.87,
    "emotion_distribution": {
      "Happy": 15,
      "Neutral": 5,
      "Surprise": 3,
      "Sad": 2
    },
    "questions": [
      {
        "question_id": "q1",
        "total_frames": 10,
        "average_emotion": "Happy",
        "emotion_distribution": {
          "Happy": 7,
          "Neutral": 3
        }
      },
      // more questions...
    ],
    "session_summary": {
      "most_common_emotion": "Happy",
      "least_common_emotion": "Sad",
      "emotion_variability": "Moderate mood fluctuations",
      "overall_trend": "Predominantly positive emotions",
      "notable_observations": [
        "Happy was the dominant emotion across all questions.",
        "Detected 4 different emotions across 3 questions.",
        "Average confidence level: 87.0%"
      ]
    }
  }
}
```

#### Clear a Session
```
POST /clear_session
```

Deletes a session and all associated questions and frames.

**Request Body (form-data):**
- `session_id` (required): ID of the session to delete

**Response:**
```json
{
  "status": "success",
  "message": "Session a1b2c3d4-e5f6-7890-abcd-1234567890ab and all associated data cleared"
}
```

### Frame Upload

#### Upload a Frame for Analysis
```
POST /upload_frame
```

Analyzes a single image frame and associates it with a specific question in a session.

**Request Body (form-data):**
- `session_id` (required): ID of the active session
- `question_id` (required): ID of the question (provided by your frontend)
- `image` (required): Image file to analyze (PNG, JPG, JPEG, or GIF)

**Response:**
```json
{
  "status": "success",
  "session_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
  "question_id": "q1",
  "frame_id": "f1b2c3d4-e5f6-7890-abcd-1234567890ab",
  "emotion": "Happy",
  "confidence": 0.92
}
```

### Results Retrieval

#### Get Question Results
```
GET /get_question_results
```

Retrieves results for a specific question.

**Query Parameters:**
- `question_id` (required): ID of the question

**Response:**
```json
{
  "question_id": "q1",
  "total_frames": 10,
  "average_emotion": "Happy",
  "average_confidence": 0.88,
  "emotion_distribution": {
    "Happy": 7,
    "Neutral": 2,
    "Surprise": 1
  },
  "summary": {
    "most_common_emotion": "Happy",
    "least_common_emotion": "Surprise",
    "emotion_variability": "Moderate mood fluctuations",
    "overall_trend": "Predominantly positive emotions",
    "notable_observations": [
      "Happy was the dominant emotion.",
      "Detected 3 different emotions.",
      "Average confidence level: 88.0%"
    ]
  }
}
```

#### Get Session Results
```
GET /get_session_results
```

Retrieves aggregated results for an entire session, including all questions.

**Query Parameters:**
- `session_id` (required): ID of the session

**Response:**
```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
  "session_status": "active",
  "total_questions": 3,
  "total_frames": 25,
  "average_emotion": "Happy",
  "average_confidence": 0.87,
  "emotion_distribution": {
    "Happy": 15,
    "Neutral": 5,
    "Surprise": 3,
    "Sad": 2
  },
  "questions": [
    {
      "question_id": "q1",
      "total_frames": 10,
      "average_emotion": "Happy",
      "emotion_distribution": {
        "Happy": 7,
        "Neutral": 3
      }
    },
    // more questions...
  ],
  "session_summary": {
    "most_common_emotion": "Happy",
    "least_common_emotion": "Sad",
    "emotion_variability": "Moderate mood fluctuations",
    "overall_trend": "Predominantly positive emotions",
    "notable_observations": [
      "Happy was the dominant emotion across all questions.",
      "Detected 4 different emotions across 3 questions.",
      "Average confidence level: 87.0%"
    ]
  }
}
```

#### Get All Sessions
```
GET /get_all_sessions
```

Retrieves a list of all sessions.

**Query Parameters:** None

**Response:**
```json
{
  "sessions": [
    {
      "session_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
      "start_time": "2025-02-21T14:30:00.000Z",
      "end_time": "2025-02-21T14:45:00.000Z",
      "status": "completed",
      "total_images": 25
    },
    {
      "session_id": "b2c3d4e5-f6a7-8901-bcde-23456789abcd",
      "start_time": "2025-02-21T13:00:00.000Z",
      "end_time": null,
      "status": "active",
      "total_images": 12
    }
  ]
}
```

#### Get Session Questions
```
GET /get_session_questions
```

Retrieves all questions for a specific session.

**Query Parameters:**
- `session_id` (required): ID of the session

**Response:**
```json
{
  "questions": [
    {
      "question_id": "q1",
      "timestamp": "2025-02-21T14:30:10.000Z",
      "total_frames": 10,
      "results": {
        "question_id": "q1",
        "total_frames": 10,
        "average_emotion": "Happy",
        "average_confidence": 0.88,
        "emotion_distribution": {
          "Happy": 7,
          "Neutral": 2,
          "Surprise": 1
        },
        "summary": {
          "most_common_emotion": "Happy",
          "least_common_emotion": "Surprise",
          "emotion_variability": "Moderate mood fluctuations",
          "overall_trend": "Predominantly positive emotions",
          "notable_observations": [
            "Happy was the dominant emotion.",
            "Detected 3 different emotions.",
            "Average confidence level: 88.0%"
          ]
        }
      }
    },
    // more questions...
  ]
}
```

### System Information

#### Health Check
```
GET /health
```

Checks if the API is running and if the model is loaded.

**Response:**
```json
{
  "status": "healthy",
  "model_loaded": true,
  "server_time": "2025-02-21T14:30:00.000Z"
}
```

## Data Types

### Emotions
The following emotions are detected by the system:
- `Angry`
- `Disgust` 
- `Fear`
- `Happy`
- `Sad`
- `Surprise`
- `Neutral`

### Session Status
A session can have the following status values:
- `active`: Session is ongoing and can accept new frames
- `completed`: Session has been ended and results are finalized

### File Types
Allowed image file types:
- PNG (`.png`)
- JPEG (`.jpg`, `.jpeg`)
- GIF (`.gif`)

## Error Handling

All endpoints return appropriate HTTP status codes:
- `200 OK`: Request processed successfully
- `400 Bad Request`: Invalid parameters or request
- `404 Not Found`: Session or question not found
- `500 Internal Server Error`: Server-side error

Error responses follow this format:
```json
{
  "error": "Description of the error"
}
```

## Usage Flow

1. Start a session using `/start_session`
2. Upload frames with question IDs using `/upload_frame`
3. Get intermediate results using `/get_question_results` or `/get_session_results`
4. End the session using `/end_session` when done
5. Get final results using `/get_session_results`
