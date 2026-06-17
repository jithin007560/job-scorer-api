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

jobs = {}

def make_job_id():
    letters = string.ascii_uppercase + string.digits
    return "JOB-" + "".join(random.choices(letters, k=6))

class JobPost(BaseModel):
    job_description: str
    company_email: str

class ApplyRequest(BaseModel):
    job_id: str
    cv_text: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/job")
def post_job(data: JobPost):
    job_id = make_job_id()
    jobs[job_id] = {
        "description": data.job_description,
        "email": data.company_email
    }
    return {"job_id": job_id}

@app.post("/apply")
def apply_job(data: ApplyRequest):
    if data.job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[data.job_id]

    prompt = f"""
You are an HR recruiter. Compare this job description and CV.
Return ONLY a JSON with these fields:
- match_percentage (number 0-100)
- matched_skills (list)
- missing_skills (list)
- verdict (Strong Match / Moderate Match / Weak Match)
- summary (2 sentences)

Job Description:
{job["description"]}

CV:
{data.cv_text}
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
    result["company_email"] = job["email"]
    return result

@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Job Scorer</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 600px; margin: 60px auto; padding: 20px; background: #f0f4ff; }
        .box { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 16px rgba(0,0,0,0.1); }
        h1 { color: #4f46e5; }
        .btns { display: flex; gap: 12px; margin: 20px 0; }
        .btn { flex: 1; padding: 16px; border: 2px solid #ddd; border-radius: 8px; cursor: pointer; background: white; font-size: 15px; }
        .btn.active { border-color: #4f46e5; background: #eef2ff; color: #4f46e5; font-weight: bold; }
        .section { display: none; }
        .section.active { display: block; }
        label { font-weight: bold; display: block; margin: 12px 0 4px; }
        input, textarea { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; }
        textarea { height: 140px; resize: vertical; }
        .submit { margin-top: 14px; background: #4f46e5; color: white; padding: 12px; border: none; border-radius: 8px; width: 100%; font-size: 15px; cursor: pointer; }
        .submit:hover { background: #4338ca; }
        .result { margin-top: 20px; padding: 16px; background: #f9fafb; border-radius: 8px; display: none; }
        .score { font-size: 38px; font-weight: bold; color: #4f46e5; }
        .tag { display: inline-block; padding: 3px 10px; border-radius: 16px; margin: 3px; font-size: 13px; }
        .green { background: #dcfce7; color: #16a34a; }
        .red { background: #fee2e2; color: #dc2626; }
        .apply { margin-top: 14px; background: #16a34a; color: white; padding: 12px; border: none; border-radius: 8px; width: 100%; font-size: 15px; cursor: pointer; display: none; }
        .id-box { background: #eef2ff; border: 2px dashed #4f46e5; border-radius: 8px; padding: 14px; text-align: center; margin-top: 14px; font-size: 26px; font-weight: bold; color: #4f46e5; letter-spacing: 2px; display: none; }
    </style>
</head>
<body>
<div class="box">
    <h1>🎯 Job Scorer</h1>
    <p style="color:#666">AI-powered CV vs Job matching</p>

    <div class="btns">
        <button class="btn" onclick="show('company', this)">🏢 Company</button>
        <button class="btn" style="color:#16a34a" onclick="show('seeker', this)">👤 Job Seeker</button>
    </div>

    <div class="section" id="company">
        <label>Company Email</label>
        <input id="email" type="email" placeholder="hr@company.com" />
        <label>Job Description</label>
        <textarea id="jd" placeholder="Describe the role and required skills..."></textarea>
        <button class="submit" onclick="postJob()">Post Job</button>
        <div class="id-box" id="job-id-box"></div>
    </div>

    <div class="section" id="seeker">
        <label>Job ID</label>
        <input id="job-id" placeholder="e.g. JOB-ABC123" />
        <label>Your CV</label>
        <textarea id="cv" placeholder="Paste your CV here..."></textarea>
        <button class="submit" onclick="scoreCV()">Check My Match</button>
        <div class="result" id="result">
            <div class="score" id="score"></div>
            <div style="margin:8px 0 14px;font-size:17px" id="verdict"></div>
            <div id="matched"></div>
            <div id="missing"></div>
            <p style="margin-top:10px;color:#555" id="summary"></p>
            <button class="apply" id="apply-btn" onclick="applyNow()">🚀 Apply to Company</button>
        </div>
    </div>
</div>

<script>
    let email = '';

    function show(role, btn) {
        document.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(role).classList.add('active');
    }

    async function postJob() {
        const res = await fetch('/job', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                job_description: document.getElementById('jd').value,
                company_email: document.getElementById('email').value
            })
        });
        const data = await res.json();
        const box = document.getElementById('job-id-box');
        box.textContent = data.job_id;
        box.style.display = 'block';
    }

    async function scoreCV() {
        const res = await fetch('/apply', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                job_id: document.getElementById('job-id').value,
                cv_text: document.getElementById('cv').value
            })
        });
        const data = await res.json();
        email = data.company_email;

        document.getElementById('score').textContent = data.match_percentage + '% Match';
        document.getElementById('verdict').textContent = '✅ ' + data.verdict;
        document.getElementById('matched').innerHTML = '<b>Matched:</b> ' + data.matched_skills.map(s => `<span class="tag green">${s}</span>`).join('');
        document.getElementById('missing').innerHTML = '<b>Missing:</b> ' + data.missing_skills.map(s => `<span class="tag red">${s}</span>`).join('');
        document.getElementById('summary').textContent = data.summary;
        document.getElementById('result').style.display = 'block';

        if (data.match_percentage === 100) {
            document.getElementById('apply-btn').style.display = 'block';
        }
    }

    function applyNow() {
        window.location.href = `mailto:${email}?subject=Job Application&body=Hi, I got a 100% match for your job posting!`;
    }
</script>
</body>
</html>
"""