import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';
import { Line, Bar } from 'react-chartjs-2';
import { 
  Camera, 
  UserPlus, 
  Users, 
  RefreshCw, 
  Activity, 
  Cpu, 
  Clock, 
  CheckCircle, 
  AlertCircle, 
  Trash2,
  UserCheck,
  Calendar,
  LayoutDashboard,
  ArrowRight,
  TrendingUp,
  Award
} from 'lucide-react';

// Register Chart.js modules
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

const API_BASE_URL = `http://${window.location.hostname}:8000`;

// Helper to get formatted YYYY-MM-DD
const getTodayString = () => {
  const d = new Date();
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

function App() {
  // Navigation: 'dashboard' | 'scanner' | 'sheets'
  const [activeTab, setActiveTab] = useState('dashboard');
  
  // App States
  const [status, setStatus] = useState({
    camera_active: false,
    capture_mode: false,
    register_id: "",
    captured_count: 0,
    target_capture_count: 20,
    is_training: false,
    training_progress: "Idle",
    training_logs: []
  });
  
  const [students, setStudents] = useState([]);
  const [availableDates, setAvailableDates] = useState([getTodayString()]);
  const [selectedDate, setSelectedDate] = useState(getTodayString());
  const [sheetRecords, setSheetRecords] = useState([]);
  
  // KPI / Chart States
  const [analytics, setAnalytics] = useState({
    kpis: {
      total_students: 0,
      today_present: 0,
      today_rate: 0.0,
      today_away: 0,
      weekly_average_rate: 0.0
    },
    charts: {
      weekly: { labels: [], data: [] },
      hourly: { labels: [], data: [] }
    }
  });

  // Face Registration Form States
  const [registerName, setRegisterName] = useState("");
  const [isRegistering, setIsRegistering] = useState(false);
  const [registerError, setRegisterError] = useState("");
  const [registerSuccess, setRegisterSuccess] = useState("");
  
  // Search and overrides loading
  const [sheetSearch, setSheetSearch] = useState("");
  const [togglingStudents, setTogglingStudents] = useState({});
  
  // Ref for auto-scrolling training logs
  const logsContainerRef = useRef(null);

  // Poll server camera & retraining status
  const fetchStatus = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/status`);
      setStatus(response.data);
    } catch (error) {
      console.error("Error fetching status:", error);
    }
  };

  // Fetch student directory
  const fetchStudents = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/students`);
      setStudents(response.data);
    } catch (error) {
      console.error("Error fetching students:", error);
    }
  };

  // Fetch logged dates
  const fetchDates = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/attendance/dates`);
      setAvailableDates(response.data);
    } catch (error) {
      console.error("Error fetching dates:", error);
    }
  };

  // Fetch attendance sheet for selected date
  const fetchSheetRecords = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/attendance`, {
        params: { date: selectedDate }
      });
      setSheetRecords(response.data);
    } catch (error) {
      console.error("Error fetching sheet records:", error);
    }
  };

  // Fetch analytics summary
  const fetchAnalytics = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/attendance/summary`);
      setAnalytics(response.data);
    } catch (error) {
      console.error("Error fetching analytics:", error);
    }
  };

  // Initial and reactive updates
  useEffect(() => {
    fetchStatus();
    fetchStudents();
    fetchDates();
    fetchAnalytics();
  }, []);

  // Polling logic depending on tab or background retraining
  useEffect(() => {
    const statusInterval = setInterval(() => {
      fetchStatus();
    }, status.capture_mode || status.is_training ? 400 : 2000);

    return () => clearInterval(statusInterval);
  }, [status.capture_mode, status.is_training]);

  // Poll sheet records for selected date
  useEffect(() => {
    fetchSheetRecords();
    
    const sheetInterval = setInterval(() => {
      fetchSheetRecords();
    }, selectedDate === getTodayString() ? 1500 : 5000); // Poll fast if looking at today's check-ins

    return () => clearInterval(sheetInterval);
  }, [selectedDate]);

  // Poll analytics less frequently
  useEffect(() => {
    const analyticsInterval = setInterval(() => {
      fetchAnalytics();
    }, 5000);

    return () => clearInterval(analyticsInterval);
  }, []);

  // Scroll logs container to bottom on retraining update
  useEffect(() => {
    if (logsContainerRef.current) {
      logsContainerRef.current.scrollTop = logsContainerRef.current.scrollHeight;
    }
  }, [status.training_logs]);

  // Save Face registration handler
  const handleRegister = async (e) => {
    e.preventDefault();
    if (!registerName.trim()) {
      setRegisterError("Please enter a valid name.");
      return;
    }
    
    setIsRegistering(true);
    setRegisterError("");
    setRegisterSuccess("");

    try {
      const response = await axios.post(`${API_BASE_URL}/api/register`, {
        name: registerName
      });
      if (response.data.success) {
        setRegisterSuccess(response.data.message);
        setRegisterName("");
        fetchStatus();
        fetchStudents();
      }
    } catch (error) {
      const errMsg = error.response?.data?.detail || "Registration failed. Try again.";
      setRegisterError(errMsg);
    } finally {
      setIsRegistering(false);
    }
  };

  // Toggle manual attendance overrides (Present <-> Absent)
  const toggleAttendanceStatus = async (studentId, currentStatus) => {
    // Show spinner for this student
    setTogglingStudents(prev => ({ ...prev, [studentId]: true }));
    
    const newStatus = (currentStatus === 'Absent') ? 'Present' : 'Absent';
    
    try {
      const response = await axios.post(`${API_BASE_URL}/api/attendance/mark`, {
        student_id: studentId,
        date: selectedDate,
        status: newStatus
      });
      if (response.data.success) {
        // Immediately refresh sheet & dashboard statistics
        await fetchSheetRecords();
        await fetchAnalytics();
        fetchDates();
      }
    } catch (error) {
      console.error("Error setting attendance override:", error);
    } finally {
      setTogglingStudents(prev => ({ ...prev, [studentId]: false }));
    }
  };

  // Reset Session handler for today's logs
  const handleResetSession = async () => {
    if (window.confirm("Are you sure you want to reset today's attendance sheet? This will clear all check-ins for today.")) {
      try {
        const response = await axios.post(`${API_BASE_URL}/api/session/reset`);
        if (response.data.success) {
          fetchSheetRecords();
          fetchAnalytics();
        }
      } catch (error) {
        console.error("Error resetting session:", error);
      }
    }
  };

  // Filter sheet records based on search
  const filteredSheet = sheetRecords.filter(r => 
    r.name.toLowerCase().includes(sheetSearch.toLowerCase()) || 
    r.id.toLowerCase().includes(sheetSearch.toLowerCase())
  );

  // Find the most recently detected student for scanner view
  const lastDetected = sheetRecords.length > 0 && selectedDate === getTodayString()
    ? [...sheetRecords]
        .filter(r => r.status !== 'Absent' && r.last_seen_epoch)
        .sort((a, b) => b.last_seen_epoch - a.last_seen_epoch)[0]
    : null;

  // Chart configs (Amber glows and brushed Copper bars)
  const lineChartData = {
    labels: analytics.charts.weekly.labels,
    datasets: [{
      label: 'Students Present',
      data: analytics.charts.weekly.data,
      borderColor: '#f59e0b', // Amber line
      backgroundColor: 'rgba(245, 158, 11, 0.08)', // Glowing transparent amber fill
      borderWidth: 2,
      pointBackgroundColor: '#fbbf24',
      pointBorderColor: '#050505',
      pointHoverRadius: 6,
      pointHoverBackgroundColor: '#FFFFFF',
      pointRadius: 4,
      fill: true,
      tension: 0.38,
    }]
  };

  const lineChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: 'rgba(20, 20, 22, 0.95)',
        borderColor: 'rgba(245, 158, 11, 0.25)',
        borderWidth: 1,
        titleColor: '#FFFFFF',
        bodyColor: '#E4E4E7',
        padding: 10,
        cornerRadius: 8,
        displayColors: false
      }
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { color: '#71717A', font: { size: 10, family: 'monospace' } }
      },
      y: {
        grid: { color: 'rgba(255, 255, 255, 0.03)' },
        ticks: { color: '#71717A', font: { size: 10 }, stepSize: 1 }
      }
    }
  };

  const barChartData = {
    labels: analytics.charts.hourly.labels.slice(7, 20), // Show school hours 7:00 to 19:00
    datasets: [{
      label: 'Check-in Count',
      data: analytics.charts.hourly.data.slice(7, 20),
      backgroundColor: 'rgba(217, 119, 6, 0.35)', // Translucent copper bars
      hoverBackgroundColor: '#d97706', // Brushed copper on hover
      borderRadius: 6,
      borderWidth: 1,
      borderColor: 'rgba(217, 119, 6, 0.6)'
    }]
  };

  const barChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: 'rgba(20, 20, 22, 0.95)',
        borderColor: 'rgba(217, 119, 6, 0.25)',
        borderWidth: 1,
        titleColor: '#FFFFFF',
        bodyColor: '#E4E4E7',
        padding: 10,
        cornerRadius: 8,
        displayColors: false
      }
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { color: '#71717A', font: { size: 9, family: 'monospace' } }
      },
      y: {
        grid: { color: 'rgba(255, 255, 255, 0.03)' },
        ticks: { color: '#71717A', font: { size: 10 }, stepSize: 1 }
      }
    }
  };

  return (
    <div className="min-h-screen bg-[#050505] text-[#f4f4f5] px-6 py-8 md:px-16 flex flex-col justify-between selection:bg-zinc-800 selection:text-white relative z-0">
      
      {/* Floating blur orbs background */}
      <div className="orb-layer">
        <div className="bg-orb-indigo animate-float"></div>
        <div className="bg-orb-copper animate-float-reverse"></div>
        <div className="bg-orb-emerald"></div>
      </div>
      
      {/* Header */}
      <header className="w-full max-w-6xl mx-auto mb-8 flex flex-col md:flex-row md:items-end md:justify-between border-b border-zinc-900/60 pb-6">
        <div className="text-left">
          <h1 className="text-xl md:text-2xl font-semibold tracking-tight text-gradient-apple font-display">
            AetherScan Student Tracker
          </h1>
          <p className="text-xs text-zinc-500 mt-0.5 font-display">
            Class Sheets, Retraining Pipelines, and Biometric Statistics.
          </p>
        </div>

        {/* Global tab control navigation */}
        <div className="bg-[#141416]/70 backdrop-blur-md p-1.5 rounded-xl flex items-center border border-amber-600/15 mt-6 md:mt-0 max-w-sm shadow-inner shadow-black/60">
          <button 
            onClick={() => setActiveTab('dashboard')}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-[11px] font-semibold uppercase tracking-wider font-mono transition-all duration-300 ${
              activeTab === 'dashboard' 
                ? 'bg-gradient-to-br from-amber-600/20 to-amber-700/10 border border-amber-500/30 text-amber-200 shadow-lg shadow-black/40 scale-105' 
                : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.01]'
            }`}
          >
            <LayoutDashboard strokeWidth={1.5} className="h-3.5 w-3.5 text-amber-500" />
            Dashboard
          </button>
          
          <button 
            onClick={() => {
              setActiveTab('scanner');
              setSelectedDate(getTodayString()); // Sync to today
            }}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-[11px] font-semibold uppercase tracking-wider font-mono transition-all duration-300 ${
              activeTab === 'scanner' 
                ? 'bg-gradient-to-br from-amber-600/20 to-amber-700/10 border border-amber-500/30 text-amber-200 shadow-lg shadow-black/40 scale-105' 
                : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.01]'
            }`}
          >
            <Camera strokeWidth={1.5} className="h-3.5 w-3.5 text-amber-500" />
            Live Scanner
          </button>

          <button 
            onClick={() => setActiveTab('sheets')}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-[11px] font-semibold uppercase tracking-wider font-mono transition-all duration-300 ${
              activeTab === 'sheets' 
                ? 'bg-gradient-to-br from-amber-600/20 to-amber-700/10 border border-amber-500/30 text-amber-200 shadow-lg shadow-black/40 scale-105' 
                : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.01]'
            }`}
          >
            <Calendar strokeWidth={1.5} className="h-3.5 w-3.5 text-amber-500" />
            Sheets
          </button>
        </div>
      </header>

      {/* Main Layout Area */}
      <main className="w-full max-w-6xl mx-auto flex-1 mb-8">
        
        {/* Tab 1: Dashboard */}
        {activeTab === 'dashboard' && (
          <div className="flex flex-col gap-8 text-left">
            
            {/* KPIs Row */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              
              {/* Card 1: Student Registry */}
              <div className="apple-panel interactive-hover-amber rounded-xl p-5 flex flex-col justify-between min-h-[110px] relative overflow-hidden group border border-amber-500/10 hover:border-amber-500/30">
                <div className="absolute top-0 right-0 w-24 h-24 bg-amber-500/5 rounded-full blur-2xl group-hover:scale-125 transition-all duration-300"></div>
                <div className="flex items-center justify-between text-zinc-400 text-[10px] font-semibold tracking-wider font-mono uppercase z-10">
                  <span className="font-display">Student Registry</span>
                  <Users strokeWidth={1.5} className="h-4 w-4 text-amber-500 group-hover:scale-110 transition-all duration-300" />
                </div>
                <div className="mt-4 z-10">
                  <span className="text-3xl font-semibold tracking-tight text-gradient-copper font-display">
                    {analytics.kpis.total_students}
                  </span>
                  <span className="text-[9px] text-zinc-500 block mt-1 font-mono uppercase tracking-wider">
                    COORD::0x7F_REG // 37.42°N
                  </span>
                </div>
              </div>

              {/* Card 2: Today's Attendance */}
              <div className="apple-panel interactive-hover-amber rounded-xl p-5 flex flex-col justify-between min-h-[110px] relative overflow-hidden group border border-amber-500/10 hover:border-amber-500/30">
                <div className="absolute top-0 right-0 w-24 h-24 bg-amber-500/5 rounded-full blur-2xl group-hover:scale-125 transition-all duration-300"></div>
                <div className="flex items-center justify-between text-zinc-400 text-[10px] font-semibold tracking-wider font-mono uppercase z-10">
                  <span className="font-display">Today's Attendance</span>
                  <UserCheck strokeWidth={1.5} className="h-4 w-4 text-amber-500 group-hover:scale-110 transition-all duration-300" />
                </div>
                <div className="mt-4 z-10">
                  <span className="text-3xl font-semibold tracking-tight text-gradient-copper font-display">
                    {analytics.kpis.today_rate}%
                  </span>
                  <span className="text-[9px] text-zinc-500 block mt-1 font-mono uppercase tracking-wider">
                    SYS::BIOM_MATCH // 122.16°W
                  </span>
                </div>
              </div>

              {/* Card 3: Weekly Average */}
              <div className="apple-panel interactive-hover-amber rounded-xl p-5 flex flex-col justify-between min-h-[110px] relative overflow-hidden group border border-amber-500/10 hover:border-amber-500/30">
                <div className="absolute top-0 right-0 w-24 h-24 bg-amber-500/5 rounded-full blur-2xl group-hover:scale-125 transition-all duration-300"></div>
                <div className="flex items-center justify-between text-zinc-400 text-[10px] font-semibold tracking-wider font-mono uppercase z-10">
                  <span className="font-display">Weekly Average</span>
                  <TrendingUp strokeWidth={1.5} className="h-4 w-4 text-amber-500 group-hover:scale-110 transition-all duration-300" />
                </div>
                <div className="mt-4 z-10">
                  <span className="text-3xl font-semibold tracking-tight text-gradient-copper font-display">
                    {analytics.kpis.weekly_average_rate}%
                  </span>
                  <span className="text-[9px] text-zinc-500 block mt-1 font-mono uppercase tracking-wider">
                    INDEX::DAILY_LOG // ELEV::32M
                  </span>
                </div>
              </div>

              {/* Card 4: Status Panel */}
              {(() => {
                const isTraining = status.is_training;
                const isCapturing = status.capture_mode;
                
                let statusLabel = "Scanner Idle";
                if (isTraining) {
                  statusLabel = "AI Retraining";
                } else if (isCapturing) {
                  statusLabel = "Capturing Face";
                }
                
                return (
                  <div className="apple-panel interactive-hover-amber rounded-xl p-5 flex flex-col justify-between min-h-[110px] relative overflow-hidden group border border-amber-500/10 hover:border-amber-500/30">
                    <div className="absolute top-0 right-0 w-24 h-24 bg-amber-500/5 rounded-full blur-2xl group-hover:scale-125 transition-all duration-300"></div>
                    <div className="flex items-center justify-between text-zinc-400 text-[10px] font-semibold tracking-wider font-mono uppercase z-10">
                      <span>Status Panel</span>
                      <Activity strokeWidth={1.5} className="h-4 w-4 text-amber-500 group-hover:scale-110 transition-all duration-300" />
                    </div>
                    <div className="mt-4 z-10">
                      <span className="text-lg font-semibold tracking-tight text-gradient-copper block truncate">
                        {statusLabel}
                      </span>
                      <span className="text-[9px] text-zinc-500 block mt-1 font-mono uppercase tracking-wider">
                        STATUS::ACTIVE // SCAN_SWEEP
                      </span>
                    </div>
                  </div>
                );
              })()}

            </div>

            {/* Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              
              {/* Weekly Attendance Trend Curve inside vector scope frame (Signature Aesthetic Risk) */}
              <div className="apple-panel titanium-console rounded-2xl p-6 flex flex-col relative overflow-hidden">
                <div className="radar-crosshair pointer-events-none"></div>
                <div className="mb-4 z-10">
                  <span className="text-xs font-semibold uppercase tracking-wider text-amber-500/80 font-mono">Attendance Trend</span>
                  <h3 className="text-base font-semibold text-zinc-200 mt-1 font-display">Weekly Presence Rates</h3>
                </div>
                <div className="h-[250px] relative w-full z-10">
                  {analytics.charts.weekly.data.length > 0 ? (
                    <Line data={lineChartData} options={lineChartOptions} />
                  ) : (
                    <div className="flex items-center justify-center h-full text-xs text-zinc-600 font-mono">
                      Calculating analytics datasets...
                    </div>
                  )}
                </div>
              </div>

              {/* Hourly Distribution Bar Chart */}
              <div className="apple-panel rounded-2xl p-6 flex flex-col">
                <div className="mb-4">
                  <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400 font-mono">Peak hours</span>
                  <h3 className="text-base font-semibold text-zinc-200 mt-1">Hourly Check-in Distribution</h3>
                </div>
                <div className="h-[250px] relative w-full">
                  {analytics.charts.hourly.data.some(c => c > 0) ? (
                    <Bar data={barChartData} options={barChartOptions} />
                  ) : (
                    <div className="flex items-center justify-center h-full text-xs text-zinc-600 font-mono">
                      No check-in distribution timestamps recorded yet.
                    </div>
                  )}
                </div>
              </div>

            </div>

          </div>
        )}

        {/* Tab 2: Live Scanner & Take Attendance */}
        {activeTab === 'scanner' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            
            {/* Left Column: Live Feed & Retraining */}
            <section className="lg:col-span-7 flex flex-col gap-8 w-full">
              
              {/* Webcam Stream - Titanium Radar Console (Signature Aesthetic Risk) */}
              <div className="apple-panel titanium-console rounded-2xl p-5 flex flex-col relative overflow-hidden text-left group">
                
                {/* Radar Scope Sweeper background effect */}
                <div className="radar-scope-sweep animate-radar-sweep pointer-events-none"></div>
                <div className="radar-crosshair pointer-events-none"></div>
                
                <div className="flex items-center justify-between mb-3.5 z-10">
                  <div className="flex items-center gap-2">
                    <Camera strokeWidth={1.5} className="h-4.5 w-4.5 text-amber-500/80" />
                    <span className="text-xs font-medium text-zinc-400 font-display">Scanner View</span>
                  </div>
                  
                  {status.is_training ? (
                    <span className="bg-[#FF9F0A]/10 text-[#FF9F0A] border border-[#FF9F0A]/20 text-[9px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider font-mono">
                      TRAINING AI
                    </span>
                  ) : status.capture_mode ? (
                    <span className="bg-[#30D158]/10 text-[#30D158] border border-[#30D158]/20 text-[9px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider font-mono animate-pulse-dot">
                      CAPTURING SAMPLES
                    </span>
                  ) : (
                    <div className="flex items-center gap-1.5 text-zinc-500 text-[10px] font-semibold tracking-wider font-mono">
                      <span className="h-1.5 w-1.5 rounded-full bg-[#30D158] animate-pulse-dot"></span>
                      SCANNING ACTIVE
                    </div>
                  )}
                </div>

                <div className="relative w-full aspect-video rounded-xl overflow-hidden bg-black flex items-center justify-center border border-amber-500/10 shadow-2xl shadow-black/90 z-10">
                  {!status.is_training && (
                    <div className="laser-scan-line animate-laser-sweep z-10 pointer-events-none"></div>
                  )}

                  <img 
                    src={`${API_BASE_URL}/api/video_feed`} 
                    alt="Live Scanner Stream" 
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      e.target.style.display = 'none';
                    }}
                  />
                  
                  {status.capture_mode && (
                    <div className="absolute inset-0 bg-black/60 flex flex-col justify-end p-5 z-20">
                      <div className="w-full bg-[#1c1c1e] rounded-xl p-4 border border-zinc-800">
                        <div className="flex items-center justify-between text-xs font-medium mb-2">
                          <span className="text-[#30D158] flex items-center gap-1.5 font-mono text-[10px] uppercase font-semibold">
                            Capturing face samples
                          </span>
                          <span className="text-zinc-400 font-mono text-xs">
                            {status.captured_count} / {status.target_capture_count}
                          </span>
                        </div>
                        <div className="w-full h-1.5 bg-black rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-zinc-400 transition-all duration-300"
                            style={{ width: `${(status.captured_count / status.target_capture_count) * 100}%` }}
                          ></div>
                        </div>
                      </div>
                    </div>
                  )}

                  {status.is_training && (
                    <div className="absolute inset-0 bg-black/90 flex flex-col items-center justify-center p-6 z-20 text-center">
                      <div className="w-10 h-10 rounded-full border border-zinc-800 border-t-zinc-400 animate-spin mb-3"></div>
                      <h3 className="text-sm font-semibold text-zinc-200 mb-1">Fitting Model Classifier</h3>
                      <p className="text-xs text-zinc-500 max-w-xs mb-4">
                        Re-building embeddings. Camera view paused.
                      </p>
                      <div className="px-3 py-1 bg-zinc-900 border border-zinc-800 rounded-lg text-[11px] font-mono text-zinc-400">
                        {status.training_progress}
                      </div>
                    </div>
                  )}
                </div>

                {!status.camera_active && !status.is_training && (
                  <div className="mt-3 flex items-center gap-2 text-left bg-zinc-900/60 border border-zinc-800 px-4 py-2.5 rounded-xl text-xs text-zinc-400">
                    <AlertCircle strokeWidth={1.5} className="h-4.5 w-4.5 text-zinc-500 shrink-0" />
                    <div>
                      <span className="font-medium text-zinc-300 block">Simulation Mode</span>
                      Webcam offline. The backend is running in simulation mode with simulated student triggers.
                    </div>
                  </div>
                )}

              </div>


            </section>

            {/* Right Column: Focus Widget & Save Face */}
            <section className="lg:col-span-5 flex flex-col gap-8 w-full text-left">

              {/* Active Scanner Focus Widget */}
              <div className="apple-panel rounded-2xl p-6 flex flex-col">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <Activity strokeWidth={1.5} className="h-4.5 w-4.5 text-[#30D158] animate-pulse" />
                    <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400 font-mono">Scanner Focus</span>
                  </div>
                  {lastDetected && lastDetected.status === 'Active' && (
                    <span className="bg-[#30D158]/10 text-[#30D158] border border-[#30D158]/20 text-[9px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider font-mono">
                      Active
                    </span>
                  )}
                </div>
                
                {lastDetected ? (
                  <div className="flex items-center justify-between bg-black border border-zinc-900 rounded-xl p-4">
                    <div className="flex items-center gap-3">
                      <div className="h-10 w-10 rounded-full bg-[#1c1c1e] border border-zinc-800 text-zinc-300 flex items-center justify-center font-bold text-sm uppercase font-mono">
                        {lastDetected.name.charAt(0)}
                      </div>
                      <div>
                        <span className="font-semibold text-sm block text-white">
                          {lastDetected.name}
                        </span>
                        <span className="text-[10px] text-zinc-500 font-mono">
                          Last seen: {lastDetected.last_seen.split(' ')[1]}
                        </span>
                      </div>
                    </div>
                    <div className="text-right">
                      <span className="text-xs font-mono font-bold text-zinc-300 block">
                        {lastDetected.duration_str}
                      </span>
                      <span className="text-[9px] uppercase font-semibold text-zinc-600 tracking-wider font-mono">
                        Session time
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-6 border border-dashed border-zinc-800 rounded-xl text-xs text-zinc-600 font-mono">
                    No active face tracks in current session.
                  </div>
                )}
              </div>

              {/* Save Student Face Form */}
              <div className="apple-panel rounded-2xl p-6 flex flex-col">
                <div className="flex items-center gap-2 mb-4">
                  <UserPlus strokeWidth={1.5} className="h-4.5 w-4.5 text-zinc-400" />
                  <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400 font-mono">Save Student Face</span>
                </div>
                
                <form onSubmit={handleRegister} className="flex flex-col gap-4">
                  <div>
                    <label className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider block mb-1.5 font-mono">
                      Full Name
                    </label>
                    <input 
                      type="text" 
                      disabled={status.capture_mode || status.is_training || isRegistering}
                      placeholder="e.g. Satyam Rana" 
                      value={registerName}
                      onChange={(e) => setRegisterName(e.target.value)}
                      className="w-full apple-glass-input disabled:opacity-30 disabled:cursor-not-allowed rounded-xl px-4 py-2.5 text-sm placeholder:text-zinc-600 text-white"
                    />
                  </div>

                  <button 
                    type="submit"
                    disabled={status.capture_mode || status.is_training || isRegistering || !registerName.trim()}
                    className="w-full bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-600 hover:from-indigo-600 hover:via-purple-600 hover:to-pink-700 disabled:from-zinc-800 disabled:to-zinc-900 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold text-xs uppercase tracking-wider rounded-xl py-3 px-4 shadow-lg shadow-indigo-500/10 hover:shadow-indigo-500/25 hover:-translate-y-[1px] transition-all active:translate-y-0 active:scale-[0.98] cursor-pointer flex items-center justify-center gap-2"
                  >
                    {isRegistering ? (
                      <>
                        <RefreshCw strokeWidth={1.5} className="h-4 w-4 animate-spin" />
                        Connecting...
                      </>
                    ) : (
                      <>
                        Save Face & Train AI
                      </>
                    )}
                  </button>
                </form>

                {registerError && (
                  <div className="mt-3 flex items-start gap-2 bg-[#FF453A]/10 border border-[#FF453A]/20 text-[#FF453A] p-3 rounded-xl text-xs">
                    <AlertCircle strokeWidth={1.5} className="h-4 w-4 text-[#FF453A] shrink-0 mt-0.5" />
                    <span>{registerError}</span>
                  </div>
                )}

                {registerSuccess && (
                  <div className="mt-3 flex items-start gap-2 bg-[#30D158]/10 border border-[#30D158]/20 text-[#30D158] p-3 rounded-xl text-xs">
                    <CheckCircle strokeWidth={1.5} className="h-4 w-4 text-[#30D158] shrink-0 mt-0.5" />
                    <span>{registerSuccess}</span>
                  </div>
                )}
              </div>

            </section>

          </div>
        )}

        {/* Tab 3: Attendance Sheets */}
        {activeTab === 'sheets' && (
          <div className="apple-panel rounded-2xl p-6 text-left flex flex-col">
            
            {/* Sheet Control Header */}
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-zinc-900 pb-6 mb-6">
              
              <div className="flex items-center gap-3">
                <div className="relative">
                  <Calendar strokeWidth={1.5} className="absolute left-3 top-2.5 h-4.5 w-4.5 text-zinc-500 pointer-events-none" />
                  
                  {/* Select Date dropdown */}
                  <select 
                    value={selectedDate} 
                    onChange={(e) => setSelectedDate(e.target.value)}
                    className="apple-glass-input rounded-xl pl-9 pr-8 py-2 text-xs font-mono font-semibold text-white appearance-none cursor-pointer"
                  >
                    {availableDates.map(date => (
                      <option key={date} value={date}>
                        {date === getTodayString() ? `${date} (Today)` : date}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Calendar Input to create a custom sheet date */}
                <input 
                  type="date"
                  max={getTodayString()}
                  value={selectedDate}
                  onChange={(e) => {
                    const val = e.target.value;
                    if (val) {
                      setSelectedDate(val);
                      if (!availableDates.includes(val)) {
                        setAvailableDates(prev => sortedDates([val, ...prev]));
                      }
                    }
                  }}
                  className="apple-glass-input rounded-xl px-3 py-2 text-xs font-mono font-semibold text-white cursor-pointer"
                />
              </div>

              {/* Text Search + Reset for today's logs */}
              <div className="flex items-center gap-3 flex-1 md:justify-end">
                <input 
                  type="text" 
                  placeholder="Search students..." 
                  value={sheetSearch}
                  onChange={(e) => setSheetSearch(e.target.value)}
                  className="apple-glass-input rounded-xl px-3.5 py-2 text-xs text-white placeholder:text-zinc-600 w-full max-w-[200px]"
                />

                {selectedDate === getTodayString() && sheetRecords.some(r => r.status !== 'Absent') && (
                  <button 
                    onClick={handleResetSession}
                    className="text-[10px] uppercase font-bold text-zinc-400 hover:text-white border border-zinc-800 hover:border-zinc-700 bg-zinc-900/60 px-3 py-2 rounded-xl transition-all flex items-center gap-1.5 font-mono"
                  >
                    <Trash2 strokeWidth={1.5} className="h-3.5 w-3.5 text-zinc-500" />
                    Reset Sheet
                  </button>
                )}
              </div>

            </div>

            {/* Attendance Sheet Table */}
            <div className="overflow-x-auto">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="border-b border-zinc-900 text-zinc-500 text-[10px] font-semibold tracking-wider font-mono uppercase text-left">
                    <th className="pb-3 pl-4">Student</th>
                    <th className="pb-3">Status</th>
                    <th className="pb-3">Check-In</th>
                    <th className="pb-3">Duration</th>
                    <th className="pb-3 pr-4 text-right">Attendance Override</th>
                  </tr>
                </thead>
                
                <tbody className="divide-y divide-zinc-900/60 text-xs">
                  {filteredSheet.length > 0 ? (
                    filteredSheet.map((record) => {
                      const isToggling = !!togglingStudents[record.id];
                      
                      return (
                        <tr key={record.id} className="hover:bg-white/[0.01] transition-all">
                          {/* Student Details */}
                          <td className="py-3.5 pl-4">
                            <div className="flex items-center gap-3">
                              <div className="h-7 w-7 rounded-full bg-zinc-900 border border-zinc-800 text-zinc-400 flex items-center justify-center font-bold text-[10px] uppercase font-mono">
                                {record.name.charAt(0)}
                              </div>
                              <div>
                                <span className="font-semibold text-zinc-200 block">
                                  {record.name}
                                </span>
                                <span className="text-[9px] font-mono text-zinc-600 block mt-0.5">
                                  {record.id}
                                </span>
                              </div>
                            </div>
                          </td>

                          {/* Status Badge */}
                          <td className="py-3.5">
                            <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.75 rounded-full text-[9px] font-bold font-mono uppercase tracking-wider ${
                              record.status === 'Active' || record.status === 'Present'
                                ? 'status-pill-present animate-radial-pulse'
                                : record.status === 'Away'
                                ? 'status-pill-away'
                                : 'status-pill-absent'
                            }`}>
                              <span className={`h-1.5 w-1.5 rounded-full ${
                                record.status === 'Active' || record.status === 'Present'
                                  ? 'bg-emerald-400'
                                  : record.status === 'Away'
                                  ? 'bg-amber-400'
                                  : 'bg-red-400'
                              }`}></span>
                              {record.status}
                            </span>
                          </td>

                          {/* Check-In Timestamp */}
                          <td className="py-3.5 font-mono text-zinc-400">
                            {record.check_in.includes(":") ? record.check_in.split(" ")[1] : record.check_in}
                          </td>

                          {/* Cumulative Duration */}
                          <td className="py-3.5 font-mono text-zinc-300">
                            {record.duration_str}
                          </td>

                          {/* Toggle overrides checkbox */}
                          <td className="py-3.5 pr-4 text-right">
                            <button
                              disabled={isToggling}
                              onClick={() => toggleAttendanceStatus(record.id, record.status)}
                              className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-[10px] font-semibold uppercase tracking-wider font-mono transition-all duration-300 border ${
                                record.status === 'Absent'
                                  ? 'bg-transparent border-zinc-800/80 hover:border-zinc-600 hover:text-zinc-200 text-zinc-500 hover:bg-white/[0.02]'
                                  : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20 hover:border-emerald-500/50 hover:shadow-md hover:shadow-emerald-500/5'
                              } disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer active:scale-95`}
                            >
                              {isToggling ? (
                                <RefreshCw className="h-3 w-3 animate-spin text-zinc-500" />
                              ) : record.status === 'Absent' ? (
                                'Mark Present'
                              ) : (
                                'Mark Absent'
                              )}
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan="5" className="py-12 text-center text-zinc-600 font-mono select-none">
                        No registered students found. Add students in the Live Scanner tab.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

          </div>
        )}

      </main>

      {/* Footer */}
      <footer className="w-full max-w-6xl mx-auto border-t border-zinc-900 pt-6 flex flex-col md:flex-row items-center justify-between text-zinc-600 text-[10px] font-medium tracking-widest uppercase font-mono">
        <div>Aetherscan Sheet Terminal v3.0</div>
        <div className="flex items-center gap-4 mt-2 md:mt-0">
          <span>MacOS Localhost</span>
          <span>CV backend: OpenCV + TensorFlow</span>
        </div>
      </footer>

    </div>
  );
}

// Simple date sort helper
const sortedDates = (arr) => {
  return [...new Set(arr)].sort((a, b) => new Date(b) - new Date(a));
};

export default App;
