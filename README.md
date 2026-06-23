# Aura Class Hub

Aura Class Hub is a warm, reliable, and human-centered classroom management portal designed to simplify attendance and student records. Built on-device with privacy at its core, Aura recognizes face shapes locally to automate attendance sheet check-ins without cloud database syncs or external latencies.

## Human-Centric Design Principles

- **Humanist Typography**: Crafted using a classic editorial serif **Lora** for headings paired with a clean, warm sans-serif **Plus Jakarta Sans** for readable body copy and tabular stats.
- **Relatable Imagery & Layout**: Devoid of cold AI graphics, robot indicators, linear grid scans, or complex telemetry dashboards. Instead, it utilizes clean portrait boxes and simple class community cards.
- **Warm & Trustworthy Experience**: Communicates with friendly, clear classroom terminology (Roster entries, portrait frames, roster updates) rather than high-tech biometrics and neural net fitting jargon.

## Key Features

- **Robust SQLite Database Backend**: Moves from file-based JSON sheets to local SQLite storage (`data/attendance.db`) with relational integrity and automatic legacy migrations.
- **Complete Student Roster CRUD**:
  - **Create**: Add a student manually directly by name.
  - **Read**: Browse student directories and register photos.
  - **Update**: Edit registered student names inline.
  - **Delete**: Remove a student entirely. Clears face photos, database profiles, and automatically cascades to wipe attendance records before refitting local models.
- **Webcam Portrait Verification**: Integrates a clean, border-only frame scanner running localized image models (OpenCV cascades + MobileNetV2 embeddings) on-device.
- **Interactive Class Sheets**: Check daily lists, filter by presence status ("All", "Present", "Absent"), and override records with manual Present/Absent toggles.
- **Visual Analytics**: View weekly attendance trend curves and hourly check-in distribution columns.

---

## Getting Started

### Prerequisites

- **Python 3.8+**
- **Node.js 16+**

### Easy Startup (Single Script)

You can launch both the frontend and backend servers concurrently using the provided shell script:

```bash
chmod +x run.sh
./run.sh
```

- **Roster & Attendance App**: [http://localhost:5173](http://localhost:5173)
- **API Portal**: [http://localhost:8000](http://localhost:8000)

---

## Manual Execution Steps

If you prefer to start the servers separately:

### 1. Backend Server Setup & Start

Navigate to the `backend` folder, set up the virtual environment, and run FastAPI:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 2. Frontend Server Setup & Start

Navigate to the `frontend` folder, install Node modules, and run the Vite bundler:

```bash
cd frontend
npm install
npm run dev
```
