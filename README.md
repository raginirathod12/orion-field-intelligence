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

Every existing tool stops at "here are the numbers." None of them investigate, test a hypothesis, or verify the outcome.

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

Most AI systems commit to an answer. ORION **tests** its answer and reports honestly — including when the answer was wrong.

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

**That second output is the point.** Most AI tools cannot say "I was wrong." ORION can, does, and reports the evidence for it.

---

## The Safety Model

ORION runs on your real machine. It takes that seriously.

### 1. Explicit user permission

No action runs without you clicking **Approve**. The voice layer cannot bypass this — a spoken command is not authorization.

### 2. Protected process policy

The backend refuses to touch:

    System, smss.exe, csrss.exe, services.exe, lsass.exe,
    winlogon.exe, svchost.exe, dwm.exe, explorer.exe, conhost.exe,
    memcompression

Any request matching this list returns `403 Forbidden`, no matter who asks.

### 3. Process identity verification

Before acting, ORION re-reads the PID and confirms the name still matches the investigation. This prevents PID recycling attacks.

### 4. Always-resume guarantee

The suspend function wraps resume in a `try/finally`. Even if measurement crashes, the process is resumed.

### 5. No process is ever terminated

ORION only calls `process.suspend()`. Never `terminate()`. Never `kill()`. The process keeps its memory, files, and state.

---

## How ORION Works

### Investigation Pipeline

Every investigation runs through 7 stages:

| Stage              | What it does                                  |
| ------------------ | --------------------------------------------- |
| Understanding      | Classify intent (INVESTIGATE vs GENERAL)      |
| Telemetry          | Collect live CPU, RAM, disk, GPU snapshots    |
| Anomaly Detection  | Score individual processes against baselines  |
| Root Cause Ranking | Order candidates by weighted evidence         |
| Investigation      | Autonomously pick the next tool based on gaps |
| Evidence Fusion    | Combine independent signals into one score    |
| Diagnosis          | Produce structured explanation + next step    |

### Evidence Fusion

The fusion engine combines:

- **Anomaly score** — how far a process deviates from normal
- **Temporal score** — is the activity persistent or transient?
- **Deep investigation** — command line, threads, open files
- **Per-core distribution** — is CPU load concentrated?

Each signal has a weight. The final score is 0–100.

Classifications:

- `STRONG_CANDIDATE` (score ≥ 50)
- `POSSIBLE_CANDIDATE` (score 10–49)
- `WEAKENED` (score 1–9)
- `NOT_CONFIRMED` (score 0)

### Remediation Model

The remediation layer has 4 checks:

1. **User approval** — explicit `approved: true` in the request
2. **Investigation membership** — the PID was actually investigated
3. **Process identity** — the PID still maps to the same name
4. **Protected policy** — the name is not on the protected list

If all four pass, ORION:

1. Measures system CPU (before)
2. Suspends the process for N seconds
3. Measures system CPU (during)
4. Resumes the process
5. Computes improvement
6. Returns verification status

### Verification Statuses

- `SUPPORTED_BY_INTERVENTION` — CPU dropped > 5 percentage points
- `WEAK_INTERVENTION_SIGNAL` — CPU dropped 0–5 points
- `NO_MEASURED_IMPROVEMENT` — CPU did not drop

---

## Multi-Node Monitoring

ORION monitors more than one machine. Each computer runs a lightweight collector script that reports telemetry back to a central ORION server. The dashboard shows all nodes at once.

    MONITORED NODES
    Infrastructure              3 NODES

    * DESKTOP-01
      CPU 18%   RAM 52%   DISK 45%
      ONLINE - 3s ago

    * SERVER-ALPHA
      CPU 87%   RAM 71%   DISK 62%
      ONLINE - 5s ago

    * CLOUD-VM-02
      CPU 12%   RAM 30%   DISK 22%
      OFFLINE - 4m ago

### How it works

1. Run the ORION backend on one machine (the "control server")
2. Run `scripts/collector.py` on every machine you want to monitor
3. Each collector sends CPU, RAM, disk, and uptime every 30 seconds
4. The dashboard shows all nodes with their online/offline status

### Running a collector

    python scripts/collector.py --server http://ORION_HOST:8000 --name "Server-01"

There is no limit to how many machines can report to the same ORION server.

### Multi-node API

| Endpoint           | Method | Purpose                          |
| ------------------ | ------ | -------------------------------- |
| `/nodes`           | GET    | List all registered nodes        |
| `/nodes/{node_id}` | GET    | Get a specific node              |
| `/nodes/report`    | POST   | Collector reports telemetry here |

---

## Architecture

    +------------------------------------------------------+
    |                    FRONTEND                          |
    |  React + Vite                                        |
    |  - Investigation timeline                            |
    |  - Evidence fusion display                           |
    |  - Action panel (protected / actionable)             |
    |  - Verification result                               |
    |  - Voice agent (AssemblyAI Voice Agent API)          |
    |  - Multi-node dashboard                              |
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
    |  - Voice agent token service                         |
    |  - Multi-node registry + collector API               |
    +----------------------+-------------------------------+
                           |
        +------------------+------------------+
        |                  |                  |
        v                  v                  v
     psutil          AssemblyAI            Groq

(telemetry) (Voice Agent API) (reasoning)
| | |
+------------------+------------------+
|
v
SQLite
(investigation history)

---

## Technology Stack

| Layer           | Technology                     |
| --------------- | ------------------------------ |
| Frontend        | React 18, Vite, custom CSS     |
| Backend         | Python 3.13, FastAPI, Uvicorn  |
| Telemetry       | psutil                         |
| Voice           | AssemblyAI Voice Agent API     |
| Reasoning       | Groq                           |
| Persistence     | SQLite                         |
| Process control | psutil (suspend / resume only) |
| Multi-node      | Custom collector + registry    |

---

## Installation

### 1. Clone or copy the project

Place at: `C:\Users\HP\Desktop\ORION-Field-Intelligence`

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

Create `backend/.env`:

    ASSEMBLYAI_API_KEY=your_assemblyai_api_key
    GROQ_API_KEY=your_groq_api_key
    GROQ_MODEL=openai/gpt-oss-120b

Both keys stay server-side. The browser only ever receives a short-lived AssemblyAI token.

Never commit `.env` to Git. It is already in `.gitignore`.

---

## Running ORION

Four terminals.

### Terminal 1 — CPU load (optional, for demos)

    cd C:\Users\HP\Desktop\ORION-Field-Intelligence
    python scripts\demo_cpu_load.py

Creates a real, sustained CPU load so ORION has something to find.

### Terminal 2 — Backend

    cd C:\Users\HP\Desktop\ORION-Field-Intelligence
    .\venv\Scripts\Activate.ps1
    cd backend
    uvicorn api.main:app --reload

Available at `http://127.0.0.1:8000`

### Terminal 3 — Frontend

    cd C:\Users\HP\Desktop\ORION-Field-Intelligence\frontend
    npm run dev

Open the Vite URL (usually `http://localhost:5175/`).

### Terminal 4 — Multi-node collector (optional)

    cd C:\Users\HP\Desktop\ORION-Field-Intelligence
    .\venv\Scripts\Activate.ps1
    python scripts\collector.py

Register this machine as a node.

---

## Using ORION

Open the frontend. Click **START VOICE AGENT**. Say:

    "Why is my laptop slow?"

ORION investigates, speaks the result, and offers an intervention.

Or type the request into the text box and click **INVESTIGATE**.

The dashboard displays:

- Voice conversation with barge-in
- Investigation timeline (7 stages)
- System telemetry (CPU, RAM, Disk, GPU)
- Evidence fusion (strongest candidate + score)
- ORION reasoning (primary signals + ruled out)
- Root cause ranking
- Structured diagnosis
- Action panel (protected / actionable / not actionable)
- Verification result
- Multi-node dashboard
- Automatic findings feed
- Investigation history

---

## Example Investigation

**User:**

    My laptop is extremely slow. Find out why.

**ORION observes:**

    CPU: 74.6%
    RAM: 51.1%

**ORION identifies:**

    python3.13.exe
    PID 17412
    CPU 90.6%
    Temporal: PERSISTENT
    Evidence Score: 100
    Classification: STRONG_CANDIDATE

**ORION proposes:**

    Controlled intervention

    python3.13.exe   PID 17412

    [ TEMPORARILY SUSPEND & VERIFY ]

**If the user approves:**

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

**Result:**

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

Runs a full investigation.

### Investigations

    GET /investigations?limit=10

Returns stored investigations.

    GET /investigations/{investigation_id}

Returns one specific investigation.

### Remediation

    POST /investigations/{investigation_id}/actions/suspend

Requires explicit user approval. Body:

    {
      "approved": true,
      "pid": 17412,
      "process_name": "python3.13.exe",
      "suspend_seconds": 4
    }

### Voice

    GET /voice/health

Reports whether the AssemblyAI key and microphone are available.

    GET /voice/agent-token

Returns a full agent configuration with tools and system prompt.

    POST /voice/agent-tool

Executes a tool called by the voice agent.

### Multi-node

    POST /nodes/report

Collectors report telemetry here.

    GET /nodes

List all registered nodes.

    GET /nodes/{node_id}

Get a specific node.

---

## Project Structure

    ORION-Field-Intelligence/
    |
    +-- backend/
    |   +-- agents/orion_agent.py
    |   +-- api/
    |   |   +-- main.py
    |   |   +-- remediation.py
    |   |   +-- voice.py
    |   |   +-- voice_agent.py
    |   |   +-- tts.py
    |   |   +-- findings.py
    |   |   +-- nodes.py
    |   +-- database/
    |   |   +-- investigation_store.py
    |   |   +-- findings_store.py
    |   +-- monitoring/watcher.py
    |   +-- nodes/
    |   |   +-- registry.py
    |   +-- tools/
    |   +-- voice/
    |   +-- .env
    |   +-- config.py
    |   +-- requirements.txt
    |
    +-- frontend/
    |   +-- public/audio/
    |   |   +-- pcm-processor-24k.js
    |   +-- src/
    |       +-- App.jsx
    |       +-- App.css
    |       +-- VoiceAgent.jsx
    |       +-- ActionPanel.jsx
    |       +-- VerificationResult.jsx
    |       +-- InvestigationHistory.jsx
    |       +-- InvestigationTimeline.jsx
    |       +-- FindingsPanel.jsx
    |       +-- NodesPanel.jsx
    |
    +-- scripts/
    |   +-- demo_cpu_load.py
    |   +-- demo_memory_load.py
    |   +-- demo_transient_spike.py
    |   +-- collector.py
    |
    +-- venv/
    +-- .gitignore
    +-- README.md

---

## What Makes ORION Different

| Other tools       | ORION                       |
| ----------------- | --------------------------- |
| Show metrics      | Investigates causes         |
| Commit to a guess | Tests the guess             |
| Kill the process  | Suspends and resumes        |
| No verification   | Measures the result         |
| No safety model   | Refuses protected processes |
| Never wrong       | Reports when it's wrong     |
| Single machine    | Multi-node monitoring       |

---

## Design Principles

1. **Evidence before conclusions.** Measure first. Conclude second.
2. **Candidates are not causes.** A candidate must be investigated.
3. **Multiple evidence sources.** Never rely on one metric.
4. **Uncertainty is valid.** `NO_CONFIRMED_CAUSE` is a real answer.
5. **Human control.** Disruptive actions require user approval.
6. **Verify actions.** Success is not "the action ran" — it is "the system measurably improved."
7. **Structured intelligence.** The engine produces structured data the UI can consume directly.

---

## Future Development

- **Hardware intelligence** — CPU/GPU temperature, fan speed, battery
- **Storage intelligence** — read/write latency, queue depth, SMART
- **Network intelligence** — latency, packet loss, DNS
- **Kubernetes support** — pods, deployments, services as monitorable units
- **Cloud integration** — AWS CloudWatch, Azure Monitor, GCP
- **Long-term monitoring** — baseline learning, anomaly alerts
- **Fleet intelligence** — investigate multiple data centers from one dashboard

---

## Limitations

ORION is a prototype. It has real limitations:

- **Windows-focused.** Telemetry layer targets Windows.
- **No hardware sensors by default.** Temperature and fan data may be unavailable on some machines.
- **Causality is statistical, not absolute.** Monitoring cannot always prove a single cause.
- **LLM quality depends on evidence quality.** Poor measurements lead to poor reasoning.
- **Elevated permissions may be required** for some telemetry or actions.

---

## Author

**Bhavesh**
ORION — Field Intelligence

Built as an AI-powered system investigation and diagnostic platform.

---

## License

MIT (to be finalized before public release).

---

Built for the AssemblyAI x LabLab Hackathon.
The AI that proves itself wrong.
