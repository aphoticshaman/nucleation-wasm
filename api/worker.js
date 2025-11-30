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
        return jsonResponse({
          name: "Divergence Engine API",
          version: "1.0.0",
          endpoints: {
            "POST /predict": "Predict escalation between two actors",
            "POST /divergence": "Compute divergence between custom distributions",
            "GET /actors": "List available actors",
            "GET /health": "Health check",
          },
          docs: "https://github.com/aphoticshaman/nucleation-wasm",
        });
      }

      return jsonResponse({ error: "Not found" }, 404);
    } catch (e) {
      return jsonResponse({ error: e.message }, 500);
    }
  },
};
