# ORION — The AI That Proves Itself Wrong

> Most system monitors tell you **what** is happening. ORION tells you **why** — and then proves it.

---

## The Problem

When your laptop is slow, you open Task Manager. You see:

    CPU       74%
    Chrome    43%
    python    17%

That tells you **what** is consuming resources. It does not tell you:

- **Why** your machine is slow
- **Whether** Chrome is actually the cause
- **What** happens if you act on that guess

Every existing tool stops at "here are the numbers." None of them
investigate, test a hypothesis, or verify the outcome.

---

## What ORION Does

ORION treats a slow computer like a scientific problem.

    User asks: "My laptop is extremely slow. Find out why."
                            |
                            v
                        OBSERVE
                Collect real system telemetry
                            |
                            v
                      INVESTIGATE
            Rank anomalies. Profile processes over time.
                            |
                            v
                     FUSE EVIDENCE
           Combine independent signals into a score.
                            |
                            v
                       REASON
              Explain what's happening in plain language.
                            |
                            v
                  ASK FOR PERMISSION
            "Chrome is using 43% CPU. Suspend it and measure?"
                            |
                            v
                         ACT
                Temporarily suspend the process.
                            |
                            v
                      MEASURE
                  Read the system again.
                            |
                            v
                        VERIFY
           Report whether the action actually helped.

Every number in that chain is **live telemetry**. Nothing is mocked.

---

## The Killer Feature: Falsifiability

Most AI systems commit to an answer. ORION **tests** its answer and
reports honestly — including when the answer was wrong.

### When ORION is right

    INTERVENTION COMPLETE

    CPU BEFORE     47.8%
    CPU DURING     26.4%
    IMPROVEMENT    21.4 pts

    [OK] PROCESS RESUMED

    SUPPORTED_BY_INTERVENTION

### When ORION is wrong

    INTERVENTION COMPLETE

    CPU BEFORE     62.0%
    CPU DURING     61.4%
    IMPROVEMENT     0.6 pts

    [OK] PROCESS RESUMED

    NO_MEASURED_IMPROVEMENT

    The intervention did not produce a meaningful system-level
    improvement. The candidate is therefore weakened as the
    primary contributor.

**That second output is the point.** Most AI tools cannot say "I was
wrong." ORION can, does, and reports the evidence for it.

---

## The Safety Model

ORION runs on your real machine. It takes that seriously.

### 1. Explicit user permission
No action runs without you clicking Approve. The voice layer
cannot bypass this — a spoken command is not authorization.

### 2. Protected process policy
The backend refuses to touch:

    System, smss.exe, csrss.exe, services.exe, lsass.exe,
    winlogon.exe, svchost.exe, dwm.exe, explorer.exe, conhost.exe,
    memcompression

Any request matching this list returns 403 Forbidden, no matter
who asks.

### 3. Process identity verification
Before acting, ORION re-reads the PID and confirms the name still
matches the investigation. This prevents PID recycling attacks.

### 4. Always-resume guarantee
The suspend function wraps resume in a try/finally. Even if
measurement crashes, the process is resumed.

### 5. No process is ever terminated
ORION only calls process.suspend(). Never terminate(). Never
kill(). The process keeps its memory, files, and state.

---

## How ORION Works

### Investigation Pipeline

Every investigation runs through 7 stages:

| Stage | What it does |
|---|---|
| Understanding | Classify intent (INVESTIGATE vs GENERAL) |
| Telemetry | Collect live CPU, RAM, disk, GPU snapshots |
| Anomaly Detection | Score individual processes against baselines |
| Root Cause Ranking | Order candidates by weighted evidence |
| Investigation | Autonomously pick the next tool based on gaps |
| Evidence Fusion | Combine independent signals into one score |
| Diagnosis | Produce structured explanation + next step |

### Evidence Fusion

The fusion engine combines:

- Anomaly score — how far a process deviates from normal
- Temporal score — is the activity persistent or transient?
- Deep investigation — command line, threads, open files
- Per-core distribution — is CPU load concentrated?

Each signal has a weight. The final score is 0-100.

Classifications:

- STRONG_CANDIDATE (score >= 50)
- POSSIBLE_CANDIDATE (score 10-49)
- WEAKENED (score 1-9)
- NOT_CONFIRMED (score 0)

### Remediation Model

The remediation layer has 4 checks:

1. User approval — explicit approved: true in the request
2. Investigation membership — the PID was actually investigated
3. Process identity — the PID still maps to the same name
4. Protected policy — the name is not on the protected list

If all four pass, ORION:

1. Measures system CPU (before)
2. Suspends the process for N seconds
3. Measures system CPU (during)
4. Resumes the process
5. Computes improvement
6. Returns verification status

### Verification Statuses

- SUPPORTED_BY_INTERVENTION — CPU dropped > 5 percentage points
- WEAK_INTERVENTION_SIGNAL — CPU dropped 0-5 points
- NO_MEASURED_IMPROVEMENT — CPU did not drop

---

## Architecture

    +------------------------------------------------------+
    |                    FRONTEND                          |
    |  React + Vite                                        |
    |  - Investigation timeline                            |
    |  - Evidence fusion display                           |
    |  - Action panel (protected / actionable)             |
    |  - Verification result                               |
    |  - Voice input (AssemblyAI token-based)              |
    +----------------------+-------------------------------+
                           |  HTTP / WebSocket
    +----------------------v-------------------------------+
    |                    BACKEND                           |
    |  FastAPI + Python                                    |
    |  - Intent classifier                                 |
    |  - Investigation planner                             |
    |  - Evidence fusion engine                            |
    |  - Temporal process profiler                         |
    |  - Remediation policy + execution                    |
    |  - Voice token service                               |
    +----------------------+-------------------------------+
                           |
            +--------------+--------------+
            |              |              |
            v              v              v
        psutil       AssemblyAI         Groq
      (live telemetry) (realtime voice) (structured
                                          reasoning)
                           |
                           v
                        SQLite
                  (investigation history)

---

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, custom CSS |
| Backend | Python 3.13, FastAPI, Uvicorn |
| Telemetry | psutil |
| Voice | AssemblyAI v3 streaming (v1.1.0 SDK) |
| Reasoning | Groq |
| Persistence | SQLite |
| Process control | psutil (suspend / resume only) |

---

## Installation

### 1. Clone or copy the project

Place at:

    C:\Users\HP\Desktop\ORION-Field-Intelligence

### 2. Create and activate Python environment

    cd C:\Users\HP\Desktop\ORION-Field-Intelligence
    .\venv\Scripts\Activate.ps1

### 3. Install backend dependencies

    cd backend
    pip install -r requirements.txt

### 4. Install frontend dependencies

    cd ..\frontend
    npm install

---

## Environment Configuration

Create backend/.env:

    ASSEMBLYAI_API_KEY=your_assemblyai_api_key
    GROQ_API_KEY=your_groq_api_key
    GROQ_MODEL=openai/gpt-oss-120b

Both keys stay server-side. The browser only ever receives a
short-lived AssemblyAI streaming token.

Never commit .env to Git. It is already in .gitignore.

---

## Running ORION

Three terminals.

### Terminal 1 — CPU load (optional, for demos)

    cd C:\Users\HP\Desktop\ORION-Field-Intelligence
    python scripts\demo_cpu_load.py

Creates a real, sustained CPU load so ORION has something to find.

### Terminal 2 — Backend

    cd C:\Users\HP\Desktop\ORION-Field-Intelligence
    .\venv\Scripts\Activate.ps1
    cd backend
    uvicorn api.main:app --reload

Available at http://127.0.0.1:8000. Health check:

    http://127.0.0.1:8000/health

### Terminal 3 — Frontend

    cd C:\Users\HP\Desktop\ORION-Field-Intelligence\frontend
    npm run dev

Open the Vite URL (usually http://localhost:5175/).

---

## Using ORION

Open the frontend. Type:

    My laptop is extremely slow. Find out why.

Press INVESTIGATE.

The dashboard displays:

- Investigation timeline
- System telemetry (CPU, RAM, Disk, GPU)
- Evidence fusion (strongest candidate + score)
- Supporting evidence list
- Root cause ranking
- Structured diagnosis
- Action panel (protected / actionable / not actionable)
- Verification result
- Investigation history

---

## Example Investigation

User:

    My laptop is extremely slow. Find out why.

ORION observes:

    CPU: 74.6%
    RAM: 51.1%

ORION identifies:

    python3.13.exe
    PID 17412
    CPU 90.6%
    Temporal: PERSISTENT
    Evidence Score: 100
    Classification: STRONG_CANDIDATE

ORION proposes:

    Controlled intervention

    python3.13.exe   PID 17412

    [ TEMPORARILY SUSPEND & VERIFY ]

If the user approves:

    Suspend process
          |
          v
    Measure system CPU
          |
          v
    Resume process
          |
          v
    Verify

Result:

    CPU BEFORE     47.8%
    CPU DURING     26.4%
    IMPROVEMENT    21.4 pts

    [OK] PROCESS RESUMED

    SUPPORTED_BY_INTERVENTION

---

## API Endpoints

### Root

    GET /

Basic API information.

### Health

    GET /health

Backend health check.

### Ask ORION

    GET /ask?message=<question>

Example:

    /ask?message=My laptop is extremely slow

Runs a full investigation.

### Investigation History

    GET /investigations?limit=10

Returns stored investigations.

### Investigation Details

    GET /investigations/{investigation_id}

Returns one specific investigation.

### Remediation — Suspend and Verify

    POST /investigations/{investigation_id}/actions/suspend

Requires explicit user approval.

Body:

    {
      "approved": true,
      "pid": 17412,
      "process_name": "python3.13.exe",
      "suspend_seconds": 4
    }

The backend validates approval, investigation membership, process
identity, and the protected-process policy. All four must pass.

### Voice Health

    GET /voice/health

Reports whether the AssemblyAI key and microphone are available.

### Voice Token

    GET /voice/token

Returns a short-lived AssemblyAI streaming token. The permanent key
never leaves the server.

---

## Investigation History

ORION stores investigation results locally using SQLite:

    backend/database/orion_history.db

The store supports:

    create_investigation_id()
    save_investigation()
    get_investigation()
    list_investigations()

Each entry contains:

- Investigation ID
- Timestamp
- Question
- Intent
- Status
- Structured result
- Evidence
- Diagnosis

This lets ORION move beyond one-off conversations. Every
investigation is retrievable later.

---

## Project Structure

    ORION-Field-Intelligence/
    |
    +-- backend/
    |   +-- agents/
    |   |   +-- orion_agent.py
    |   +-- api/
    |   |   +-- main.py
    |   |   +-- remediation.py
    |   |   +-- voice.py
    |   +-- database/
    |   |   +-- investigation_store.py
    |   |   +-- orion_history.db
    |   +-- tools/
    |   |   +-- system_info.py
    |   |   +-- process_monitor.py
    |   |   +-- performance_monitor.py
    |   |   +-- evidence_fusion.py
    |   |   +-- investigation_planner.py
    |   |   +-- gpu_monitor.py
    |   |   +-- memory_pressure.py
    |   |   +-- storage_latency.py
    |   |   +-- remediation/
    |   |       +-- action_policy.py
    |   |       +-- process_actions.py
    |   +-- voice/
    |   |   +-- realtime_transcriber.py
    |   |   +-- voice_session.py
    |   |   +-- samples/
    |   +-- .env
    |   +-- config.py
    |   +-- requirements.txt
    |
    +-- frontend/
    |   +-- public/
    |   |   +-- audio/
    |   |       +-- pcm-processor.js
    |   +-- src/
    |       +-- App.jsx
    |       +-- App.css
    |       +-- VoiceInput.jsx
    |       +-- ActionPanel.jsx
    |       +-- VerificationResult.jsx
    |       +-- InvestigationHistory.jsx
    |       +-- InvestigationTimeline.jsx
    |
    +-- scripts/
    |   +-- demo_cpu_load.py
    |   +-- demo_memory_load.py
    |   +-- demo_transient_spike.py
    |
    +-- docs/
    |   +-- architecture.md
    |
    +-- venv/
    +-- .gitignore
    +-- README.md

---

## What Makes ORION Different

| Other tools | ORION |
|---|---|
| Show metrics | Investigates causes |
| Commit to a guess | Tests the guess |
| Kill the process | Suspends and resumes |
| No verification | Measures the result |
| No safety model | Refuses protected processes |
| Never wrong | Reports when it is wrong |

---

## Voice Interface

ORION accepts browser-based voice input.

    Microphone
        |
        v
    Browser Audio Capture (Web Audio API)
        |
        v
    PCM16 mono 16 kHz
        |
        v
    AssemblyAI v3 streaming (WebSocket)
        |
        v
    Live transcript
        |
        v
    ORION investigation

The permanent AssemblyAI API key is never sent to the browser.
Instead, the browser requests a short-lived token from
GET /voice/token.

The frontend displays:

- Voice state (IDLE / LISTENING / TRANSCRIPT READY)
- Start and stop listening button
- Live transcript

---

## Design Principles

1. Evidence before conclusions. Measure first. Conclude second.
2. Candidates are not causes. A candidate must be investigated.
3. Multiple evidence sources. Never rely on one metric.
4. Uncertainty is valid. NO_CONFIRMED_CAUSE is a real answer.
5. Human control. Disruptive actions require user approval.
6. Verify actions. Success is not "the action ran" — it is "the
   system measurably improved."
7. Structured intelligence. The engine produces structured data
   the UI can consume directly, not prose that must be re-parsed.

---

## Future Development

- Hardware intelligence — CPU/GPU temperature, fan speed, battery, thermal throttling
- Storage intelligence — read/write latency, queue depth, SMART data
- Network intelligence — latency, packet loss, DNS, per-process network usage
- Long-term monitoring — baseline learning, anomaly alerts over time
- Fleet intelligence — investigate multiple machines from one dashboard

---

## Limitations

ORION is a prototype. It has real limitations:

- Windows-focused. The current telemetry layer targets Windows.
- No hardware sensors by default. Temperature and fan data may be
  unavailable on some machines.
- No GPU on every system. Discrete GPU telemetry depends on driver
  support.
- Causality is statistical, not absolute. System monitoring cannot
  always prove a single cause.
- LLM reasoning quality depends on evidence quality. If the tool
  layer measures poorly, the reasoning layer reasons poorly.
- Elevated permissions may be required for some telemetry or actions.

---

## Manual Test Plan

1. Backend health — GET /health returns {"status":"healthy"}
2. General question — non-investigation input is handled correctly
3. Investigation — "My laptop is extremely slow" runs the full pipeline
4. History — the investigation appears in the history panel
5. Voice — click mic, speak, transcript, investigation
6. Remediation — safe process, approve, suspend, measure, resume, verify
7. Protected process — dwm.exe refused with PROTECTED PROCESS
8. Weak evidence — low-score candidate refused with NOT ACTIONABLE

---

## Philosophy

> Do not just answer the computer. Investigate it.

A chatbot can say "Your CPU is high."
A monitoring tool can say "Python is using 90% CPU."

ORION goes further:

    What is happening?
          |
          v
    What could explain it?
          |
          v
    What evidence supports each candidate?
          |
          v
    What additional investigation is needed?
          |
          v
    Does the evidence converge?
          |
          v
    Can a safe intervention test the hypothesis?
          |
          v
    Did the system actually improve?

That is the purpose of ORION — Field Intelligence.

---

## Author

Bhavesh
ORION — Field Intelligence

Built as an AI-powered system investigation and diagnostic platform.

---

## License

MIT (to be finalized before public release).

---

Built for the AssemblyAI x LabLab Hackathon.
The AI that proves itself wrong.
