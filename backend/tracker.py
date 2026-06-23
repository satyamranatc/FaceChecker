import os
import json
import time
import sqlite3
from datetime import datetime, timedelta

# Paths
STUDENTS_CONFIG_PATH = 'data/students.json'
ATTENDANCE_LOG_PATH = 'data/attendance.json'

def load_json(path, default):
    """Load json helper."""
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading JSON file {path}: {e}")
            return default
    return default

class AttendanceTracker:
    def __init__(self):
        self.db_path = 'data/attendance.db'
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.away_threshold = 15  # seconds to wait before marking a student as "Away"
        
        # Initialize SQLite tables
        self.init_db()
        
        # Migrate legacy data from JSON if it exists
        self.migrate_legacy_data()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Enable foreign key support
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        # Create students table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                registered_at TEXT NOT NULL
            );
        """)
        
        # Create attendance table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                date TEXT NOT NULL,
                check_in TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                last_seen_epoch REAL NOT NULL,
                total_seconds REAL NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                UNIQUE(student_id, date)
            );
        """)
        
        conn.commit()
        conn.close()

    def migrate_legacy_data(self):
        students_json_path = STUDENTS_CONFIG_PATH
        attendance_json_path = ATTENDANCE_LOG_PATH
        
        if os.path.exists(students_json_path):
            print("Found legacy students.json. Migrating to SQLite...")
            try:
                students_data = load_json(students_json_path, {})
                
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                for s_id, s_info in students_data.items():
                    cursor.execute(
                        "INSERT OR IGNORE INTO students (id, name, registered_at) VALUES (?, ?, ?)",
                        (s_id, s_info["name"], s_info.get("registered_at", datetime.now().isoformat()))
                    )
                conn.commit()
                conn.close()
                os.rename(students_json_path, students_json_path + '.bak')
                print("Successfully migrated student registry to SQLite.")
            except Exception as e:
                print(f"Error migrating students.json: {e}")
                
        if os.path.exists(attendance_json_path):
            print("Found legacy attendance.json. Migrating to SQLite...")
            try:
                attendance_data = load_json(attendance_json_path, {})
                
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                for date_str, date_sheet in attendance_data.items():
                    try:
                        datetime.strptime(date_str, "%Y-%m-%d")
                    except ValueError:
                        continue # Skip malformed keys
                        
                    for s_id, record in date_sheet.items():
                        # Ensure student exists in DB
                        cursor.execute("SELECT id FROM students WHERE id = ?", (s_id,))
                        if not cursor.fetchone():
                            cursor.execute(
                                "INSERT INTO students (id, name, registered_at) VALUES (?, ?, ?)",
                                (s_id, record["name"], datetime.now().isoformat())
                            )
                            
                        cursor.execute(
                            """
                            INSERT OR IGNORE INTO attendance 
                            (student_id, date, check_in, last_seen, last_seen_epoch, total_seconds, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                s_id,
                                date_str,
                                record["check_in"],
                                record["last_seen"],
                                record.get("last_seen_epoch", time.time()),
                                record.get("total_seconds", 0.0),
                                record["status"]
                            )
                        )
                conn.commit()
                conn.close()
                os.rename(attendance_json_path, attendance_json_path + '.bak')
                print("Successfully migrated attendance records to SQLite.")
            except Exception as e:
                print(f"Error migrating attendance.json: {e}")

    def register_student(self, student_name):
        """Register a new student with a unique ID."""
        student_id = student_name.lower().replace(" ", "_")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM students WHERE id = ?", (student_id,))
        exists = cursor.fetchone()
        
        if not exists:
            registered_at = datetime.now().isoformat()
            cursor.execute(
                "INSERT INTO students (id, name, registered_at) VALUES (?, ?, ?)",
                (student_id, student_name, registered_at)
            )
            conn.commit()
            print(f"Student '{student_name}' registered successfully.")
            
        conn.close()
        return student_id

    def create_student_manual(self, student_name):
        """CRUD Create: Add a student manually (without starting webcam capture immediately)"""
        student_id = student_name.lower().replace(" ", "_")
        if not student_id.strip():
            return False, "Invalid name."
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM students WHERE id = ?", (student_id,))
        if cursor.fetchone():
            conn.close()
            return False, f"Student with ID '{student_id}' already exists."
            
        registered_at = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO students (id, name, registered_at) VALUES (?, ?, ?)",
            (student_id, student_name, registered_at)
        )
        conn.commit()
        conn.close()
        return True, student_id

    def update_student(self, student_id, new_name):
        """CRUD Update: Update a student's name"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM students WHERE id = ?", (student_id,))
        if not cursor.fetchone():
            conn.close()
            return False, "Student not found."
            
        cursor.execute("UPDATE students SET name = ? WHERE id = ?", (new_name, student_id))
        
        conn.commit()
        conn.close()
        return True, "Student updated successfully."

    def delete_student(self, student_id):
        """CRUD Delete: Delete a student and their face images directory"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM students WHERE id = ?", (student_id,))
        if not cursor.fetchone():
            conn.close()
            return False, "Student not found."
            
        # Due to PRAGMA foreign_keys = ON, attendance logs for this student delete automatically on cascade
        cursor.execute("DELETE FROM students WHERE id = ?", (student_id,))
        conn.commit()
        conn.close()
        
        # Delete faces directory
        import shutil
        faces_dir = os.path.join('data/faces', student_id)
        if os.path.exists(faces_dir):
            try:
                shutil.rmtree(faces_dir)
            except Exception as e:
                print(f"Error removing faces directory {faces_dir}: {e}")
                
        # Clean up mapping file if it exists
        mapping_path = 'data/class_mapping.json'
        if os.path.exists(mapping_path):
            try:
                with open(mapping_path, 'r') as f:
                    mapping = json.load(f)
                if student_id in mapping:
                    del mapping[student_id]
                    # Update indices
                    new_mapping = {cls_name: idx for idx, cls_name in enumerate(sorted(mapping.keys()))}
                    with open(mapping_path, 'w') as f:
                        json.dump(new_mapping, f, indent=4)
            except Exception as e:
                print(f"Error cleaning class mapping: {e}")
                
        # Clean up feature cache npz file to remove cached embeddings for this student's images
        cache_path = 'data/feature_cache.npz'
        if os.path.exists(cache_path):
            try:
                loaded = np.load(cache_path, allow_pickle=True)
                cache = loaded['cache'].item()
                # Remove keys matching this student
                new_cache = {k: v for k, v in cache.items() if not k.startswith(f"{student_id}/")}
                np.savez_compressed(cache_path, cache=new_cache)
            except Exception as e:
                print(f"Error cleaning feature cache npz: {e}")
                
        return True, "Student deleted successfully."

    def get_students(self):
        """Get list of registered students with face image counts."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, registered_at FROM students ORDER BY name ASC")
        rows = cursor.fetchall()
        conn.close()
        
        students = []
        for r in rows:
            faces_dir = os.path.join('data/faces', r[0])
            face_count = 0
            if os.path.exists(faces_dir):
                face_count = len([f for f in os.listdir(faces_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
                
            students.append({
                "id": r[0],
                "name": r[1],
                "registered_at": r[2],
                "face_count": face_count
            })
        return students

    def update_presence(self, student_name, date_str=None):
        """
        Record that a student was detected.
        Accumulates attendance time if they were seen recently on date_str.
        """
        student_id = student_name.lower().replace(" ", "_")
        current_time = time.time()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Ensure student exists in DB
        cursor.execute("SELECT id FROM students WHERE id = ?", (student_id,))
        if not cursor.fetchone():
            registered_at = datetime.now().isoformat()
            cursor.execute(
                "INSERT INTO students (id, name, registered_at) VALUES (?, ?, ?)",
                (student_id, student_name, registered_at)
            )
            conn.commit()
            
        # Get existing attendance record
        cursor.execute(
            "SELECT check_in, last_seen, last_seen_epoch, total_seconds, status FROM attendance WHERE student_id = ? AND date = ?",
            (student_id, date_str)
        )
        row = cursor.fetchone()
        
        if not row:
            # First check-in of the day
            cursor.execute(
                """
                INSERT INTO attendance (student_id, date, check_in, last_seen, last_seen_epoch, total_seconds, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (student_id, date_str, now_str, now_str, current_time, 1.0, "Active")
            )
        else:
            check_in, last_seen, last_seen_epoch, total_seconds, status = row
            elapsed = current_time - last_seen_epoch
            
            new_total_seconds = total_seconds
            if elapsed <= self.away_threshold:
                new_total_seconds += elapsed
                
            cursor.execute(
                """
                UPDATE attendance 
                SET last_seen = ?, last_seen_epoch = ?, total_seconds = ?, status = ?
                WHERE student_id = ? AND date = ?
                """,
                (now_str, current_time, new_total_seconds, "Active", student_id, date_str)
            )
            
        conn.commit()
        conn.close()

    def clean_statuses(self, date_str=None):
        """
        Mark students as 'Away' if they haven't been seen recently today.
        """
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
            
        current_time = time.time()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # If check-in was manual, elapsed check is bypassed
        cursor.execute(
            """
            UPDATE attendance
            SET status = 'Away'
            WHERE date = ? AND status = 'Active' AND check_in != 'Manual Override' AND (? - last_seen_epoch) > ?
            """,
            (date_str, current_time, self.away_threshold)
        )
        
        conn.commit()
        conn.close()

    def get_attendance_records(self, date_str=None):
        """
        Get the attendance sheet for a specific date.
        Returns a list of ALL registered students with check-in info and status (Active, Away, Present, or Absent).
        """
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
            
        today_str = datetime.now().strftime("%Y-%m-%d")
        if date_str == today_str:
            self.clean_statuses(date_str)
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, name FROM students ORDER BY name ASC")
        students = cursor.fetchall()
        
        cursor.execute(
            "SELECT student_id, check_in, last_seen, last_seen_epoch, total_seconds, status FROM attendance WHERE date = ?",
            (date_str,)
        )
        date_sheet = {row[0]: row for row in cursor.fetchall()}
        conn.close()
        
        records = []
        for s_id, s_name in students:
            if s_id in date_sheet:
                _, check_in, last_seen, last_seen_epoch, total_seconds, status = date_sheet[s_id]
                
                # Format duration
                m = int(total_seconds) // 60
                s = int(total_seconds) % 60
                duration_str = f"{m}m {s}s" if m > 0 else f"{s}s"
                
                display_status = status
                if date_str != today_str and status in ["Active", "Away"]:
                    display_status = "Present"
                    
                records.append({
                    "id": s_id,
                    "name": s_name,
                    "check_in": check_in,
                    "last_seen": last_seen,
                    "last_seen_epoch": last_seen_epoch,
                    "total_seconds": total_seconds,
                    "minutes": round(total_seconds / 60.0, 2),
                    "duration_str": duration_str,
                    "status": display_status
                })
            else:
                records.append({
                    "id": s_id,
                    "name": s_name,
                    "check_in": "-",
                    "last_seen": "-",
                    "total_seconds": 0.0,
                    "minutes": 0.0,
                    "duration_str": "-",
                    "status": "Absent"
                })
        return records

    def mark_attendance(self, student_id, date_str, status):
        """
        Manually override a student's attendance status for a given date.
        status: 'Present' or 'Absent'
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check student exists
        cursor.execute("SELECT name FROM students WHERE id = ?", (student_id,))
        student_row = cursor.fetchone()
        if not student_row:
            conn.close()
            return False
            
        s_name = student_row[0]
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
            
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        if status in ["Present", "Active"]:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_time = time.time()
            cursor.execute(
                """
                INSERT INTO attendance (student_id, date, check_in, last_seen, last_seen_epoch, total_seconds, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(student_id, date) DO UPDATE SET
                    check_in = 'Manual Override',
                    last_seen = excluded.last_seen,
                    last_seen_epoch = excluded.last_seen_epoch,
                    total_seconds = 300.0,
                    status = excluded.status
                """,
                (student_id, date_str, "Manual Override", now_str, current_time, 300.0, "Active" if date_str == today_str else "Present")
            )
        elif status == "Absent":
            cursor.execute("DELETE FROM attendance WHERE student_id = ? AND date = ?", (student_id, date_str))
            
        conn.commit()
        conn.close()
        return True

    def get_attendance_dates(self):
        """Get sorted list of all dates that have attendance logs."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT date FROM attendance ORDER BY date DESC")
        dates = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        today_str = datetime.now().strftime("%Y-%m-%d")
        if today_str not in dates:
            dates.append(today_str)
        return sorted(dates, reverse=True)

    def get_analytics_summary(self):
        """
        Compute dashboard KPIs and data points for Chart.js.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM students")
        total_students = cursor.fetchone()[0]
        
        today_str = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("SELECT COUNT(*) FROM attendance WHERE date = ?", (today_str,))
        today_present = cursor.fetchone()[0]
        
        today_rate = round((today_present / total_students * 100), 1) if total_students > 0 else 0.0
        
        cursor.execute("SELECT COUNT(*) FROM attendance WHERE date = ? AND status = 'Away'", (today_str,))
        today_away = cursor.fetchone()[0]
        
        weekly_labels = []
        weekly_data = []
        for i in range(6, -1, -1):
            date_dt = datetime.now() - timedelta(days=i)
            d_str = date_dt.strftime("%Y-%m-%d")
            d_label = date_dt.strftime("%a (%m/%d)")
            weekly_labels.append(d_label)
            
            cursor.execute("SELECT COUNT(*) FROM attendance WHERE date = ?", (d_str,))
            count = cursor.fetchone()[0]
            weekly_data.append(count)
            
        hourly_counts = [0] * 24
        cursor.execute("SELECT check_in FROM attendance WHERE check_in != 'Manual Override'")
        rows = cursor.fetchall()
        for r in rows:
            check_in_time = r[0]
            if check_in_time and ":" in check_in_time:
                try:
                    time_part = check_in_time.split(" ")[1]
                    hour = int(time_part.split(":")[0])
                    if 0 <= hour < 24:
                        hourly_counts[hour] += 1
                except Exception:
                    pass
                    
        conn.close()
        
        weekly_rates = [c / total_students * 100 if total_students > 0 else 0.0 for c in weekly_data]
        average_weekly_rate = round(sum(weekly_rates) / len(weekly_rates), 1)
        
        return {
            "kpis": {
                "total_students": total_students,
                "today_present": today_present,
                "today_rate": today_rate,
                "today_away": today_away,
                "weekly_average_rate": average_weekly_rate
            },
            "charts": {
                "weekly": {
                    "labels": weekly_labels,
                    "data": weekly_data
                },
                "hourly": {
                    "labels": [f"{h:02d}:00" for h in range(24)],
                    "data": hourly_counts
                }
            }
        }

    def reset_session(self):
        """Reset the attendance logs for the current day only."""
        today_str = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM attendance WHERE date = ?", (today_str,))
        conn.commit()
        conn.close()
        print(f"Attendance session for today ({today_str}) has been reset.")
