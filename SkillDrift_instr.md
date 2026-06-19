

# SkillDrift

> A real-time tech skill demand tracker. Ingests live job postings, processes them with a distributed PySpark pipeline, and computes how fast each skill's demand is rising or falling — answering questions like "is Rust growing faster than Go right now?"

![Python](https://img.shields.io/badge/Python-3.11-blue)
![PySpark](https://img.shields.io/badge/PySpark-3.5-E25A1C)
![Apache Solr](https://img.shields.io/badge/Apache%20Solr-9.4-D9411E)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688)
![AWS S3](https://img.shields.io/badge/AWS-S3%20%28LocalStack%29-FF9900)

---

## 1. What This Is

Job boards and skill databases show you what's in demand **today**. They don't show you **direction** — is a skill accelerating or dying out? SkillDrift answers that by:

1. Pulling live job postings daily from a public job API
2. Storing each pull as a dated "snapshot" (so the same dataset exists across multiple days)
3. Running a **PySpark** job that, for each tracked skill, computes what % of job postings mention it on each day
4. Calculating **drift** — the change in that percentage from the earliest to the latest snapshot — and **status** (rising / declining / stable)
5. Indexing all job postings into **Apache Solr** for fast full-text search
6. Exposing both the trend data and search via a REST API + dashboard

### Why this matters
This directly mirrors how large-scale talent intelligence platforms operate — they don't just match a resume to a job description once, they continuously track how skill relevance shifts across millions of postings to keep recommendations current. SkillDrift is a small, honest version of that same problem: distributed data processing over real-world, messy job data, turned into an actionable trend signal.

---

## 2. Tech Stack — What Each Piece Is For

| Component | Technology | Why it's used here |
|---|---|---|
| **Data Source** | RemoteOK public API | Free, no API key, returns real live job postings (title, company, tags, description). Used as the raw input dataset. |
| **Snapshot Storage** | SQLite | Stores every day's job pull, tagged with the date it was fetched. This date-stamping is what makes trend analysis possible — without it, you'd only ever see "today," never "how has this changed." |
| **Distributed Processing** | PySpark (local mode) | Computes skill-mention counts and percentages across potentially huge datasets using the same `groupBy`/`agg` API used in production Spark clusters processing terabytes. Running `local[*]` means Spark parallelizes work across every CPU core on your machine — a genuine (if small-scale) distributed computation, not a simulation. |
| **Full-Text Search** | Apache Solr | Lets you search job postings by keyword instantly (e.g., "machine learning python remote"), which plain SQL `LIKE` queries handle poorly at scale. Demonstrates a real search-engine integration, which most student projects never touch. |
| **Cloud Storage (emulated)** | AWS S3 (via LocalStack) | Every time the trend engine runs, it uploads a summary JSON to S3 — a permanent, queryable artifact of "what the system concluded on this run." Mirrors how production data pipelines persist outputs to durable cloud storage. |
| **API Layer** | FastAPI | Exposes trend data and search results as clean REST endpoints for the dashboard (or any other consumer) to use. |
| **Containerization** | Docker | Runs Solr and LocalStack as disposable containers — no native installs needed. |

---

## 3. Project Structure

```
skilldrift/
├── README.md
├── requirements.txt
├── .gitignore
│
├── ingest.py                    # Fetches live job data from RemoteOK, saves dated snapshots to SQLite
├── indexer.py                   # Pushes job snapshots from SQLite into Solr for full-text search
├── trend_engine.py              # Core PySpark job — computes skill demand % and drift per skill
├── aws_uploader.py               # Uploads trend run summaries to S3 (LocalStack)
├── api.py                        # FastAPI app — trending skills, skill detail, search endpoints
├── simulate_history.py          # (Optional, for demo/testing) backfills multiple days of snapshot data
│
├── dashboard/
│   └── index.html                # Single-file frontend showing skill trend cards + search bar
│
├── data/
│   ├── jobs.db                   # SQLite: raw job snapshots (gitignored)
│   └── trends.db                 # SQLite: computed skill_trends table (gitignored)
│
└── docs/
    └── architecture.png          # (optional) pipeline diagram for the README
```

### Why this structure
- **Pipeline stages are separate files** (`ingest.py` → `indexer.py` → `trend_engine.py`) rather than one monolithic script. This mirrors how real data pipelines are built as discrete, independently-runnable stages — you can re-run just the trend computation without re-fetching data, for example.
- **Two separate SQLite files** (`jobs.db` for raw data, `trends.db` for computed output) — keeps raw ingested data cleanly separated from derived/computed results, which is good practice so you never accidentally corrupt your source data while iterating on analysis logic.
- **`aws_uploader.py` isolated** — same reasoning as AgentPulse: one file owns all AWS calls, so cloud provider logic never leaks into your data processing code.

---

## 4. Installation — Step by Step

### Step 1: Install Docker
Same as AgentPulse — install Docker Desktop if you don't have it: [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop)

### Step 2: Install Java (required for PySpark)
PySpark runs on the JVM under the hood, so you need Java installed even though you're writing Python.

```bash
# Check if you already have it
java -version

# If not installed (Ubuntu/Debian):
sudo apt update
sudo apt install -y openjdk-17-jdk

# Verify
java -version
# Should show: openjdk version "17.x.x"
```

> **⚠️ Manual step:** Java installation differs by OS (apt on Linux, brew on Mac, manual installer on Windows) and can't be reliably scripted across all environments — install it yourself based on your OS.

### Step 3: Clone and set up the project

```bash
git clone https://github.com/<your-username>/skilldrift.git
cd skilldrift

python3 -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate
```

### Step 4: Install Python dependencies

```bash
pip install -r requirements.txt --break-system-packages
```

`requirements.txt`:
```
pyspark==3.5.1
pysolr==3.9.0
pandas==2.2.2
requests==2.31.0
fastapi==0.110.0
uvicorn==0.29.0
boto3==1.34.100
```

### Step 5: Start Apache Solr — Docker

```bash
docker run -d \
  -p 8983:8983 \
  --name skilldrift-solr \
  solr:9.4 \
  solr-precreate jobs_core

# Wait ~20 seconds, then verify
curl "http://localhost:8983/solr/jobs_core/select?q=*:*"
# Should return: {"response":{"numFound":0,"docs":[]}}
```

> **What `solr-precreate jobs_core` does:** creates a Solr "core" (think of it like a database/table) named `jobs_core` with a default schema that auto-detects field types. This is fine for a portfolio project; production Solr deployments define explicit schemas.

### Step 6: Start LocalStack (AWS S3 emulator) — Docker

```bash
docker run -d \
  -p 4566:4566 \
  -e SERVICES=s3 \
  -e DEFAULT_REGION=us-east-1 \
  --name skilldrift-localstack \
  localstack/localstack

curl http://localhost:4566/_localstack/health
# Should show "s3": "available"
```

### Step 7: Configure fake AWS credentials

```bash
aws configure
# AWS Access Key ID: test
# AWS Secret Access Key: test
# Default region: us-east-1
# Default output format: json
```

(Install `awscli`/`awscli-local` first if needed: `pip install awscli awscli-local --break-system-packages`)

### Step 8: Create the S3 bucket manually (first time only)

```bash
awslocal s3 mb s3://skilldrift-output
awslocal s3 ls
# Should show: skilldrift-output
```

> **⚠️ Manual step (first run only):** Bucket creation is idempotent in the code (`aws_uploader.py` tries to create it automatically too), but doing it manually first lets you confirm LocalStack is working before your pipeline depends on it silently succeeding.

### Step 9: Run the pipeline — in order

This is the most important part to get right — each stage depends on the previous one's output.

```bash
# Stage 1: Fetch live job data → saves to data/jobs.db
python ingest.py
# Expected output: [Ingest] Fetched 280 jobs / Saved 280 jobs for snapshot 2026-06-19

# Stage 2: Push jobs into Solr for search
python indexer.py
# Expected output: [Solr] Indexed 280 documents

# (Optional, for a richer demo) Stage 2.5: backfill 6 days of synthetic history
# Without this, drift will be 0 since you only have 1 day of real data
python simulate_history.py
python indexer.py    # re-index after backfilling

# Stage 3: Run the PySpark trend engine
python trend_engine.py
# Expected output: a per-skill drift table printed to terminal, ending with
# [Done] Computed trends for 25 skills
```

### Step 10: Start the API

```bash
uvicorn api:app --reload --port 8000
```

### Step 11: Start the dashboard

```bash
cd dashboard
python -m http.server 3000
```

Open `http://localhost:3000` in your browser.

---

## 5. Verifying Everything Works

```bash
# 1. Solr has indexed documents
curl "http://localhost:8983/solr/jobs_core/select?q=python&rows=2"
# → Should return real job postings mentioning "python"

# 2. LocalStack S3 is alive
curl http://localhost:4566/_localstack/health   # → s3: available

# 3. Trend run was uploaded to S3
awslocal s3 ls s3://skilldrift-output/runs/ --recursive
# → Should show a summary.json file with a timestamp

# 4. API returns trend data
curl "http://localhost:8000/skills/trending?direction=rising&limit=5"
# → JSON list of skills with positive drift

# 5. Specific skill detail works
curl "http://localhost:8000/skills/python"
# → Full trend curve for Python across all snapshot dates

# 6. Search works end-to-end through the API
curl "http://localhost:8000/search?q=machine+learning"
# → Real job postings matching the query
```

---

## 6. What's Manual vs Automated — Summary

| Task | Manual or Automated? | Notes |
|---|---|---|
| Install Docker | **Manual** — one-time installer | OS-specific |
| Install Java (for PySpark) | **Manual** — one-time, OS-specific | `apt`, `brew`, or Windows installer depending on platform |
| Start Solr/LocalStack containers | Automated via `docker run` | Can be wrapped in `docker-compose.yml` (below) |
| Create Solr core | Automated via `solr-precreate` flag in the `docker run` command | One-time, baked into the container start |
| Create S3 bucket | **Manual (first time)**, then auto-created by code on subsequent runs | Verify by hand once |
| Run ingest → index → trend_engine in order | **Manual sequence** — must run scripts in this exact order | Could be wrapped in a `run_pipeline.sh` script (see below) |
| Backfilling history for demo purposes | **Manual, optional** | Only needed because a fresh project has just 1 day of real data |

### Optional: docker-compose.yml to simplify Steps 5–6

```yaml
version: "3.8"
services:
  solr:
    image: solr:9.4
    ports: ["8983:8983"]
    command: solr-precreate jobs_core
  localstack:
    image: localstack/localstack
    ports: ["4566:4566"]
    environment:
      - SERVICES=s3
      - DEFAULT_REGION=us-east-1
```
Run with: `docker-compose up -d`

### Optional: run_pipeline.sh to simplify Step 9

```bash
#!/bin/bash
set -e
echo "Stage 1: Ingesting jobs..."
python ingest.py
echo "Stage 2: Indexing to Solr..."
python indexer.py
echo "Stage 3: Computing trends..."
python trend_engine.py
echo "Pipeline complete."
```
Run with: `chmod +x run_pipeline.sh && ./run_pipeline.sh`

---

## 7. API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/skills/trending?direction=rising\|declining\|all&limit=N` | Top N skills by drift in the given direction |
| `GET` | `/skills/{skill_name}` | Full trend curve and stats for one specific skill |
| `GET` | `/search?q=query` | Full-text search across all indexed job postings via Solr |

---

## 8. How Drift Is Calculated (for transparency)

For each tracked skill, on each snapshot date:
```
demand_pct = (jobs mentioning the skill that day / total jobs that day) × 100
```

Drift is simply:
```
drift = demand_pct(latest snapshot) − demand_pct(earliest snapshot)
```

A skill is classified:
- **Rising** if `drift > 0.3`
- **Declining** if `drift < -0.3`
- **Stable** otherwise

This threshold avoids flagging noise (a 0.1% fluctuation) as a meaningful trend.

---

## 9. Limitations & Future Work
- Currently single data source (RemoteOK) — could expand to multiple job boards for better signal
- Drift calculation is simple (first-vs-last snapshot) — could move to linear regression over all snapshots for a smoother trend line
- No scheduled/automated daily ingestion yet — `ingest.py` must be run manually or via a cron job
