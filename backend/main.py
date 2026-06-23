from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from tracker import AttendanceTracker
from camera import VideoCamera
from model_utils import load_classifier_for_inference

app = FastAPI(title="Student Attendance Face Checker API")

# Allow all origins or React development origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

tracker = AttendanceTracker()
camera = VideoCamera(tracker)

# Pre-load classifier if it exists
load_classifier_for_inference()

class RegisterRequest(BaseModel):
    name: str

class MarkAttendanceRequest(BaseModel):
    student_id: str
    date: str
    status: str

def gen(camera_obj):
    """Video streaming generator function."""
    while True:
        try:
            frame = camera_obj.get_frame()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')
        except Exception as e:
            print(f"Error in video generator: {e}")
            break

@app.get("/api/video_feed")
async def video_feed():
    """Video streaming route. Put this in the src attribute of an img tag."""
    return StreamingResponse(gen(camera), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/api/students")
async def get_students():
    """Get all registered students."""
    return tracker.get_students()

@app.get("/api/attendance")
async def get_attendance(date: str = Query(None)):
    """Get attendance records for a specific date (defaults to today)."""
    return tracker.get_attendance_records(date)

@app.post("/api/attendance/mark")
async def mark_attendance(payload: MarkAttendanceRequest):
    """Manually toggle a student present/absent on a sheet."""
    success = tracker.mark_attendance(payload.student_id, payload.date, payload.status)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to mark attendance. Check student_id.")
    return {"success": True, "message": f"Student {payload.student_id} marked as {payload.status} for {payload.date}."}

@app.get("/api/attendance/dates")
async def get_attendance_dates():
    """List all logged attendance dates."""
    return tracker.get_attendance_dates()

@app.get("/api/attendance/summary")
async def get_attendance_summary():
    """Get Chart.js data and KPI metrics."""
    return tracker.get_analytics_summary()

@app.post("/api/register")
async def register_student(payload: RegisterRequest):
    """Trigger student registration and capture mode."""
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Student name cannot be empty")
        
    # Check if name is alphanumeric/whitespace
    clean_name = "".join(c for c in name if c.isalnum() or c.isspace())
    if not clean_name:
        raise HTTPException(status_code=400, detail="Invalid student name")
        
    student_id = tracker.register_student(clean_name)
    
    # Start capturing frames for this student
    camera.start_registration(student_id)
    
    return {
        "success": True, 
        "student_id": student_id,
        "message": f"Started capturing face frames for '{clean_name}'. Please look at the camera."
    }

@app.post("/api/session/reset")
async def reset_session():
    """Reset the current attendance session."""
    tracker.reset_session()
    return {"success": True, "message": "Attendance session reset successfully"}

@app.get("/api/status")
async def get_status():
    """Get camera and training/capture status."""
    with camera.lock:
        status_data = {
            "camera_active": camera.is_camera_open,
            "capture_mode": camera.capture_mode,
            "register_id": camera.register_id,
            "captured_count": camera.captured_count,
            "target_capture_count": camera.target_capture_count,
            "is_training": camera.is_training,
            "training_progress": camera.training_progress,
            "training_logs": camera.training_logs
        }
    return status_data

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
# Trigger reload to parse updated attendance logs
