from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv
import os
import json
import random
import string

load_dotenv()

app = FastAPI()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# In-memory storage for job postings
jobs = {}

def generate_job_id():
    return "JOB-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

# ── Models ──────────────────────────────────────────
class JobPost(BaseModel):
    job_description: str

class ApplyRequest(BaseModel):
    job_id: str
    cv_text: str

# ── Health ──────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}

# ── Post a Job ──────────────────────────────────────
@app.post("/job")
def post_job(data: JobPost):
    job_id = generate_job_id()
    jobs[job_id] = data.job_description
    return {"job_id": job_id, "message": "Job posted! Share this ID with applicants."}

# ── Apply for a Job ─────────────────────────────────
@app.post("/apply")
def apply_job(data: ApplyRequest):
    if data.job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job ID not found")

    jd = jobs[data.job_id]

    prompt = f"""
You are an expert HR recruiter. Analyze this job application and return a JSON response with:
- match_percentage (0-100)
- matched_skills (list)
- missing_skills (list)
- verdict (one of: "Strong Match", "Moderate Match", "Weak Match")
- summary (2-3 sentence explanation)

Job Description:
{jd}

Candidate CV:
{data.cv_text}

Respond ONLY with valid JSON, no extra text.
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )

    content = response.choices[0].message.content.strip()

    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]

    result = json.loads(content)
    result["job_id"] = data.job_id
    return result

# ── Frontend ─────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Job Application Scorer</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: Arial, sans-serif; background: #f0f4ff; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .container { background: white; padding: 40px; border-radius: 12px; width: 100%; max-width: 600px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }
        h1 { color: #4f46e5; margin-bottom: 10px; }
        p { color: #666; margin-bottom: 30px; }
        .role-btns { display: flex; gap: 16px; margin-bottom: 30px; }
        .role-btn { flex: 1; padding: 20px; border: 2px solid #e5e7eb; border-radius: 10px; cursor: pointer; text-align: center; background: white; font-size: 16px; transition: all 0.2s; }
        .role-btn:hover { border-color: #4f46e5; }
        .role-btn.active { border-color: #4f46e5; background: #eef2ff; font-weight: bold; }
        .section { display: none; }
        .section.active { display: block; }
        label { font-weight: bold; color: #444; display: block; margin-bottom: 6px; }
        textarea { width: 100%; height: 160px; padding: 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; margin-bottom: 16px; resize: vertical; }
        input { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; margin-bottom: 16px; }
        button { background: #4f46e5; color: white; padding: 12px 30px; border: none; border-radius: 8px; cursor: pointer; font-size: 16px; width: 100%; }
        button:hover { background: #4338ca; }
        .result { margin-top: 24px; padding: 20px; background: #f9fafb; border-radius: 10px; display: none; }
        .match { font-size: 40px; font-weight: bold; color: #4f46e5; }
        .verdict { font-size: 18px; margin: 8px 0 16px; }
        .tag { display: inline-block; padding: 4px 12px; border-radius: 20px; margin: 4px; font-size: 13px; }
        .matched { background: #dcfce7; color: #16a34a; }
        .missing { background: #fee2e2; color: #dc2626; }
        .job-id-box { background: #eef2ff; border: 2px dashed #4f46e5; border-radius: 8px; padding: 16px; text-align: center; margin-top: 16px; }
        .job-id-box span { font-size: 28px; font-weight: bold; color: #4f46e5; letter-spacing: 2px; }
        .skills { margin: 10px 0; }
    </style>
</head>
<body>
<div class="container">
    <h1> Job Application Scorer</h1>
    <p>AI-powered recruiter — instant CV vs JD matching</p>

    <div class="role-btns">
        <button class="role-btn" style="color:#4f46e5;" onclick="setRole('company', this)">🏢 Company</button>
        <button class="role-btn" style="color:#16a34a;" onclick="setRole('seeker', this)">👤 Job Seeker</button>
    </div>

    <!-- Company Section -->
    <div class="section" id="company-section">
        <label>Job Description</label>
        <textarea id="jd" placeholder="Describe the role, required skills, experience..."></textarea>
        <button onclick="postJob()">Post Job & Get ID</button>
        <div class="result" id="company-result">
            <p>✅ Job posted! Share this ID with applicants:</p>
            <div class="job-id-box"><span id="generated-id"></span></div>
        </div>
    </div>

    <!-- Seeker Section -->
    <div class="section" id="seeker-section">
        <label>Job ID</label>
        <input id="job-id" placeholder="Enter Job ID (e.g. JOB-ABC123)" />
        <label>Your CV</label>
        <textarea id="cv" placeholder="Paste your CV / resume here..."></textarea>
        <button onclick="applyJob()">Score My Application</button>
        <div class="result" id="seeker-result">
            <div class="match" id="match"></div>
            <div class="verdict" id="verdict"></div>
            <div class="skills" id="matched"></div>
            <div class="skills" id="missing"></div>
            <p id="summary" style="margin-top:12px; color:#555;"></p>
        </div>
    </div>
</div>

<script>
    function setRole(role, btn) {
        document.querySelectorAll('.role-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(role + '-section').classList.add('active');
    }

    async function postJob() {
        const jd = document.getElementById('jd').value;
        const btn = document.querySelector('#company-section button');
        btn.textContent = 'Posting...';
        const res = await fetch('/job', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ job_description: jd })
        });
        const data = await res.json();
        document.getElementById('generated-id').textContent = data.job_id;
        document.getElementById('company-result').style.display = 'block';
        btn.textContent = 'Post Job & Get ID';
    }

    async function applyJob() {
        const job_id = document.getElementById('job-id').value;
        const cv = document.getElementById('cv').value;
        const btn = document.querySelector('#seeker-section button');
        btn.textContent = 'Scoring...';
        const res = await fetch('/apply', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ job_id: job_id, cv_text: cv })
        });
        const data = await res.json();
        document.getElementById('match').textContent = data.match_percentage + '% Match';
        document.getElementById('verdict').textContent = '✅ ' + data.verdict;
        document.getElementById('matched').innerHTML = '<b>Matched Skills:</b> ' + data.matched_skills.map(s => `<span class="tag matched">${s}</span>`).join('');
        document.getElementById('missing').innerHTML = '<b>Missing Skills:</b> ' + data.missing_skills.map(s => `<span class="tag missing">${s}</span>`).join('');
        document.getElementById('summary').textContent = data.summary;
        document.getElementById('seeker-result').style.display = 'block';
        btn.textContent = 'Score My Application';
    }
</script>
</body>
</html>
"""