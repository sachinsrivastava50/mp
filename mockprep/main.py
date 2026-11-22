"""
MockPrep - Single-file FastAPI Backend
Serves frontend + all API routes in one clean file.
"""
import os, json, random, re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
import jwt
from passlib.context import CryptContext

# ─── Config ───────────────────────────────────────────────────────────────────
SECRET_KEY   = os.getenv("SECRET_KEY", "mockprep_secret_iet_lucknow_group05_2026")
ALGORITHM    = "HS256"
TOKEN_EXPIRE = 60 * 24 * 7          # 7 days in minutes

BASE_DIR = Path(__file__).parent

# ── Frontend path: check multiple locations so it works locally AND on Render ─
def _find_frontend() -> Path:
    candidates = [
        BASE_DIR / "frontend",           # local: mockprep/frontend
        Path.cwd() / "frontend",         # Render: cwd/frontend
        Path("/opt/render/project/src/frontend"),  # Render absolute fallback
    ]
    for p in candidates:
        if p.is_dir() and (p / "index.html").is_file():
            return p
    return BASE_DIR / "frontend"          # default even if missing

FRONTEND_DIR = _find_frontend()
DB_URL       = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'mockprep.db'}")

# ─── Database ─────────────────────────────────────────────────────────────────
connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
engine       = create_engine(DB_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base         = declarative_base()

class User(Base):
    __tablename__ = "users"
    id              = Column(Integer, primary_key=True, index=True)
    name            = Column(String(100), nullable=False)
    email           = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at      = Column(DateTime, default=datetime.utcnow)
    sessions        = relationship("InterviewSession", back_populates="user", cascade="all, delete-orphan")
    results         = relationship("QuestionResult",   back_populates="user", cascade="all, delete-orphan")

class InterviewSession(Base):
    __tablename__ = "interview_sessions"
    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    role            = Column(String(100), nullable=False)
    interview_type  = Column(String(50),  nullable=False)
    difficulty      = Column(String(50),  nullable=False)
    status          = Column(String(50),  default="IN_PROGRESS")
    average_score   = Column(Float, default=0.0)
    total_questions = Column(Integer, default=0)
    started_at      = Column(DateTime, default=datetime.utcnow)
    completed_at    = Column(DateTime, nullable=True)
    user            = relationship("User", back_populates="sessions")
    results         = relationship("QuestionResult", back_populates="session", cascade="all, delete-orphan")

class QuestionResult(Base):
    __tablename__ = "question_results"
    id               = Column(Integer, primary_key=True, index=True)
    session_id       = Column(Integer, ForeignKey("interview_sessions.id"), nullable=False)
    user_id          = Column(Integer, ForeignKey("users.id"), nullable=False)
    question_text    = Column(Text, nullable=False)
    category         = Column(String(100), nullable=True)
    user_answer      = Column(Text, nullable=False)
    score            = Column(Float, nullable=False)
    correctness      = Column(Float, default=0.0)
    clarity          = Column(Float, default=0.0)
    depth            = Column(Float, default=0.0)
    relevance        = Column(Float, default=0.0)
    communication    = Column(Float, default=0.0)
    feedback_summary = Column(Text, nullable=True)
    strengths_json   = Column(Text, nullable=True)
    improvements_json= Column(Text, nullable=True)
    model_answer     = Column(Text, nullable=True)
    time_taken_seconds = Column(Integer, default=0)
    created_at       = Column(DateTime, default=datetime.utcnow)
    session          = relationship("InterviewSession", back_populates="results")
    user             = relationship("User", back_populates="results")

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ─── Auth helpers ─────────────────────────────────────────────────────────────
pwd_ctx  = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

def hash_pw(pw):       return pwd_ctx.hash(pw)
def verify_pw(pw, hpw):return pwd_ctx.verify(pw, hpw)

def make_token(user_id: int) -> str:
    exp = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE)
    return jwt.encode({"sub": str(user_id), "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)

def current_user(creds: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> User:
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        uid = int(payload["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# ─── Schemas ──────────────────────────────────────────────────────────────────
class RegisterIn(BaseModel):
    name: str
    email: str
    password: str

class LoginIn(BaseModel):
    email: str
    password: str

class SessionIn(BaseModel):
    role: str
    interview_type: str
    difficulty: str

class GenQuestionIn(BaseModel):
    session_id: int
    role: str
    interview_type: str
    difficulty: str
    previous_questions: Optional[List[str]] = []

class SubmitAnswerIn(BaseModel):
    session_id: int
    question_text: str
    category: Optional[str] = "General"
    user_answer: str
    time_taken_seconds: Optional[int] = 0

# ─── Rich Diverse Question Bank ───────────────────────────────────────────────
QUESTION_BANK = [
    # ── Software Engineer: Technical (Easy, Medium, Hard)
    {"role":"Software Engineer","type":"Technical","diff":"Easy",
     "question":"What is the difference between a process and a thread? How does memory sharing differ between them?",
     "category":"Operating Systems","hint":"Think about address spaces, heap vs stack, and context-switch overhead.",
     "keywords":["process","thread","memory","stack","heap","address","context","switch","shared","cpu","overhead"]},
    {"role":"Software Engineer","type":"Technical","diff":"Easy",
     "question":"Explain how a HashMap works internally. What happens during a hash collision and how is it resolved?",
     "category":"Data Structures","hint":"Discuss hashing functions, bucket arrays, chaining with linked lists/red-black trees, load factor.",
     "keywords":["hash","bucket","collision","chaining","linked","tree","load","factor","array","complexity"]},
    {"role":"Software Engineer","type":"Technical","diff":"Easy",
     "question":"What are the ACID properties in database management systems? Explain each with a short banking transaction example.",
     "category":"Databases","hint":"Atomicity, Consistency, Isolation, Durability with rollback and commit semantics.",
     "keywords":["acid","atomicity","consistency","isolation","durability","transaction","rollback","commit","database"]},
    {"role":"Software Engineer","type":"Technical","diff":"Medium",
     "question":"Explain the difference between optimistic and pessimistic locking in databases. In what scenarios would you choose one over the other?",
     "category":"Databases","hint":"Consider contention levels, SELECT FOR UPDATE, version counters, and retry overheads.",
     "keywords":["lock","optimistic","pessimistic","contention","version","update","transaction","concurrency","retry"]},
    {"role":"Software Engineer","type":"Technical","diff":"Medium",
     "question":"Design a URL shortening service like Bitly. How would you generate unique aliases and efficiently handle high-read traffic?",
     "category":"System Design","hint":"Base62 encoding, distributed ID generation (Snowflake), Redis caching, DB indexing.",
     "keywords":["url","shortener","base62","hash","cache","redis","database","snowflake","redirect","throughput"]},
    {"role":"Software Engineer","type":"Technical","diff":"Medium",
     "question":"What is the difference between TCP and UDP? When would you strictly pick UDP over TCP in a production system?",
     "category":"Networking","hint":"Connection-oriented, 3-way handshake, congestion control vs streaming/gaming packet loss tolerance.",
     "keywords":["tcp","udp","handshake","packet","loss","streaming","latency","reliable","connection","header"]},
    {"role":"Software Engineer","type":"Technical","diff":"Hard",
     "question":"Walk me through how the Raft consensus algorithm handles leader election, log replication, and network partitions without split-brain.",
     "category":"Distributed Systems","hint":"Terms, election timeouts, quorum majority (N/2 + 1), term numbers, uncommitted entries.",
     "keywords":["raft","consensus","leader","election","quorum","majority","partition","split","brain","term","log"]},
    {"role":"Software Engineer","type":"Technical","diff":"Hard",
     "question":"How would you design a distributed rate limiter capable of handling 500k requests/second across multiple geographical data centers?",
     "category":"Distributed Systems","hint":"Token bucket, sliding window counter, Redis with Lua script, local memory caching, fail-open policy.",
     "keywords":["rate","limiter","token","bucket","sliding","window","redis","lua","latency","datacenter","cluster"]},
    {"role":"Software Engineer","type":"Technical","diff":"Hard",
     "question":"Explain memory management in modern runtimes (JVM or V8): how does generational garbage collection (Mark & Sweep) mitigate latency spikes?",
     "category":"Computer Architecture","hint":"Young gen (Eden, Survivor) vs Old gen, stop-the-world pauses, incremental marking.",
     "keywords":["garbage","collection","heap","memory","young","old","generation","pause","mark","sweep","v8","jvm"]},

    # ── Frontend Developer: Technical
    {"role":"Frontend Developer","type":"Technical","diff":"Easy",
     "question":"Explain the CSS Box Model and the practical difference between content-box and border-box sizing.",
     "category":"CSS & Layout","hint":"Margin, border, padding, content width calculations.",
     "keywords":["box","model","border","padding","margin","content","sizing","width","layout"]},
    {"role":"Frontend Developer","type":"Technical","diff":"Medium",
     "question":"Explain the JavaScript Event Loop in detail: microtasks (Promises), macrotasks (setTimeout), and requestAnimationFrame execution order.",
     "category":"JavaScript Internals","hint":"Call stack, microtask queue drainage, task queue, render phase.",
     "keywords":["event","loop","call","stack","microtask","macrotask","promise","settimeout","queue","render"]},
    {"role":"Frontend Developer","type":"Technical","diff":"Medium",
     "question":"How does React's Virtual DOM diffing algorithm work? Why is using array index as a key considered an anti-pattern?",
     "category":"React Internals","hint":"Reconciliation, heuristic O(n), fiber nodes, unmounting vs updating state mismatch.",
     "keywords":["virtual","dom","reconciliation","diffing","fiber","key","index","state","render","component"]},
    {"role":"Frontend Developer","type":"Technical","diff":"Hard",
     "question":"How would you optimize Core Web Vitals (LCP, FID/INP, CLS) for an enterprise web application with heavy asset bundles?",
     "category":"Web Performance","hint":"SSR/SSG, code-splitting, lazy loading, font optimization, critical CSS, image CDN.",
     "keywords":["core","web","vitals","lcp","inp","cls","bundle","lazy","splitting","performance","render"]},

    # ── Backend Developer: Technical
    {"role":"Backend Developer","type":"Technical","diff":"Easy",
     "question":"What is RESTful API architecture? Explain the significance of HTTP status codes 200, 201, 400, 401, 403, and 500.",
     "category":"API Design","hint":"Statelessness, resource URI, client vs server errors, authentication vs authorization.",
     "keywords":["rest","api","http","stateless","status","endpoint","authentication","authorization","json"]},
    {"role":"Backend Developer","type":"Technical","diff":"Medium",
     "question":"Explain the Saga pattern for distributed transactions in microservices. When would you choose choreography over orchestration?",
     "category":"Microservices","hint":"Compensating transactions, 2PC alternatives, event broker vs central coordinator.",
     "keywords":["saga","distributed","transaction","orchestration","choreography","compensating","event","microservices"]},
    {"role":"Backend Developer","type":"Technical","diff":"Medium",
     "question":"How do database connection pools (like HikariCP or PgBouncer) work and how do you size them for high concurrency?",
     "category":"Database Infrastructure","hint":"Connection handshake cost, thread contention, Little's Law, CPU core scaling.",
     "keywords":["connection","pool","database","concurrency","threads","cpu","hikari","latency","timeout"]},
    {"role":"Backend Developer","type":"Technical","diff":"Hard",
     "question":"How would you design an event-driven architecture using Apache Kafka to ensure exactly-once processing semantics across microservices?",
     "category":"Distributed Streaming","hint":"Producer idempotence, transactional outbox pattern, consumer offset commits, deduplication.",
     "keywords":["kafka","event","exactly","once","idempotent","outbox","partition","offset","consumer","producer"]},

    # ── Data Analyst / Data Scientist: Technical
    {"role":"Data Analyst","type":"Technical","diff":"Easy",
     "question":"What is the difference between WHERE and HAVING clauses in SQL? Provide a specific query where WHERE will throw an error.",
     "category":"SQL & Query Optimization","hint":"Execution order: FROM -> WHERE -> GROUP BY -> HAVING. Aggregates cannot be filtered in WHERE.",
     "keywords":["where","having","sql","group","by","aggregate","count","sum","filter","syntax"]},
    {"role":"Data Analyst","type":"Technical","diff":"Medium",
     "question":"How do you detect, evaluate, and handle missing data (MCAR, MAR, MNAR) and outliers in a business dataset?",
     "category":"Data Cleaning & Prep","hint":"Mean/median imputation, KNN/MICE, IQR boundaries, domain context, business impact.",
     "keywords":["missing","outlier","imputation","mcar","mar","iqr","median","skew","variance","dataset"]},
    {"role":"Data Analyst","type":"Technical","diff":"Medium",
     "question":"Explain window functions in SQL (like ROW_NUMBER, RANK, DENSE_RANK, and LAG/LEAD) with practical analytical use cases.",
     "category":"Advanced SQL","hint":"Partition by, order by, handling ties, running totals, cohort comparisons.",
     "keywords":["window","function","rank","dense","partition","over","lag","lead","running","total"]},
    {"role":"Data Analyst","type":"Technical","diff":"Hard",
     "question":"Design an end-to-end A/B test for a major product feature: how do you calculate sample size, ensure statistical power, and guard against p-hacking?",
     "category":"Statistical Experimentation","hint":"Null hypothesis, Type I/II errors, MDE, alpha, power (1-beta), variance reduction (CUPED).",
     "keywords":["ab","test","hypothesis","statistical","power","sample","significance","p","value","variance","experiment"]},

    # ── Product Manager: Strategy & Execution
    {"role":"Product Manager","type":"Technical","diff":"Easy",
     "question":"How do you define and prioritize product features using the RICE (Reach, Impact, Confidence, Effort) scoring framework?",
     "category":"Product Prioritization","hint":"Formula: (R * I * C) / E, balancing quantitative data with development bandwidth.",
     "keywords":["rice","reach","impact","confidence","effort","prioritize","framework","roadmap","score"]},
    {"role":"Product Manager","type":"Technical","diff":"Medium",
     "question":"If daily active users (DAU) for our core mobile app dropped by 12% week-over-week, walk me through your step-by-step diagnostic process.",
     "category":"Root Cause Analysis","hint":"Internal vs external factors, funnel breakdown, platform/version segmentation, release bug vs seasonality.",
     "keywords":["dau","metric","drop","funnel","segmentation","diagnostic","release","analytics","cohort","root","cause"]},
    {"role":"Product Manager","type":"Technical","diff":"Hard",
     "question":"How would you formulate the go-to-market and monetization strategy for launching an AI-powered conversational copilot?",
     "category":"Product Strategy & GTM","hint":"Pricing tiers (usage vs seat), ICP definition, friction-free onboarding, adoption KPIs.",
     "keywords":["monetization","pricing","gtm","strategy","copilot","ai","adoption","retention","icp","value"]},

    # ── Behavioral (Across All Roles)
    {"role":"Software Engineer","type":"Behavioral","diff":"Easy",
     "question":"Tell me about a time you had to quickly learn an unfamiliar technology or framework to deliver a project on time.",
     "category":"Adaptability & Learning","hint":"STAR technique: context, deliberate learning strategy, implementation, positive outcome.",
     "keywords":["learn","new","technology","framework","project","deadline","documentation","delivered"]},
    {"role":"Software Engineer","type":"Behavioral","diff":"Medium",
     "question":"Describe a situation where you strongly disagreed with a senior engineer or manager on a technical architecture decision. How did you handle it?",
     "category":"Conflict Resolution","hint":"STAR technique: objective data, active listening, finding compromise, disagree and commit.",
     "keywords":["disagree","architecture","decision","manager","data","compromise","communication","outcome"]},
    {"role":"Software Engineer","type":"Behavioral","diff":"Medium",
     "question":"Tell me about a project that failed or did not meet customer expectations. What was your role and what systemic changes did you implement?",
     "category":"Ownership & Resilience","hint":"Take ownership without blaming others, post-mortem process, lessons learned, permanent improvements.",
     "keywords":["failed","mistake","ownership","postmortem","learned","expectation","improved","prevention"]},
    {"role":"Software Engineer","type":"Behavioral","diff":"Hard",
     "question":"Give an example of a high-pressure production incident you resolved under tight SLA deadlines while keeping stakeholders informed.",
     "category":"Crisis Management","hint":"Triaging, incident response protocol, clear communication channels, blameless post-incident RCA.",
     "keywords":["incident","production","outage","pressure","communication","triage","sla","rca","resolution"]},

    # ── System Design & Architecture
    {"role":"Software Engineer","type":"System Design","diff":"Medium",
     "question":"Design a scalable Notification System supporting Push, SMS, and Email with guaranteed delivery and user preference filtering.",
     "category":"System Design","hint":"Message queues (SQS/Kafka), worker pools, third-party vendor abstraction, rate limiting, retry/DLQ.",
     "keywords":["notification","queue","push","sms","email","dlq","worker","scalability","retry","preference"]},
    {"role":"Software Engineer","type":"System Design","diff":"Hard",
     "question":"Design a distributed, highly available Key-Value store like DynamoDB or Cassandra. Explain data partitioning, replication, and quorum reads/writes.",
     "category":"Distributed Storage","hint":"Consistent hashing, virtual nodes, replication factor, tunable consistency (W + R > N), gossip protocol.",
     "keywords":["key","value","consistent","hashing","replication","quorum","dynamo","cassandra","partition","availability"]},

    # ── HR & Cultural Fit
    {"role":"Software Engineer","type":"HR","diff":"Easy",
     "question":"Why are you interested in this engineering position, and what unique technical strengths or perspective do you bring to our team?",
     "category":"Cultural Fit & Motivation","hint":"Connect personal passion with team vision, mention relevant hands-on projects, emphasize team collaboration.",
     "keywords":["passion","strength","team","growth","projects","interest","culture","collaboration"]}
]

# ── Dynamic Question Generator ────────────────────────────────────────────────
def generate_question(role: str, itype: str, diff: str, previous: list) -> dict:
    """
    Selects a fresh, non-repeating question from the bank, or dynamically synthesizes
    an authentic, tailored interview challenge if the bank is exhausted or custom role is used.
    """
    prev_set = set(p.strip().lower() for p in previous if isinstance(p, str))

    # Match pool
    pool = [
        q for q in QUESTION_BANK
        if (q["role"].lower() == role.lower() or role.lower() in q["role"].lower() or q["role"] == "Software Engineer")
        and q["type"].lower() == itype.lower()
        and q.get("diff", "").lower() == diff.lower()
    ]

    if not pool:
        pool = [q for q in QUESTION_BANK if q["type"].lower() == itype.lower()]
    if not pool:
        pool = list(QUESTION_BANK)

    fresh = [q for q in pool if q["question"].strip().lower() not in prev_set]

    if fresh:
        chosen = random.choice(fresh)
        return {
            "question": chosen["question"],
            "category": chosen.get("category", "Core Competency"),
            "hint": chosen.get("hint", "Structure your answer with clear definitions, trade-offs, and examples."),
            "expected_key_points": [
                f"Accurate understanding of {chosen.get('category', 'technical core')}",
                "Clear architectural or operational trade-offs",
                "Structured delivery with practical real-world context",
                "Quantifiable outcomes or metrics where relevant"
            ]
        }

    # If pool is exhausted or user asked for a custom role, synthesize a unique dynamic question
    dynamic_topics = {
        "Technical": [
            ("Concurrency & Memory", f"In {role}, how do you identify, profile, and fix memory leaks or thread contention under sustained load?"),
            ("High Availability & Fault Tolerance", f"For a mission-critical {role} service, design a multi-region failover strategy with minimal downtime (RTO) and data loss (RPO)."),
            ("API & Scalability", f"Explain how you would architect asynchronous background task processing for a high-volume {role} platform."),
            ("Security & Data Protection", f"How do you enforce zero-trust authentication, token rotation, and SQL/XSS prevention in a modern {role} application?"),
            ("Performance Optimization", f"Walk me through your systematic approach to profiling CPU and database query bottlenecks in a slow {role} subsystem.")
        ],
        "Behavioral": [
            ("Cross-functional Alignment", f"As a {role}, describe a situation where you had to influence non-technical stakeholders to approve a major technical refactoring."),
            ("Delivery Under Ambiguity", f"Tell me about a time in your {role} career when project specifications were vague. How did you clarify requirements and deliver successfully?"),
            ("Mentorship & Code Quality", f"Describe an experience where you helped an underperforming teammate improve their technical standards and code reviews.")
        ],
        "System Design": [
            ("Scalable Systems", f"Architect an end-to-end real-time analytics and telemetry tracking pipeline for a {role} infrastructure handling 200k events/sec."),
            ("Distributed Caching", f"How would you design a multi-tier caching system for {role} to eliminate cache stampedes and hot-key degradation?")
        ]
    }

    type_key = itype if itype in dynamic_topics else "Technical"
    candidates = dynamic_topics.get(type_key, dynamic_topics["Technical"])
    cat, q_text = random.choice(candidates)

    # Ensure uniqueness with timestamp variation if needed
    if q_text.strip().lower() in prev_set:
        q_text += f" (Discuss specific edge cases and error handling for {diff} level scenarios)."

    return {
        "question": q_text,
        "category": f"{role} • {cat}",
        "hint": f"Demonstrate deep {diff}-level insights, practical implementation steps, and concrete trade-offs.",
        "expected_key_points": [
            f"Demonstrate comprehensive mastery of {role} fundamentals",
            "Evaluate trade-offs between competing approaches",
            "Provide concrete real-world context or implementation details"
        ]
    }


# ── Intelligent AI Answer Evaluation Engine ───────────────────────────────────
def evaluate_answer(question: str, answer: str, role: str, itype: str, diff: str, secs: int) -> dict:
    """
    Evaluates student response dynamically based on:
    - Semantic keyword matching against the question domain
    - Length & substantive depth
    - Structural transitions (trade-offs, analytical phrasing)
    - Vocabulary diversity (anti-repetition check)
    - Behavioral STAR methodology (for behavioral questions)
    Provides varying, fair, realistic scores out of 10 with actionable feedback.
    """
    ans_clean = (answer or "").strip()
    words = ans_clean.split()
    word_count = len(words)
    al = ans_clean.lower()
    ql = question.lower()

    # 1. Check for empty or trivial answers
    if word_count < 10:
        return {
            "overall_score": 2.5,
            "correctness": 2.5,
            "clarity": 3.0,
            "depth": 1.5,
            "relevance": 3.0,
            "communication": 2.5,
            "strengths": ["Answer submitted within the allotted session time."],
            "improvements": [
                "Your answer is too brief to evaluate. Provide a complete, detailed response.",
                "Define the core concept clearly and explain the underlying mechanics.",
                "Include a concrete technical example or practical scenario."
            ],
            "feedback_summary": "Incomplete response scoring 2.5/10. An interview answer requires substantive explanation and real examples.",
            "model_answer": "A strong answer should define the fundamental concept, discuss architecture or mechanics, outline advantages and trade-offs, and conclude with an illustrative real-world example."
        }

    # 2. Vocabulary diversity (checks for spam / repeated words)
    unique_words = len(set(w.lower() for w in words))
    diversity_ratio = unique_words / max(word_count, 1)

    # 3. Extract relevant domain keywords from question & question bank
    matched_q = next((q for q in QUESTION_BANK if q["question"] == question), None)
    expected_keywords = matched_q.get("keywords", []) if matched_q else []
    
    # If no pre-configured keywords, extract key terms (> 4 chars) from question
    if not expected_keywords:
        stopwords = {"what", "which", "where", "difference", "explain", "between", "would", "could", "should", "using", "their", "there", "about", "describe", "design"}
        expected_keywords = [re.sub(r'[^a-z0-9]', '', w) for w in ql.split() if len(w) > 4 and w not in stopwords]

    # Keyword hit count
    keyword_hits = sum(1 for kw in expected_keywords if kw in al)
    keyword_coverage = keyword_hits / max(len(expected_keywords), 1)

    # 4. Dimension Baselines
    # Base starting points
    c_base = 5.0
    cl_base = 5.5
    d_base = 4.5
    r_base = 5.0
    cm_base = 5.5

    # 5. Length & Depth Grading
    if word_count < 25:
        c_base -= 1.5; d_base -= 2.0; cl_base -= 1.0; cm_base -= 1.0
    elif 25 <= word_count < 60:
        c_base += 0.5; d_base += 0.8; cl_base += 0.8; cm_base += 0.8
    elif 60 <= word_count <= 180:
        c_base += 1.8; d_base += 2.2; cl_base += 1.8; cm_base += 1.6
    elif word_count > 180:
        c_base += 2.0; d_base += 2.7; cl_base += 1.2; cm_base += 1.4

    # 6. Keyword & Relevance Impact
    if keyword_coverage > 0.4:
        c_base += 1.8
        r_base += 2.2
        d_base += 1.2
    elif keyword_coverage > 0.15:
        c_base += 0.8
        r_base += 1.0
        d_base += 0.5
    else:
        # Off-topic or low technical content
        c_base -= 1.5
        r_base -= 2.0

    # 7. Analytical & Structural Transitions
    transitions = [
        "because", "therefore", "for example", "specifically", "in contrast",
        "trade-off", "tradeoff", "latency", "performance", "scalability",
        "however", "on the other hand", "firstly", "secondly", "in production",
        "bottleneck", "complexity", "implementation", "architecture"
    ]
    transition_count = sum(1 for t in transitions if t in al)
    if transition_count >= 4:
        cl_base += 1.6
        cm_base += 1.6
        d_base += 0.8
    elif transition_count >= 2:
        cl_base += 0.8
        cm_base += 0.8

    # 8. Behavioral STAR Check
    if itype.lower() == "behavioral":
        star_situation = bool(re.search(r'(in my|when i was|at my|during|while working|we faced)', al))
        star_task = bool(re.search(r'(my role|responsible for|objective was|task was|needed to|goal was)', al))
        star_action = bool(re.search(r'(i decided|i implemented|i proposed|i built|i designed|i scheduled|i analyzed)', al))
        star_result = bool(re.search(r'(result|outcome|improved|reduced|increased|delivered|launched|by \d+%)', al))
        star_score = sum([star_situation, star_task, star_action, star_result])
        if star_score >= 3:
            r_base += 1.8
            cl_base += 1.4
            cm_base += 1.5
        elif star_score <= 1:
            r_base -= 1.0
            d_base -= 1.0

    # 9. Penalize Spam or Repetitive Text
    if diversity_ratio < 0.45:
        c_base -= 3.0
        d_base -= 3.0
        cl_base -= 2.5
        r_base -= 2.5

    # 10. Difficulty Adjustment
    if diff.lower() == "hard":
        d_base -= 0.5  # Higher expectation for hard questions
    elif diff.lower() == "easy":
        d_base += 0.3

    # Add controlled micro-variation based on hash of answer for natural scoring
    salt = (hash(ans_clean) % 7) * 0.1 - 0.3
    c_base += salt
    d_base -= salt * 0.5

    # Clamp scores between 2.0 and 9.8
    correctness = round(min(9.8, max(2.0, c_base)), 1)
    clarity = round(min(9.8, max(2.5, cl_base)), 1)
    depth = round(min(9.8, max(2.0, d_base)), 1)
    relevance = round(min(9.8, max(2.0, r_base)), 1)
    communication = round(min(9.8, max(2.5, cm_base)), 1)

    # Weighted Overall: Correctness 25%, Clarity 20%, Depth 20%, Relevance 20%, Communication 15%
    overall = round(
        correctness * 0.25 + clarity * 0.20 + depth * 0.20 + relevance * 0.20 + communication * 0.15, 1
    )
    overall = min(9.8, max(2.5, overall))

    # Dynamic Strengths & Improvements
    strengths, improvements = [], []
    if keyword_coverage > 0.3:
        strengths.append(f"Strong domain accuracy: addressed core concepts ({keyword_hits} key topics matched).")
    else:
        improvements.append("Include more domain-specific terminology and core technical mechanisms.")

    if depth >= 7.5:
        strengths.append("High technical depth with clear discussion of mechanics and trade-offs.")
    else:
        improvements.append("Elaborate on operational trade-offs, edge cases, or failure modes.")

    if transition_count >= 2:
        strengths.append("Structured delivery using logical transition points and clear explanations.")
    else:
        improvements.append("Use structured formatting (bullet points or numbered steps) to improve clarity.")

    if word_count >= 70:
        strengths.append("Comprehensive response providing adequate depth without unnecessary filler.")
    else:
        improvements.append("Expand your answer to at least 80-120 words to demonstrate thorough mastery.")

    # Feedback summary text
    if overall >= 8.5:
        summary = f"Exceptional answer scoring {overall}/10! Strong technical vocabulary, clear structure, and solid depth."
    elif overall >= 7.0:
        summary = f"Solid answer scoring {overall}/10. Clear understanding shown; expanding on quantifiable metrics will elevate this."
    elif overall >= 5.0:
        summary = f"Fair response scoring {overall}/10. Covers the basics but needs deeper technical explanation and real-world examples."
    else:
        summary = f"Needs improvement ({overall}/10). The response lacks sufficient depth, technical keywords, and structured elaboration."

    # Tailored Model Answer
    model_answer = (
        f"A top-tier answer for this question begins with a crisp definition of the concept, "
        f"highlights key mechanics (such as {', '.join(expected_keywords[:3]) if expected_keywords else 'underlying architecture'}), "
        f"evaluates practical trade-offs (e.g. latency vs consistency, memory vs CPU overhead), "
        f"and concludes with an impactful production example or measurable metric."
    )

    return {
        "overall_score": overall,
        "correctness": correctness,
        "clarity": clarity,
        "depth": depth,
        "relevance": relevance,
        "communication": communication,
        "breakdown": {
            "overall_score": overall,
            "correctness": correctness,
            "clarity": clarity,
            "depth": depth,
            "relevance": relevance,
            "communication": communication
        },
        "strengths": strengths[:3],
        "improvements": improvements[:3],
        "feedback_summary": summary,
        "model_answer": model_answer
    }

# ─── FastAPI App ───────────────────────────────────────────────────────────────
app = FastAPI(title="MockPrep API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "healthy", "app": "MockPrep", "version": "1.0.0"}

# ── Auth Routes ───────────────────────────────────────────────────────────────
@app.post("/api/auth/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email.lower()).first():
        raise HTTPException(400, "Email already registered.")
    user = User(name=body.name, email=body.email.lower(), hashed_password=hash_pw(body.password))
    db.add(user); db.commit(); db.refresh(user)
    return {"access_token": make_token(user.id), "token_type": "bearer",
            "user": {"id": user.id, "name": user.name, "email": user.email,
                     "created_at": user.created_at.isoformat()}}

@app.post("/api/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if not user or not verify_pw(body.password, user.hashed_password):
        raise HTTPException(401, "Invalid email or password.")
    return {"access_token": make_token(user.id), "token_type": "bearer",
            "user": {"id": user.id, "name": user.name, "email": user.email,
                     "created_at": user.created_at.isoformat()}}

@app.get("/api/auth/me")
def me(u: User = Depends(current_user)):
    return {"id": u.id, "name": u.name, "email": u.email, "created_at": u.created_at.isoformat()}

# ── Interview Routes ──────────────────────────────────────────────────────────
@app.post("/api/interview/session", status_code=201)
def create_session(body: SessionIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    s = InterviewSession(user_id=u.id, role=body.role,
                         interview_type=body.interview_type, difficulty=body.difficulty)
    db.add(s); db.commit(); db.refresh(s)
    return _session_dict(s)

@app.get("/api/interview/session/{sid}")
def get_session(sid: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    s = _get_session_or_404(sid, u.id, db)
    return _session_dict(s)

@app.post("/api/interview/generate-question")
def gen_question(body: GenQuestionIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    _get_session_or_404(body.session_id, u.id, db)
    q = generate_question(body.role, body.interview_type, body.difficulty, body.previous_questions)
    return q

@app.post("/api/interview/submit-answer")
def submit_answer(body: SubmitAnswerIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    s = _get_session_or_404(body.session_id, u.id, db)
    ev = evaluate_answer(body.question_text, body.user_answer,
                         s.role, s.interview_type, s.difficulty, body.time_taken_seconds)
    r = QuestionResult(
        session_id=s.id, user_id=u.id,
        question_text=body.question_text, category=body.category,
        user_answer=body.user_answer,
        score=ev["overall_score"], correctness=ev["correctness"],
        clarity=ev["clarity"], depth=ev["depth"],
        relevance=ev["relevance"], communication=ev["communication"],
        feedback_summary=ev["feedback_summary"],
        strengths_json=json.dumps(ev["strengths"]),
        improvements_json=json.dumps(ev["improvements"]),
        model_answer=ev["model_answer"],
        time_taken_seconds=body.time_taken_seconds
    )
    db.add(r); db.commit(); db.refresh(r)
    # update session averages
    all_r = db.query(QuestionResult).filter(QuestionResult.session_id == s.id).all()
    s.average_score   = round(sum(x.score for x in all_r) / len(all_r), 1)
    s.total_questions = len(all_r)
    db.commit()
    return {
        "id": r.id, "session_id": s.id, "score": ev["overall_score"],
        "breakdown": {k: ev[k] for k in ["overall_score","correctness","clarity","depth","relevance","communication"]},
        "strengths": ev["strengths"], "improvements": ev["improvements"],
        "feedback_summary": ev["feedback_summary"], "model_answer": ev["model_answer"]
    }

@app.post("/api/interview/session/{sid}/complete")
def complete_session(sid: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    s = _get_session_or_404(sid, u.id, db)
    s.status = "COMPLETED"; s.completed_at = datetime.utcnow()
    db.commit(); db.refresh(s)
    return _session_dict(s)

# ── Dashboard Routes ──────────────────────────────────────────────────────────
@app.get("/api/dashboard/stats")
def dashboard_stats(u: User = Depends(current_user), db: Session = Depends(get_db)):
    sessions = db.query(InterviewSession).filter(InterviewSession.user_id == u.id)\
                 .order_by(InterviewSession.started_at.desc()).all()
    done = [s for s in sessions if s.total_questions > 0]
    avg  = round(sum(s.average_score for s in done) / len(done), 1) if done else 0.0
    from collections import defaultdict
    role_scores = defaultdict(list)
    for s in done: role_scores[s.role].append(s.average_score)
    best_role, best_avg = "None yet", 0.0
    for role, scores in role_scores.items():
        m = sum(scores)/len(scores)
        if m > best_avg: best_avg, best_role = m, f"{role} ({round(m,1)}/10)"
    return {
        "total_interviews":        len(sessions),
        "average_score":           avg,
        "total_questions_answered":sum(s.total_questions for s in sessions),
        "strongest_role":          best_role,
        "recent_sessions":         [_session_dict(s) for s in sessions[:10]],
        "score_trend":             [s.average_score for s in list(reversed(done))[-10:]]
    }

@app.get("/api/dashboard/session/{sid}/detail")
def session_detail(sid: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    s = _get_session_or_404(sid, u.id, db)
    results = db.query(QuestionResult).filter(QuestionResult.session_id == sid)\
                .order_by(QuestionResult.created_at.asc()).all()
    return {
        "session": _session_dict(s),
        "questions": [{
            "id": r.id,
            "question_text":    r.question_text,
            "category":         r.category,
            "user_answer":      r.user_answer,
            "score":            r.score,
            "breakdown":        {"correctness": r.correctness, "clarity": r.clarity,
                                 "depth": r.depth, "relevance": r.relevance,
                                 "communication": r.communication},
            "feedback_summary": r.feedback_summary,
            "strengths":        json.loads(r.strengths_json   or "[]"),
            "improvements":     json.loads(r.improvements_json or "[]"),
            "model_answer":     r.model_answer,
            "time_taken_seconds": r.time_taken_seconds,
            "created_at":       r.created_at.isoformat()
        } for r in results]
    }

# ── Helper functions ──────────────────────────────────────────────────────────
def _session_dict(s: InterviewSession) -> dict:
    return {
        "id": s.id, "user_id": s.user_id,
        "role": s.role, "interview_type": s.interview_type,
        "difficulty": s.difficulty, "status": s.status,
        "average_score": s.average_score, "total_questions": s.total_questions,
        "started_at":   s.started_at.isoformat(),
        "completed_at": s.completed_at.isoformat() if s.completed_at else None
    }

def _get_session_or_404(sid, uid, db):
    s = db.query(InterviewSession).filter(
        InterviewSession.id == sid, InterviewSession.user_id == uid).first()
    if not s:
        raise HTTPException(404, "Session not found.")
    return s

# ── Debug Route (helps diagnose Render path issues) ───────────────────────────
@app.get("/api/debug", include_in_schema=False)
def debug_info():
    import os
    cwd = os.getcwd()
    files_cwd = os.listdir(cwd) if os.path.isdir(cwd) else []
    base_files = os.listdir(str(BASE_DIR)) if BASE_DIR.is_dir() else []
    return {
        "cwd":              cwd,
        "base_dir":         str(BASE_DIR),
        "frontend_dir":     str(FRONTEND_DIR),
        "frontend_exists":  FRONTEND_DIR.is_dir(),
        "index_exists":     (FRONTEND_DIR / "index.html").is_file(),
        "files_in_cwd":     files_cwd[:30],
        "files_in_base":    base_files[:30],
        "python_file":      str(Path(__file__)),
    }

# ── Serve Frontend (SPA) ──────────────────────────────────────────────────────
if FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        file_path = FRONTEND_DIR / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(FRONTEND_DIR / "index.html"))
else:
    @app.get("/", include_in_schema=False)
    def root():
        return {
            "msg": "API running. Frontend NOT found.",
            "frontend_dir": str(FRONTEND_DIR),
            "debug_url": "/api/debug"
        }
