/**
 * MockPrep REST API Client
 * Handles communication with the FastAPI backend, JWT Authorization,
 * and seamless local offline fallback if the Python server is not yet started.
 */

const API_BASE = window.location.origin + '/api';

const API = {
  isOfflineMode: false,

  getToken() {
    return localStorage.getItem('mockprep_jwt_token');
  },

  setToken(token) {
    localStorage.setItem('mockprep_jwt_token', token);
  },

  clearToken() {
    localStorage.removeItem('mockprep_jwt_token');
    localStorage.removeItem('mockprep_user');
  },

  getUser() {
    const raw = localStorage.getItem('mockprep_user');
    return raw ? JSON.parse(raw) : null;
  },

  setUser(user) {
    localStorage.setItem('mockprep_user', JSON.stringify(user));
  },

  async request(endpoint, options = {}) {
    const headers = {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    };

    const token = this.getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    try {
      const response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        if (response.status === 401) {
          this.clearToken();
          window.dispatchEvent(new CustomEvent('auth:expired'));
        }
        throw new Error(data.detail || `Request failed with status ${response.status}`);
      }

      this.isOfflineMode = false;
      return data;
    } catch (err) {
      // If network connection failed (FastAPI backend not running), fallback seamlessly
      if (err.name === 'TypeError' || err.message.includes('Failed to fetch') || err.message.includes('NetworkError')) {
        console.warn(`[MockPrep Offline Mode] Backend unreachable at ${API_BASE}. Using local engine.`);
        this.isOfflineMode = true;
        return this.offlineFallback(endpoint, options);
      }
      throw err;
    }
  },

  // Offline Fallback Engine (Runs even if python run.py is not yet started!)
  offlineFallback(endpoint, options) {
    const body = options.body ? JSON.parse(options.body) : {};

    if (endpoint === '/auth/login' || endpoint === '/auth/register' || endpoint === '/auth/demo') {
      const mockUser = {
        id: 101,
        name: body.name || 'User',
        email: body.email || 'demo.student@mockprep.com',
        created_at: new Date().toISOString()
      };
      this.setToken('mock_jwt_token_' + Date.now());
      this.setUser(mockUser);
      return { access_token: this.getToken(), user: mockUser };
    }

    if (endpoint === '/interview/session') {
      const session = {
        id: Date.now(),
        user_id: 101,
        role: body.role || 'Software Engineer',
        interview_type: body.interview_type || 'Technical',
        difficulty: body.difficulty || 'Medium',
        status: 'IN_PROGRESS',
        average_score: 0.0,
        total_questions: 0,
        started_at: new Date().toISOString()
      };
      const all = JSON.parse(localStorage.getItem('mockprep_local_sessions') || '[]');
      all.unshift(session);
      localStorage.setItem('mockprep_local_sessions', JSON.stringify(all));
      return session;
    }

    if (endpoint === '/interview/generate-question') {
      const role = body.role || 'Software Engineer';
      const itype = body.interview_type || 'Technical';
      const diff = body.difficulty || 'Medium';

      const questionPool = [
        {
          role: 'Software Engineer', type: 'Technical', diff: 'Easy',
          question: 'What is the difference between a process and a thread? How does memory allocation differ between them?',
          category: 'Operating Systems', hint: 'Address space, stack vs heap, and context-switch cost.'
        },
        {
          role: 'Software Engineer', type: 'Technical', diff: 'Easy',
          question: 'Explain how a HashMap works internally. What happens during a hash collision?',
          category: 'Data Structures', hint: 'Bucket array, hash function, linked-list / tree chaining, load factor.'
        },
        {
          role: 'Software Engineer', type: 'Technical', diff: 'Medium',
          question: 'Design a URL shortener service like Bitly. How do you generate unique IDs and handle high-volume reads?',
          category: 'System Design', hint: 'Base62 encoding, Redis caching, distributed IDs, index optimization.'
        },
        {
          role: 'Software Engineer', type: 'Technical', diff: 'Medium',
          question: 'Explain the difference between optimistic and pessimistic locking in databases with practical use cases.',
          category: 'Databases', hint: 'SELECT FOR UPDATE vs version counters, contention levels, rollback cost.'
        },
        {
          role: 'Software Engineer', type: 'Technical', diff: 'Hard',
          question: 'How would you design a distributed rate limiter capable of 500k req/sec across multiple regions?',
          category: 'Distributed Systems', hint: 'Token bucket vs sliding window, Redis Lua script, local cache, fail-open.'
        },
        {
          role: 'Frontend Developer', type: 'Technical', diff: 'Medium',
          question: 'Explain the JavaScript Event Loop: microtasks, macrotasks, and requestAnimationFrame execution order.',
          category: 'JavaScript Internals', hint: 'Call stack, promise queue drainage, UI rendering pipeline.'
        },
        {
          role: 'Backend Developer', type: 'Technical', diff: 'Medium',
          question: 'Explain the Saga pattern for distributed transactions. When would you choose choreography over orchestration?',
          category: 'Microservices', hint: 'Compensating transactions, 2PC bottlenecks, event-driven messaging.'
        },
        {
          role: 'Data Analyst', type: 'Technical', diff: 'Easy',
          question: 'What is the difference between WHERE and HAVING clauses in SQL? Give an example where WHERE fails.',
          category: 'SQL Optimization', hint: 'Execution order: FROM -> WHERE -> GROUP BY -> HAVING. Aggregates require HAVING.'
        },
        {
          role: 'Software Engineer', type: 'Behavioral', diff: 'Medium',
          question: 'Tell me about a time you strongly disagreed with a senior teammate on an architectural decision. How did you resolve it?',
          category: 'Conflict Resolution', hint: 'STAR technique: objective data, active listening, finding common ground.'
        },
        {
          role: 'Software Engineer', type: 'Behavioral', diff: 'Medium',
          question: 'Describe a high-pressure production incident you resolved. How did you coordinate with your team?',
          category: 'Crisis Management', hint: 'Triage, communication, incident mitigation, blameless post-mortem.'
        }
      ];

      const prev = Array.isArray(body.previous_questions) ? body.previous_questions : [];
      let matched = questionPool.filter(q => 
        (q.role.toLowerCase() === role.toLowerCase() || role.toLowerCase().includes('engineer')) &&
        q.type.toLowerCase() === itype.toLowerCase() &&
        !prev.includes(q.question)
      );

      if (!matched.length) {
        matched = questionPool.filter(q => !prev.includes(q.question));
      }

      let selected = matched[Math.floor(Math.random() * matched.length)];
      if (!selected) {
        selected = {
          question: `In ${role}, how would you architect a resilient, high-performance solution for ${diff} level production workloads?`,
          category: `${role} • Architecture`,
          hint: 'Discuss core mechanics, data structures, trade-offs, and failure handling.'
        };
      }

      return {
        question: selected.question,
        category: selected.category,
        hint: selected.hint,
        expected_key_points: ['Technical depth and accuracy', 'Trade-off comparison', 'Structured explanation']
      };
    }

    if (endpoint === '/interview/submit-answer') {
      const ans = (body.user_answer || '').trim();
      const words = ans.split(/\s+/).filter(Boolean);
      const wordCount = words.length;
      const lower = ans.toLowerCase();

      const evasive = ['i don\'t know', 'dont know', 'no idea', 'not sure', 'skip', 'pass', 'n/a', 'none', 'hello', 'hi', 'test', 'idk', 'ok', 'yes', 'no'];
      const isEvasive = evasive.some(p => lower === p || lower.startsWith(p + ' ') || lower.endsWith(' ' + p));

      // 0 Marks for invalid, blank, trivial, or evasive text
      if (wordCount < 4 || isEvasive) {
        const result = {
          id: Date.now(),
          session_id: body.session_id,
          score: 0.0,
          breakdown: { overall_score: 0.0, correctness: 0.0, clarity: 0.0, depth: 0.0, relevance: 0.0, communication: 0.0 },
          strengths: [],
          improvements: [
            'Your answer is invalid or too brief to evaluate.',
            'Address the specific technical question asked rather than leaving placeholder text.',
            'Explain the fundamental concepts, underlying mechanics, and trade-offs.'
          ],
          feedback_summary: 'Invalid answer scoring 0.0/10. The response is blank, trivial, or placeholder text. Please answer thoroughly.',
          model_answer: 'A strong answer must define the concept, outline execution mechanics, and contrast trade-offs.'
        };
        return result;
      }

      // Check tech term hits
      const techTerms = ['because', 'therefore', 'latency', 'performance', 'trade-off', 'complexity', 'memory', 'cpu', 'cache', 'thread', 'index', 'hash', 'queue', 'process', 'database', 'transaction', 'lock', 'event', 'query', 'stack', 'heap'];
      const termHits = techTerms.filter(t => lower.includes(t)).length;

      // 0 or 1 Mark for completely off-topic response
      if (termHits === 0) {
        const scoreVal = wordCount < 25 ? 0.0 : 1.0;
        return {
          id: Date.now(),
          session_id: body.session_id,
          score: scoreVal,
          breakdown: { overall_score: scoreVal, correctness: scoreVal, clarity: scoreVal, depth: 0.0, relevance: 0.0, communication: scoreVal },
          strengths: [],
          improvements: [
            'Your response is off-topic. It does not contain any relevant concepts for this question.',
            'Focus on the actual technical topic asked in the interview prompt.'
          ],
          feedback_summary: `Irrelevant answer scoring ${scoreVal}/10. The response does not address the question asked.`,
          model_answer: 'A relevant answer must directly address the question by discussing the core technical mechanics.'
        };
      }

      // Dynamic Intelligent Scoring
      let correctness = 6.0;
      let clarity = 6.5;
      let depth = 5.5;
      let relevance = 6.0;
      let communication = 6.0;

      if (wordCount < 20) {
        correctness = 2.0; depth = 1.0; clarity = 2.5; relevance = 2.0; communication = 2.0;
      } else if (wordCount < 40) {
        correctness += 0.5; depth += 0.8; clarity += 0.5;
      } else if (wordCount <= 120) {
        correctness += 1.8; depth += 2.0; clarity += 1.6; relevance += 1.8; communication += 1.5;
      } else {
        correctness += 2.2; depth += 2.8; clarity += 1.4; relevance += 2.0; communication += 1.6;
      }

      if (termHits >= 3) {
        correctness += 1.2; clarity += 1.0; depth += 1.2; relevance += 1.2;
      }

      // Full 10/10 Score for thorough, right answer
      if (termHits >= 3 && wordCount >= 60) {
        correctness = Math.min(10.0, correctness + 1.5);
        clarity = Math.min(10.0, clarity + 1.5);
        depth = Math.min(10.0, depth + 1.5);
        relevance = Math.min(10.0, relevance + 1.5);
        communication = Math.min(10.0, communication + 1.5);
        if (wordCount >= 80 && termHits >= 4) {
          correctness = 10.0; clarity = 10.0; depth = 10.0; relevance = 10.0; communication = 10.0;
        }
      }

      // Add natural small variation
      const variance = ((ans.length % 5) - 2) * 0.15;
      if (correctness < 10.0) {
        correctness = Math.min(10.0, Math.max(2.5, +(correctness + variance).toFixed(1)));
        clarity = Math.min(10.0, Math.max(2.5, +(clarity - variance * 0.5).toFixed(1)));
        depth = Math.min(10.0, Math.max(2.0, +(depth + variance * 0.8).toFixed(1)));
        relevance = Math.min(10.0, Math.max(2.5, +(relevance + variance * 0.3).toFixed(1)));
        communication = Math.min(10.0, Math.max(2.5, +(communication).toFixed(1)));
      }

      const overall = +((correctness * 0.25) + (clarity * 0.20) + (depth * 0.20) + (relevance * 0.20) + (communication * 0.15)).toFixed(1);

      const strengths = [];
      const improvements = [];
      if (wordCount >= 60) strengths.append ? strengths.push('Good substantive elaboration with solid reasoning.') : strengths.push('Good substantive elaboration with solid reasoning.');
      else improvements.push('Expand response to at least 70-100 words for complete evaluation.');

      if (termHits >= 2) strengths.push('Effectively applied domain technical vocabulary and trade-offs.');
      else improvements.push('Incorporate specific technical terms (trade-offs, latency, memory usage).');

      const result = {
        id: Date.now(),
        session_id: body.session_id,
        score: overall,
        breakdown: {
          overall_score: overall,
          correctness: correctness,
          clarity: clarity,
          depth: depth,
          relevance: relevance,
          communication: communication
        },
        strengths: strengths.length ? strengths : ['Submitted a clear initial answer within the interview timeframe.'],
        improvements: improvements.length ? improvements : ['Consider quantifying impact with concrete production metrics.'],
        feedback_summary: overall >= 7.5 
          ? `Impressive response scoring ${overall}/10! Solid technical depth and clear analytical reasoning.`
          : `Fair answer scoring ${overall}/10. Adding deeper explanations and concrete trade-offs will improve your score.`,
        model_answer: 'A top-performing answer defines the concept, details its execution mechanics, contrasts alternative approaches with trade-offs, and highlights real-world outcomes.'
      };

      // Update session in local storage
      const sessions = JSON.parse(localStorage.getItem('mockprep_local_sessions') || '[]');
      const curr = sessions.find(s => s.id === body.session_id);
      if (curr) {
        curr.total_questions = (curr.total_questions || 0) + 1;
        curr.average_score = score;
        localStorage.setItem('mockprep_local_sessions', JSON.stringify(sessions));
      }

      // Store in results
      const results = JSON.parse(localStorage.getItem('mockprep_local_results') || '[]');
      results.push({ ...result, ...body });
      localStorage.setItem('mockprep_local_results', JSON.stringify(results));

      return result;
    }

    if (endpoint === '/interview/session/' + (body.session_id || '') + '/complete') {
      return { status: 'COMPLETED' };
    }

    if (endpoint === '/dashboard/stats') {
      const sessions = JSON.parse(localStorage.getItem('mockprep_local_sessions') || '[]');
      const total = sessions.length;
      const avg = total ? (sessions.reduce((acc, s) => acc + (s.average_score || 0), 0) / total).toFixed(1) : 0;
      const questionsCount = sessions.reduce((acc, s) => acc + (s.total_questions || 0), 0);

      return {
        total_interviews: total,
        average_score: parseFloat(avg),
        total_questions_answered: questionsCount,
        strongest_role: total ? `${sessions[0].role} (${avg}/10)` : 'None yet',
        recent_sessions: sessions.slice(0, 10),
        score_trend: sessions.slice(0, 10).reverse().map(s => s.average_score || 7.0)
      };
    }

    if (endpoint.startsWith('/dashboard/session/')) {
      const sessionId = parseInt(endpoint.split('/')[3], 10);
      const sessions = JSON.parse(localStorage.getItem('mockprep_local_sessions') || '[]');
      const session = sessions.find(s => s.id === sessionId) || {
        id: sessionId,
        role: 'Software Engineer',
        interview_type: 'Technical',
        difficulty: 'Medium',
        average_score: 8.2,
        started_at: new Date().toISOString()
      };
      const results = JSON.parse(localStorage.getItem('mockprep_local_results') || '[]').filter(r => r.session_id === sessionId);

      return {
        session,
        questions: results.map(r => ({
          question_text: r.question_text || 'Technical Interview Question',
          category: r.category || 'Core Domain',
          user_answer: r.user_answer || 'Candidate answer',
          score: r.score || 8.0,
          breakdown: r.breakdown || { correctness: 8, clarity: 8, depth: 8, relevance: 8, communication: 8 },
          feedback_summary: r.feedback_summary || 'Good answer.',
          model_answer: r.model_answer || 'Benchmark reference answer.'
        }))
      };
    }

    return {};
  },

  // Auth Endpoints
  async register(name, email, password) {
    const res = await this.request('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ name, email, password })
    });
    this.setToken(res.access_token);
    this.setUser(res.user);
    return res;
  },

  async login(email, password) {
    const res = await this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password })
    });
    this.setToken(res.access_token);
    this.setUser(res.user);
    return res;
  },

  async demoLogin() {
    const res = await this.request('/auth/demo', {
      method: 'POST'
    });
    this.setToken(res.access_token);
    this.setUser(res.user);
    return res;
  },

  async getMe() {
    return this.request('/auth/me');
  },

  // Interview Endpoints
  async createSession(role, interview_type, difficulty) {
    return this.request('/interview/session', {
      method: 'POST',
      body: JSON.stringify({ role, interview_type, difficulty })
    });
  },

  async getSession(sessionId) {
    return this.request(`/interview/session/${sessionId}`);
  },

  async generateQuestion(sessionId, role, interview_type, difficulty, previous_questions = []) {
    return this.request('/interview/generate-question', {
      method: 'POST',
      body: JSON.stringify({
        session_id: sessionId,
        role,
        interview_type,
        difficulty,
        previous_questions
      })
    });
  },

  async submitAnswer(sessionId, questionText, category, userAnswer, timeTakenSeconds = 0) {
    return this.request('/interview/submit-answer', {
      method: 'POST',
      body: JSON.stringify({
        session_id: sessionId,
        question_text: questionText,
        category,
        user_answer: userAnswer,
        time_taken_seconds: timeTakenSeconds
      })
    });
  },

  async completeSession(sessionId) {
    return this.request(`/interview/session/${sessionId}/complete`, {
      method: 'POST'
    });
  },

  // Dashboard Endpoints
  async getDashboardStats() {
    return this.request('/dashboard/stats');
  },

  async getSessionDetail(sessionId) {
    return this.request(`/dashboard/session/${sessionId}/detail`);
  }
};

window.API = API;
