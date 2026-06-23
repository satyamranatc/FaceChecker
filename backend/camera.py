import os
import cv2
import numpy as np
import time
import threading
from model_utils import predict_face, train_classifier, reload_classifier, FACES_DIR
from tracker import AttendanceTracker

class VideoCamera:
    def __init__(self, tracker: AttendanceTracker):
        self.tracker = tracker
        
        # Load OpenCV's built-in Haar Cascade Face Detector
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        if self.face_cascade.empty():
            print("Warning: Failed to load Haar Cascade face detector.")
            
        # Try to initialize physical webcam
        # On macOS, this might require terminal permissions
        self.video = cv2.VideoCapture(0)
        self.is_camera_open = self.video.isOpened()
        
        if not self.is_camera_open:
            print("Warning: Webcam could not be opened. Using simulated placeholder feed.")
            
        # Camera states
        self.is_running = True
        self.lock = threading.Lock()
        
        # Registration states
        self.capture_mode = False
        self.register_id = ""
        self.captured_count = 0
        self.target_capture_count = 20
        self.last_capture_time = 0
        self.is_training = False
        self.training_progress = "Idle"
        self.training_logs = []
        
    def __del__(self):
        if hasattr(self, 'video') and self.video.isOpened():
            self.video.release()

    def draw_premium_face_overlay(self, frame, x, y, w, h, label, box_color, is_capturing):
        """Draw a clean, minimalist portrait frame and text badge (warm, human aesthetic)."""
        t_box = 2
        
        # 1. Draw elegant thin bounding box around the student's face
        cv2.rectangle(frame, (x, y), (x + w, y + h), box_color, t_box)
        
        # 2. Text badge background and name tag
        font_scale = 0.58
        font_thickness = 2
        (text_width, text_height), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness)
        
        # Padding around text
        pad_x = 10
        pad_y = 6
        
        badge_w = text_width + (pad_x * 2)
        badge_h = text_height + (pad_y * 2)
        
        badge_y1 = y - badge_h - 2
        badge_y2 = y - 2
        if badge_y1 < 0:
            badge_y1 = y + h + 2
            badge_y2 = y + h + badge_h + 2
            
        badge_x1 = x
        badge_x2 = x + badge_w
        
        # Draw translucent badge background (warm dark charcoal)
        badge_bg = (24, 24, 27) # Dark warm grey (BGR representation)
        cv2.rectangle(frame, (badge_x1, badge_y1), (badge_x2, badge_y2), badge_bg, -1)
        # Match thin badge border to the warm box_color
        cv2.rectangle(frame, (badge_x1, badge_y1), (badge_x2, badge_y2), box_color, 1)
        
        # Draw name text inside badge
        text_y = badge_y2 - pad_y if badge_y1 < y else badge_y1 + pad_y + text_height
        cv2.putText(frame, label, (badge_x1 + pad_x, text_y), 
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), font_thickness, cv2.LINE_AA)

    def start_registration(self, student_id):
        """Enable capture mode to register photos of a new student."""
        with self.lock:
            self.register_id = student_id
            self.captured_count = 0
            self.capture_mode = True
            self.training_progress = "Capturing faces..."
            print(f"Started registration capture for student: {student_id}")

    def run_training_in_background(self):
        """Worker thread to run Keras retraining without blocking video stream."""
        self.is_training = True
        self.training_progress = "Training AI model..."
        with self.lock:
            self.training_logs = ["Retraining thread started..."]
        print(" retrain thread started...")
        
        def update_progress(msg):
            with self.lock:
                self.training_progress = msg
                # Append if not duplicate of the last entry
                if not self.training_logs or self.training_logs[-1] != msg:
                    self.training_logs.append(msg)
                
        try:
            success = train_classifier(progress_callback=update_progress)
            with self.lock:
                self.is_training = False
                if success:
                    self.training_progress = "Retraining completed!"
                    self.training_logs.append("Retraining completed successfully!")
                    reload_classifier()
                else:
                    self.training_progress = "Training failed."
                    self.training_logs.append("Retraining failed.")
                # Reset back to inference mode
                self.capture_mode = False
                self.register_id = ""
        except Exception as e:
            print(f"Exception in retraining thread: {e}")
            with self.lock:
                self.is_training = False
                self.training_progress = "Training crashed."
                self.training_logs.append(f"Retraining crashed: {str(e)}")
                self.capture_mode = False
                self.register_id = ""
        print(" retrain thread finished.")

    def get_frame(self):
        """
        Capture a frame, process face detection/recognition/capture,
        draw overlays, and return JPEG bytes.
        """
        success = False
        frame = None
        
        if self.is_camera_open:
            success, frame = self.video.read()
            
        if not success or frame is None:
            # Generate simulated frame if camera is missing (graceful degradation)
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            # Create a nice dark gradient pattern for placeholder
            for y in range(480):
                color = int(20 + 30 * (y / 480))
                frame[y, :, :] = [color, color, color]
            
            # Draw a simulated web-cam indicator and error notice
            cv2.putText(frame, "Webcam Unavailable (No Permission or in Use)", (30, 220), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 100, 255), 2, cv2.LINE_AA)
            cv2.putText(frame, "Simulation Active - Feed is simulated", (30, 260), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1, cv2.LINE_AA)
            
            # Simulated blinking red dot
            if int(time.time()) % 2 == 0:
                cv2.circle(frame, (30, 40), 10, (0, 0, 255), -1)
                cv2.putText(frame, "SIM LIVE", (50, 45), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2, cv2.LINE_AA)
            else:
                cv2.putText(frame, "SIM LIVE", (50, 45), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 2, cv2.LINE_AA)
            
            # Simulate a face in simulation mode to allow testing without webcam!
            mock_x, mock_y, mock_w, mock_h = 240, 140, 160, 160
            
            if self.capture_mode and not self.is_training:
                mock_label = f"Capturing: {self.captured_count}/{self.target_capture_count}"
                mock_color = (255, 180, 0) # Cyan/Blue BGR
            elif self.is_training:
                mock_label = "AI Retraining..."
                mock_color = (10, 159, 255) # Orange BGR
            else:
                mock_label = "Demo Student (100%)"
                mock_color = (88, 209, 48) # Emerald Green BGR
                
            self.draw_premium_face_overlay(frame, mock_x, mock_y, mock_w, mock_h, mock_label, mock_color, self.capture_mode)
            
            # Track attendance for the demo student
            if not self.capture_mode and not self.is_training:
                self.tracker.update_presence("Demo Student")
                
            # Convert to JPEG bytes
            ret, jpeg = cv2.imencode('.jpg', frame)
            return jpeg.tobytes()
            
        # Flip frame horizontally for natural selfie view
        frame = cv2.flip(frame, 1)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Detect faces
        faces = self.face_cascade.detectMultiScale(
            gray, 
            scaleFactor=1.1, 
            minNeighbors=5, 
            minSize=(60, 60)
        )
        
        current_time = time.time()
        
        with self.lock:
            is_capturing = self.capture_mode and not self.is_training
            current_register_id = self.register_id
            
        for (x, y, w, h) in faces:
            # Crop face region
            face_crop = frame[y:y+h, x:x+w]
            
            if is_capturing:
                box_color = (255, 180, 0) # Cyan/Blue BGR
                label = f"Capturing: {self.captured_count}/{self.target_capture_count}"
                
                # Limit photo capture interval to 0.25 seconds to gather diverse poses
                if current_time - self.last_capture_time > 0.25:
                    student_dir = os.path.join(FACES_DIR, current_register_id)
                    os.makedirs(student_dir, exist_ok=True)
                    
                    img_path = os.path.join(student_dir, f'face_{self.captured_count}.jpg')
                    # Save the cropped face
                    cv2.imwrite(img_path, face_crop)
                    
                    self.captured_count += 1
                    self.last_capture_time = current_time
                    print(f"Captured {self.captured_count}/{self.target_capture_count} for {current_register_id}")
                    
                    if self.captured_count >= self.target_capture_count:
                        # Reached target photo count, initiate background Keras training
                        with self.lock:
                            self.capture_mode = False  # Exit capture mode
                        threading.Thread(target=self.run_training_in_background).start()
                
                self.draw_premium_face_overlay(frame, x, y, w, h, label, box_color, is_capturing)
            else:
                # Inference mode - run face recognition model
                if not self.is_training:
                    name, conf = predict_face(face_crop)
                    
                    if name != "Unknown":
                        # Log presence
                        self.tracker.update_presence(name)
                        # Retrieve display name if available in tracker
                        display_name = self.tracker.get_student_name(name) or name
                        label = f"{display_name} ({int(conf * 100)}%)"
                        box_color = (88, 209, 48)  # Apple Green BGR (Emerald)
                    else:
                        label = "Unknown"
                        box_color = (58, 69, 255)  # Apple Red BGR (Coral)
                        
                    self.draw_premium_face_overlay(frame, x, y, w, h, label, box_color, is_capturing)
                                
        # Add visual overlay indicator (LIVE webcam indicator)
        if not self.is_training:
            cv2.circle(frame, (30, 40), 10, (0, 255, 0), -1)
            cv2.putText(frame, "LIVE CAMERA", (50, 45), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2, cv2.LINE_AA)
        else:
            # Blinking yellow training indicator
            color = (0, 180, 255) if int(time.time() * 2) % 2 == 0 else (0, 100, 150)
            cv2.putText(frame, "AI RETRAINING IN PROGRESS...", (30, 45), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)
            
        ret, jpeg = cv2.imencode('.jpg', frame)
        return jpeg.tobytes()
