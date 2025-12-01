/**
 * Divergence Engine API - Cloudflare Worker
 *
 * Endpoints:
 *   POST /predict     - Predict escalation between two actors
 *   POST /divergence  - Compute divergence metrics between distributions
 *   GET  /actors      - List available pre-configured actors
 *   GET  /health      - Health check
 *
 * Deploy: wrangler publish
 */

// Pre-configured actor compression schemes (based on empirical GDELT analysis)
const ACTORS = {
  USA: { distribution: [0.35, 0.25, 0.15, 0.10, 0.05, 0.04, 0.03, 0.02, 0.01], name: "United States" },
  RUS: { distribution: [0.20, 0.20, 0.18, 0.15, 0.10, 0.08, 0.05, 0.03, 0.01], name: "Russia" },
  CHN: { distribution: [0.30, 0.22, 0.18, 0.12, 0.08, 0.05, 0.03, 0.01, 0.01], name: "China" },
  IRN: { distribution: [0.25, 0.20, 0.18, 0.15, 0.10, 0.06, 0.04, 0.01, 0.01], name: "Iran" },
  ISR: { distribution: [0.28, 0.22, 0.17, 0.13, 0.09, 0.05, 0.04, 0.01, 0.01], name: "Israel" },
  UKR: { distribution: [0.22, 0.20, 0.18, 0.15, 0.10, 0.07, 0.05, 0.02, 0.01], name: "Ukraine" },
  PRK: { distribution: [0.18, 0.18, 0.17, 0.16, 0.12, 0.09, 0.06, 0.03, 0.01], name: "North Korea" },
  TWN: { distribution: [0.32, 0.24, 0.16, 0.11, 0.07, 0.05, 0.03, 0.01, 0.01], name: "Taiwan" },
  SAU: { distribution: [0.26, 0.21, 0.17, 0.14, 0.09, 0.06, 0.04, 0.02, 0.01], name: "Saudi Arabia" },
  EUR: { distribution: [0.33, 0.24, 0.16, 0.11, 0.06, 0.05, 0.03, 0.01, 0.01], name: "European Union" },
};

const CATEGORIES = [
  "diplomatic_cooperation",
  "economic_exchange",
  "military_posture",
  "territorial_claims",
  "ideological_narrative",
  "humanitarian_concern",
  "security_threat",
  "resource_competition",
  "historical_grievance"
];

// Landing page HTML
const LANDING_PAGE_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Divergence Engine - Conflict Prediction API</title>
  <meta name="description" content="Predict conflict from divergent worldviews. 100x faster than Python.">
  <style>
    :root{--bg:#0a0a0a;--fg:#e0e0e0;--accent:#00ff88;--accent2:#ff6b6b;--muted:#666;--card:#141414;--border:#2a2a2a}
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'SF Mono','Fira Code',monospace;background:var(--bg);color:var(--fg);line-height:1.6;min-height:100vh}
    .container{max-width:900px;margin:0 auto;padding:2rem}
    header{text-align:center;padding:4rem 0}
    h1{font-size:2.5rem;margin-bottom:1rem}h1 span{color:var(--accent)}
    .tagline{color:var(--muted);font-size:1.1rem;margin-bottom:2rem}
    .formula{background:var(--card);border:1px solid var(--border);padding:1.5rem;border-radius:8px;font-size:1.2rem;margin:2rem 0}
    .formula code{color:var(--accent)}
    .demo{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:2rem;margin:3rem 0}
    .demo h2{margin-bottom:1.5rem;color:var(--accent)}
    .demo-controls{display:flex;gap:1rem;margin-bottom:1.5rem;flex-wrap:wrap}
    select,button{background:var(--bg);color:var(--fg);border:1px solid var(--border);padding:0.75rem 1rem;border-radius:4px;font-family:inherit;font-size:1rem;cursor:pointer}
    button{background:var(--accent);color:var(--bg);font-weight:bold}button:hover{opacity:0.9}
    .result{background:var(--bg);border:1px solid var(--border);border-radius:4px;padding:1rem;overflow-x:auto}
    .result pre{white-space:pre-wrap}
    .risk-LOW{color:var(--accent)}.risk-MODERATE{color:#ffd93d}.risk-ELEVATED{color:#ff9f43}.risk-HIGH{color:var(--accent2)}.risk-CRITICAL{color:#ff0000}
    .links{display:flex;gap:2rem;justify-content:center;margin:2rem 0;flex-wrap:wrap}
    .links a{color:var(--fg);text-decoration:none;padding:0.5rem 1rem;border:1px solid var(--border);border-radius:4px}
    .links a:hover{border-color:var(--accent)}
    footer{text-align:center;padding:3rem 0;color:var(--muted);border-top:1px solid var(--border);margin-top:3rem}
    footer a{color:var(--accent);text-decoration:none}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem;margin:2rem 0}
    .card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:1.5rem}
    .card h3{color:var(--accent);margin-bottom:0.5rem}
    .card p{font-size:0.9rem;color:var(--muted)}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1><span>Divergence</span> Engine</h1>
      <p class="tagline">Predict conflict from divergent worldviews.<br>100x faster than Python. Deployable anywhere.</p>
      <div class="formula">
        <code>Φ(A,B) = D<sub>KL</sub>(A‖B) + D<sub>KL</sub>(B‖A)</code><br><br>
        <em>Conflict is compression divergence. Peace is alignment.</em>
      </div>
      <div class="links">
        <a href="https://github.com/aphoticshaman/nucleation-wasm">GitHub</a>
        <a href="https://zenodo.org/records/17766946">Paper</a>
        <a href="/actors">API: /actors</a>
      </div>
    </header>
    <section class="demo">
      <h2>// Live Demo</h2>
      <div class="demo-controls">
        <select id="actorA"><option value="USA">USA</option><option value="RUS">Russia</option><option value="CHN" selected>China</option><option value="IRN">Iran</option><option value="PRK">N. Korea</option><option value="TWN">Taiwan</option></select>
        <span style="color:var(--muted);padding:0.75rem">vs</span>
        <select id="actorB"><option value="USA" selected>USA</option><option value="RUS">Russia</option><option value="CHN">China</option><option value="IRN">Iran</option><option value="PRK">N. Korea</option><option value="TWN">Taiwan</option></select>
        <button onclick="runPrediction()">Analyze</button>
      </div>
      <div class="result"><pre id="output">// Click Analyze</pre></div>
    </section>
    <h2 style="text-align:center;margin-bottom:1rem">Industry Applications</h2>
    <div class="grid">
      <div class="card"><h3>Finance</h3><p>Portfolio regime detection, counterparty risk, sentiment divergence.</p></div>
      <div class="card"><h3>Defense</h3><p>Adversary modeling, coalition stability, 6-12mo early warning.</p></div>
      <div class="card"><h3>Cybersecurity</h3><p>Threat actor profiling, insider detection, posture drift.</p></div>
      <div class="card"><h3>Supply Chain</h3><p>Supplier risk, vendor health, demand forecasting.</p></div>
    </div>
    <footer>
      <p>Built by <a href="https://twitter.com/Benthic_Shadow">@Benthic_Shadow</a></p>
      <p style="margin-top:0.5rem">Rust/WASM • Cloudflare Edge • MIT License</p>
    </footer>
  </div>
  <script>
    const E=1e-10,A={USA:[.35,.25,.15,.1,.05,.04,.03,.02,.01],RUS:[.2,.2,.18,.15,.1,.08,.05,.03,.01],CHN:[.3,.22,.18,.12,.08,.05,.03,.01,.01],IRN:[.25,.2,.18,.15,.1,.06,.04,.01,.01],PRK:[.18,.18,.17,.16,.12,.09,.06,.03,.01],TWN:[.32,.24,.16,.11,.07,.05,.03,.01,.01]};
    const norm=d=>{const s=d.reduce((a,b)=>a+b,0);return d.map(x=>(x+E)/(s+E*d.length))};
    const kl=(p,q)=>p.reduce((s,pi,i)=>s+Math.max(pi,E)*Math.log(Math.max(pi,E)/Math.max(q[i],E)),0)/Math.LN2;
    function runPrediction(){
      const a=document.getElementById('actorA').value,b=document.getElementById('actorB').value;
      const p=norm(A[a]),q=norm(A[b]);
      const phi=kl(p,q)+kl(q,p),m=p.map((pi,i)=>0.5*(pi+q[i])),js=0.5*kl(p,m)+0.5*kl(q,m);
      const prob=1/(1+Math.exp(-(0.5*phi-0.15)));
      let risk="LOW";if(phi>=0.5)risk="MODERATE";if(phi>=1)risk="ELEVATED";if(phi>=2)risk="HIGH";if(phi>=4)risk="CRITICAL";
      document.getElementById('output').innerHTML=\`{
  "dyad": "\${a} ↔ \${b}",
  "phi": \${phi.toFixed(4)},
  "jensen_shannon": \${js.toFixed(4)},
  "escalation_probability": \${prob.toFixed(3)},
  "risk_level": "<span class='risk-\${risk}'>\${risk}</span>"
}\`;
    }
    runPrediction();
  </script>
</body>
</html>`;

// Core math - pure JS implementation (WASM version is 100x faster for batch)
const EPSILON = 1e-10;

function normalize(dist) {
  const sum = dist.reduce((a, b) => a + b, 0);
  return dist.map(x => (x + EPSILON) / (sum + EPSILON * dist.length));
}

function klDivergence(p, q) {
  let kl = 0;
  for (let i = 0; i < p.length; i++) {
    const pi = Math.max(p[i], EPSILON);
    const qi = Math.max(q[i], EPSILON);
    kl += pi * Math.log(pi / qi);
  }
  return kl / Math.LN2; // Convert to bits
}

function symmetricKL(p, q) {
  return klDivergence(p, q) + klDivergence(q, p);
}

function jensenShannon(p, q) {
  const m = p.map((pi, i) => 0.5 * (pi + q[i]));
  return 0.5 * klDivergence(p, m) + 0.5 * klDivergence(q, m);
}

function hellingerDistance(p, q) {
  let sum = 0;
  for (let i = 0; i < p.length; i++) {
    const diff = Math.sqrt(p[i]) - Math.sqrt(q[i]);
    sum += diff * diff;
  }
  return Math.sqrt(0.5 * sum);
}

function riskLevel(phi) {
  if (phi < 0.5) return "LOW";
  if (phi < 1.0) return "MODERATE";
  if (phi < 2.0) return "ELEVATED";
  if (phi < 4.0) return "HIGH";
  return "CRITICAL";
}

function escalationProbability(phi, dPhiDt = 0, communication = 0.5) {
  const alpha = 0.5;  // Divergence weight
  const beta = 0.3;   // Communication dampening
  const gamma = 0.8;  // Rate sensitivity

  const logit = alpha * phi + gamma * Math.max(0, dPhiDt) - beta * communication;
  return 1 / (1 + Math.exp(-logit));
}

// API Handlers
async function handlePredict(request) {
  const body = await request.json();
  const { actor_a, actor_b, communication_level = 0.5 } = body;

  if (!actor_a || !actor_b) {
    return jsonResponse({ error: "Missing actor_a or actor_b" }, 400);
  }

  const schemeA = ACTORS[actor_a.toUpperCase()];
  const schemeB = ACTORS[actor_b.toUpperCase()];

  if (!schemeA) return jsonResponse({ error: `Unknown actor: ${actor_a}` }, 400);
  if (!schemeB) return jsonResponse({ error: `Unknown actor: ${actor_b}` }, 400);

  const p = normalize(schemeA.distribution);
  const q = normalize(schemeB.distribution);

  const phi = symmetricKL(p, q);
  const js = jensenShannon(p, q);
  const hellinger = hellingerDistance(p, q);
  const prob = escalationProbability(phi, 0, communication_level);
  const risk = riskLevel(phi);

  return jsonResponse({
    actor_a: { code: actor_a.toUpperCase(), name: schemeA.name },
    actor_b: { code: actor_b.toUpperCase(), name: schemeB.name },
    metrics: {
      phi: round(phi, 4),
      jensen_shannon: round(js, 4),
      hellinger: round(hellinger, 4),
      kl_a_b: round(klDivergence(p, q), 4),
      kl_b_a: round(klDivergence(q, p), 4),
    },
    prediction: {
      escalation_probability: round(prob, 3),
      risk_level: risk,
      communication_level: communication_level,
    },
    categories: CATEGORIES,
    timestamp: new Date().toISOString(),
  });
}

async function handleDivergence(request) {
  const body = await request.json();
  const { p, q } = body;

  if (!p || !q || !Array.isArray(p) || !Array.isArray(q)) {
    return jsonResponse({ error: "Missing or invalid p/q distributions" }, 400);
  }

  if (p.length !== q.length) {
    return jsonResponse({ error: "Distribution lengths must match" }, 400);
  }

  const pNorm = normalize(p);
  const qNorm = normalize(q);

  return jsonResponse({
    phi: round(symmetricKL(pNorm, qNorm), 6),
    jensen_shannon: round(jensenShannon(pNorm, qNorm), 6),
    hellinger: round(hellingerDistance(pNorm, qNorm), 6),
    kl_p_q: round(klDivergence(pNorm, qNorm), 6),
    kl_q_p: round(klDivergence(qNorm, pNorm), 6),
  });
}

function handleActors() {
  const actors = Object.entries(ACTORS).map(([code, data]) => ({
    code,
    name: data.name,
    entropy: round(entropy(normalize(data.distribution)), 3),
  }));
  return jsonResponse({ actors, categories: CATEGORIES });
}

function handleHealth() {
  return jsonResponse({ status: "ok", version: "1.0.0", engine: "divergence-engine" });
}

// Utilities
function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    },
  });
}

function round(n, decimals) {
  return Math.round(n * Math.pow(10, decimals)) / Math.pow(10, decimals);
}

function entropy(p) {
  return -p.reduce((sum, pi) => {
    if (pi > EPSILON) sum += pi * Math.log2(pi);
    return sum;
  }, 0);
}

// Router
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;

    // CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type",
        },
      });
    }

    try {
      if (path === "/predict" && request.method === "POST") {
        return await handlePredict(request);
      }
      if (path === "/divergence" && request.method === "POST") {
        return await handleDivergence(request);
      }
      if (path === "/actors" && request.method === "GET") {
        return handleActors();
      }
      if (path === "/health" && request.method === "GET") {
        return handleHealth();
      }
      if (path === "/" && request.method === "GET") {
        return new Response(LANDING_PAGE_HTML, {
          headers: { "Content-Type": "text/html; charset=utf-8" },
        });
      }

      return jsonResponse({ error: "Not found" }, 404);
    } catch (e) {
      return jsonResponse({ error: e.message }, 500);
    }
  },
};
