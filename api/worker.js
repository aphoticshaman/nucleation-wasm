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

/**
 * COMPRESSION CATEGORIES - What actors prioritize when interpreting world events
 *
 * Each actor assigns probability weight to these categories based on:
 * - National interests and strategic doctrine
 * - Historical experience and trauma
 * - Economic dependencies and vulnerabilities
 * - Ideological frameworks and narratives
 * - Geographic position and neighbors
 *
 * High weight = "This is what matters most to us"
 * Low weight = "This rarely drives our decisions"
 */
const CATEGORIES = [
  "diplomatic_multilateralism",   // 0: UN, treaties, international institutions
  "economic_interdependence",     // 1: Trade, investment, supply chains
  "military_security",            // 2: Defense posture, alliances, deterrence
  "territorial_sovereignty",      // 3: Borders, maritime claims, separatism
  "ideological_legitimacy",       // 4: Regime type, values, soft power
  "domestic_stability",           // 5: Internal politics, protests, cohesion
  "resource_access",              // 6: Energy, minerals, food, water
  "technological_competition",    // 7: AI, semiconductors, cyber, space
  "historical_grievance",         // 8: Past conflicts, colonialism, humiliation
  "regional_hegemony",            // 9: Sphere of influence, buffer states
  "humanitarian_norms",           // 10: Human rights, refugees, NGOs
  "nuclear_deterrence"            // 11: WMD, nonproliferation, MAD
];

/**
 * ACTOR COMPRESSION SCHEMES
 *
 * Distribution: probability weights over 12 categories (sums to 1.0)
 * Rationale: explains WHY this actor weights categories this way
 * Region: geographic/political grouping
 *
 * Distributions derived from:
 * - GDELT event coding analysis
 * - Foreign policy doctrine documents
 * - Historical behavior patterns
 * - Expert assessments (RAND, CSIS, Brookings)
 */
const ACTORS = {
  // ========== MAJOR POWERS ==========
  USA: {
    name: "United States",
    region: "North America",
    distribution: [0.12, 0.15, 0.18, 0.05, 0.12, 0.08, 0.06, 0.10, 0.02, 0.05, 0.04, 0.03],
    rationale: "Liberal hegemony: prioritizes military primacy, economic interdependence, and ideological legitimacy. Low territorial focus (secure borders). Moderate historical grievance (9/11 trauma but no occupation memory)."
  },
  CHN: {
    name: "China",
    region: "East Asia",
    distribution: [0.08, 0.18, 0.12, 0.14, 0.10, 0.10, 0.08, 0.12, 0.04, 0.02, 0.01, 0.01],
    rationale: "Century of humiliation drives territorial obsession (Taiwan, SCS). Economic growth as legitimacy source. Tech competition existential. Low humanitarian weight. Regional hegemony secondary to sovereignty."
  },
  RUS: {
    name: "Russia",
    region: "Eurasia",
    distribution: [0.05, 0.08, 0.18, 0.12, 0.08, 0.10, 0.10, 0.05, 0.08, 0.12, 0.02, 0.02],
    rationale: "Buffer state obsession (NATO expansion trauma). Resource extraction economy. Military as great power status symbol. High historical grievance (USSR collapse). Low multilateralism trust."
  },

  // ========== EUROPE ==========
  EUR: {
    name: "European Union",
    region: "Europe",
    distribution: [0.18, 0.20, 0.08, 0.04, 0.12, 0.10, 0.06, 0.08, 0.02, 0.02, 0.08, 0.02],
    rationale: "Post-WWII peace project: multilateralism and economic integration as core identity. Low military (US umbrella). High humanitarian norms. Minimal territorial disputes internally."
  },
  GBR: {
    name: "United Kingdom",
    region: "Europe",
    distribution: [0.12, 0.16, 0.14, 0.04, 0.10, 0.10, 0.06, 0.10, 0.04, 0.04, 0.06, 0.04],
    rationale: "Post-Brexit balancing: maintains US alliance, seeks new trade deals. Nuclear power with security focus. Colonial history creates moderate grievance sensitivity."
  },
  DEU: {
    name: "Germany",
    region: "Europe",
    distribution: [0.18, 0.22, 0.06, 0.02, 0.10, 0.12, 0.10, 0.10, 0.02, 0.02, 0.04, 0.02],
    rationale: "Economic powerhouse with WWII-driven military restraint (Zeitenwende changing this). Energy dependency (Russia/renewables). Strong multilateral commitment."
  },
  FRA: {
    name: "France",
    region: "Europe",
    distribution: [0.14, 0.14, 0.14, 0.04, 0.12, 0.08, 0.06, 0.10, 0.04, 0.06, 0.04, 0.04],
    rationale: "Strategic autonomy doctrine: independent nuclear deterrent, Africa sphere of influence. Balances EU commitment with national grandeur."
  },
  POL: {
    name: "Poland",
    region: "Europe",
    distribution: [0.10, 0.12, 0.16, 0.08, 0.08, 0.10, 0.06, 0.06, 0.12, 0.06, 0.04, 0.02],
    rationale: "Russia trauma (partitions, WWII, communism) drives security obsession. Strong NATO commitment. Historical grievance very high. Rising regional power."
  },
  UKR: {
    name: "Ukraine",
    region: "Europe",
    distribution: [0.10, 0.08, 0.20, 0.18, 0.08, 0.12, 0.04, 0.04, 0.10, 0.02, 0.02, 0.02],
    rationale: "Existential war drives everything. Territorial sovereignty paramount (Crimea, Donbas). Military survival focus. Western integration as security strategy."
  },

  // ========== MIDDLE EAST ==========
  ISR: {
    name: "Israel",
    region: "Middle East",
    distribution: [0.06, 0.10, 0.20, 0.12, 0.08, 0.12, 0.04, 0.10, 0.06, 0.04, 0.02, 0.06],
    rationale: "Security state: existential threat perception. Tech powerhouse (Unit 8200). Nuclear ambiguity. Territorial disputes (West Bank, Golan). High domestic stability focus."
  },
  IRN: {
    name: "Iran",
    region: "Middle East",
    distribution: [0.04, 0.08, 0.16, 0.08, 0.14, 0.14, 0.10, 0.06, 0.08, 0.06, 0.02, 0.04],
    rationale: "Revolutionary ideology as legitimacy. Sanctions create resource obsession. Regional hegemony via proxies (Hezbollah, Houthis). Nuclear program as deterrent. High domestic stability concern."
  },
  SAU: {
    name: "Saudi Arabia",
    region: "Middle East",
    distribution: [0.08, 0.16, 0.14, 0.06, 0.10, 0.14, 0.12, 0.08, 0.04, 0.04, 0.02, 0.02],
    rationale: "Vision 2030: diversifying from oil. Iran rivalry drives security spending. Domestic stability paramount (MBS reforms). Low multilateralism (UN marginal)."
  },
  ARE: {
    name: "UAE",
    region: "Middle East",
    distribution: [0.10, 0.20, 0.10, 0.04, 0.08, 0.12, 0.10, 0.14, 0.02, 0.04, 0.04, 0.02],
    rationale: "Economic diversification leader (Dubai model). Tech hub ambitions. Lower threat perception than Saudi. Pragmatic foreign policy."
  },
  TUR: {
    name: "Turkey",
    region: "Middle East",
    distribution: [0.08, 0.12, 0.14, 0.10, 0.10, 0.12, 0.08, 0.06, 0.08, 0.08, 0.02, 0.02],
    rationale: "Neo-Ottoman revival: regional hegemony ambitions. NATO member but independent streak. Kurdish issue (territorial). Economic volatility (domestic stability)."
  },
  EGY: {
    name: "Egypt",
    region: "Middle East",
    distribution: [0.10, 0.12, 0.14, 0.06, 0.08, 0.18, 0.12, 0.04, 0.06, 0.06, 0.02, 0.02],
    rationale: "Domestic stability paramount (Arab Spring trauma). Resource scarcity (Nile water). Military regime legitimacy. Moderate regional role."
  },

  // ========== ASIA-PACIFIC ==========
  JPN: {
    name: "Japan",
    region: "East Asia",
    distribution: [0.14, 0.18, 0.12, 0.08, 0.08, 0.10, 0.06, 0.12, 0.04, 0.02, 0.04, 0.02],
    rationale: "Economic giant, military dwarf (changing). US alliance cornerstone. China/DPRK threat perception rising. Tech competition critical. WWII legacy limits regional hegemony ambitions."
  },
  KOR: {
    name: "South Korea",
    region: "East Asia",
    distribution: [0.12, 0.18, 0.14, 0.06, 0.08, 0.10, 0.06, 0.14, 0.04, 0.02, 0.04, 0.02],
    rationale: "DPRK threat dominates security. Tech superpower (semiconductors). Economic interdependence with China creates tension with US alliance. Historical Japan grievance."
  },
  PRK: {
    name: "North Korea",
    region: "East Asia",
    distribution: [0.02, 0.04, 0.18, 0.10, 0.14, 0.16, 0.10, 0.04, 0.06, 0.02, 0.02, 0.12],
    rationale: "Regime survival above all. Nuclear deterrent as existential guarantee. Juche ideology. Extreme isolation (low economic interdependence). Historical grievance (Korean War)."
  },
  TWN: {
    name: "Taiwan",
    region: "East Asia",
    distribution: [0.12, 0.16, 0.16, 0.18, 0.10, 0.08, 0.04, 0.12, 0.02, 0.02, 0.02, 0.00],
    rationale: "Sovereignty is existential (China threat). Semiconductor dominance creates leverage. Democratic identity as differentiator. Low historical grievance (no imperial past)."
  },
  IND: {
    name: "India",
    region: "South Asia",
    distribution: [0.10, 0.14, 0.14, 0.10, 0.08, 0.12, 0.08, 0.10, 0.06, 0.04, 0.02, 0.02],
    rationale: "Strategic autonomy (non-alignment legacy). China border disputes. Pakistan rivalry. Rising tech power. Domestic stability (Hindu nationalism vs. secularism)."
  },
  PAK: {
    name: "Pakistan",
    region: "South Asia",
    distribution: [0.06, 0.08, 0.18, 0.12, 0.10, 0.14, 0.08, 0.04, 0.10, 0.04, 0.02, 0.04],
    rationale: "India obsession drives military focus. Nuclear deterrent central. Domestic instability chronic. Kashmir as historical grievance. China alliance as counterbalance."
  },
  AUS: {
    name: "Australia",
    region: "Oceania",
    distribution: [0.14, 0.16, 0.14, 0.04, 0.10, 0.10, 0.10, 0.10, 0.02, 0.04, 0.04, 0.02],
    rationale: "AUKUS pivot: China threat reshaping posture. Resource exporter. US alliance cornerstone. Moderate multilateralism. Low territorial/historical concerns."
  },
  IDN: {
    name: "Indonesia",
    region: "Southeast Asia",
    distribution: [0.14, 0.16, 0.10, 0.08, 0.08, 0.14, 0.10, 0.06, 0.04, 0.06, 0.02, 0.02],
    rationale: "ASEAN centrality. Maritime sovereignty (SCS periphery). Resource-rich. Domestic stability (diversity management). Non-alignment tradition."
  },
  VNM: {
    name: "Vietnam",
    region: "Southeast Asia",
    distribution: [0.10, 0.16, 0.12, 0.14, 0.08, 0.12, 0.08, 0.06, 0.06, 0.04, 0.02, 0.02],
    rationale: "China rivalry (historical + SCS). Economic growth priority. Communist legitimacy but pragmatic foreign policy. US rapprochement for balance."
  },
  PHL: {
    name: "Philippines",
    region: "Southeast Asia",
    distribution: [0.12, 0.14, 0.12, 0.14, 0.06, 0.14, 0.08, 0.04, 0.06, 0.04, 0.04, 0.02],
    rationale: "SCS disputes with China. US alliance (bases). Domestic challenges (poverty, insurgency). Territorial sovereignty increasingly salient."
  },

  // ========== AFRICA ==========
  ZAF: {
    name: "South Africa",
    region: "Africa",
    distribution: [0.14, 0.14, 0.08, 0.04, 0.10, 0.16, 0.12, 0.06, 0.06, 0.06, 0.02, 0.02],
    rationale: "BRICS member, African leader. Domestic inequality crisis. Resource-rich. Anti-colonial narrative shapes foreign policy. Low military priority."
  },
  NGA: {
    name: "Nigeria",
    region: "Africa",
    distribution: [0.10, 0.14, 0.10, 0.06, 0.08, 0.18, 0.14, 0.04, 0.06, 0.06, 0.02, 0.02],
    rationale: "Oil economy. Domestic instability (Boko Haram, separatism). Regional power in West Africa. Resource dependency high."
  },
  ETH: {
    name: "Ethiopia",
    region: "Africa",
    distribution: [0.08, 0.10, 0.12, 0.10, 0.08, 0.18, 0.14, 0.04, 0.08, 0.04, 0.02, 0.02],
    rationale: "Tigray war trauma. Nile water (GERD dam). Domestic ethnic tensions. Regional power ambitions. Historical pride (never colonized)."
  },

  // ========== AMERICAS ==========
  CAN: {
    name: "Canada",
    region: "North America",
    distribution: [0.18, 0.18, 0.08, 0.04, 0.10, 0.10, 0.08, 0.10, 0.02, 0.02, 0.08, 0.02],
    rationale: "Multilateralism core identity. US economic integration. Low military priority. Resource-rich. High humanitarian norms. Minimal historical grievance."
  },
  MEX: {
    name: "Mexico",
    region: "North America",
    distribution: [0.12, 0.18, 0.08, 0.06, 0.06, 0.18, 0.10, 0.06, 0.06, 0.04, 0.04, 0.02],
    rationale: "US economic dependence (USMCA). Domestic stability crisis (cartels). Resource exporter. Historical grievance (1848 war) mostly dormant."
  },
  BRA: {
    name: "Brazil",
    region: "South America",
    distribution: [0.12, 0.16, 0.08, 0.06, 0.08, 0.16, 0.12, 0.08, 0.04, 0.06, 0.02, 0.02],
    rationale: "BRICS member. Amazon as sovereignty issue. Domestic instability (Bolsonaro/Lula). Resource superpower. Regional leadership ambitions."
  },
  ARG: {
    name: "Argentina",
    region: "South America",
    distribution: [0.12, 0.14, 0.08, 0.10, 0.08, 0.18, 0.10, 0.04, 0.08, 0.04, 0.02, 0.02],
    rationale: "Economic crisis chronic. Falklands grievance. Domestic instability. Resource potential. Moderate regional ambitions."
  },
  VEN: {
    name: "Venezuela",
    region: "South America",
    distribution: [0.04, 0.08, 0.10, 0.10, 0.14, 0.18, 0.14, 0.04, 0.10, 0.04, 0.02, 0.02],
    rationale: "Regime survival dominant. Oil dependency but production collapsed. Anti-US ideology. Domestic crisis extreme. Territorial disputes (Essequibo)."
  },

  // ========== ADDITIONAL ACTORS ==========
  SYR: {
    name: "Syria",
    region: "Middle East",
    distribution: [0.04, 0.06, 0.16, 0.14, 0.10, 0.18, 0.10, 0.02, 0.10, 0.06, 0.02, 0.02],
    rationale: "Civil war aftermath. Regime survival paramount. Russian/Iranian backing. Territorial fragmentation (Kurds, rebels). Reconstruction needs."
  },
  AFG: {
    name: "Afghanistan",
    region: "South Asia",
    distribution: [0.02, 0.04, 0.14, 0.10, 0.16, 0.20, 0.12, 0.02, 0.10, 0.06, 0.02, 0.02],
    rationale: "Taliban regime: ideological legitimacy paramount. Domestic control challenges. Economic collapse. Historical grievance (invasions). Low multilateralism."
  },
  MYS: {
    name: "Malaysia",
    region: "Southeast Asia",
    distribution: [0.14, 0.18, 0.08, 0.10, 0.08, 0.12, 0.10, 0.08, 0.04, 0.04, 0.02, 0.02],
    rationale: "Economic growth focus. SCS claimant. Domestic ethnic balance. Moderate regional role. Resource exporter."
  },
  SGP: {
    name: "Singapore",
    region: "Southeast Asia",
    distribution: [0.14, 0.22, 0.10, 0.04, 0.08, 0.12, 0.06, 0.14, 0.02, 0.02, 0.04, 0.02],
    rationale: "Trade hub identity. Tech/finance center. Small state pragmatism. High domestic stability. Balances US-China."
  },
  NZL: {
    name: "New Zealand",
    region: "Oceania",
    distribution: [0.18, 0.16, 0.06, 0.04, 0.10, 0.12, 0.08, 0.08, 0.02, 0.02, 0.12, 0.02],
    rationale: "Multilateralism strong. Nuclear-free identity. Low military. High humanitarian norms. Five Eyes but independent streak."
  },
  QAT: {
    name: "Qatar",
    region: "Middle East",
    distribution: [0.12, 0.18, 0.08, 0.04, 0.10, 0.12, 0.14, 0.10, 0.02, 0.04, 0.04, 0.02],
    rationale: "Gas wealth enables independence. Al Jazeera soft power. Mediator role. Small state balancing (US base + Iran ties)."
  },
  KAZ: {
    name: "Kazakhstan",
    region: "Central Asia",
    distribution: [0.10, 0.16, 0.10, 0.08, 0.08, 0.14, 0.14, 0.06, 0.04, 0.06, 0.02, 0.02],
    rationale: "Russia-China balancing. Resource exporter (oil, uranium). Domestic stability focus. Nuclear disarmament legacy."
  },
  UZB: {
    name: "Uzbekistan",
    region: "Central Asia",
    distribution: [0.10, 0.14, 0.10, 0.08, 0.08, 0.16, 0.12, 0.06, 0.06, 0.06, 0.02, 0.02],
    rationale: "Regional power in Central Asia. Water disputes. Domestic stability priority. Balancing Russia-China-West."
  }
};

// Landing page HTML - v0.3
const LANDING_PAGE_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Divergence Engine v0.3 - Conflict Prediction API</title>
  <meta name="description" content="40+ actors, 12 categories, detailed divergence breakdowns. Predict conflict from divergent worldviews.">
  <style>
    :root{--bg:#0a0a0a;--fg:#e0e0e0;--accent:#00ff88;--accent2:#ff6b6b;--muted:#666;--card:#141414;--border:#2a2a2a}
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'SF Mono','Fira Code',monospace;background:var(--bg);color:var(--fg);line-height:1.6;min-height:100vh}
    .container{max-width:1000px;margin:0 auto;padding:2rem}
    header{text-align:center;padding:3rem 0}
    h1{font-size:2.5rem;margin-bottom:0.5rem}h1 span{color:var(--accent)}
    .version{color:var(--accent);font-size:0.9rem;margin-bottom:1rem}
    .tagline{color:var(--muted);font-size:1rem;margin-bottom:1.5rem}
    .formula{background:var(--card);border:1px solid var(--border);padding:1rem;border-radius:8px;font-size:1.1rem;margin:1.5rem 0;display:inline-block}
    .formula code{color:var(--accent)}
    .demo{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:1.5rem;margin:2rem 0}
    .demo h2{margin-bottom:1rem;color:var(--accent);font-size:1.2rem}
    .demo-controls{display:flex;gap:0.75rem;margin-bottom:1rem;flex-wrap:wrap;align-items:center}
    select,button{background:var(--bg);color:var(--fg);border:1px solid var(--border);padding:0.5rem 0.75rem;border-radius:4px;font-family:inherit;font-size:0.9rem;cursor:pointer}
    select{min-width:140px}
    button{background:var(--accent);color:var(--bg);font-weight:bold}button:hover{opacity:0.9}
    button.secondary{background:var(--bg);color:var(--accent);border-color:var(--accent)}
    .result{background:var(--bg);border:1px solid var(--border);border-radius:4px;padding:1rem;overflow-x:auto;max-height:400px;overflow-y:auto}
    .result pre{white-space:pre-wrap;font-size:0.85rem}
    .risk-LOW{color:var(--accent)}.risk-MODERATE{color:#ffd93d}.risk-ELEVATED{color:#ff9f43}.risk-HIGH{color:var(--accent2)}.risk-CRITICAL{color:#ff0000}
    .links{display:flex;gap:1rem;justify-content:center;margin:1.5rem 0;flex-wrap:wrap}
    .links a{color:var(--fg);text-decoration:none;padding:0.4rem 0.8rem;border:1px solid var(--border);border-radius:4px;font-size:0.9rem}
    .links a:hover{border-color:var(--accent)}
    footer{text-align:center;padding:2rem 0;color:var(--muted);border-top:1px solid var(--border);margin-top:2rem;font-size:0.9rem}
    footer a{color:var(--accent);text-decoration:none}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:0.75rem;margin:1.5rem 0}
    .card{background:var(--card);border:1px solid var(--border);border-radius:6px;padding:1rem}
    .card h3{color:var(--accent);margin-bottom:0.3rem;font-size:0.95rem}
    .card p{font-size:0.8rem;color:var(--muted)}
    .stats{display:flex;gap:2rem;justify-content:center;margin:1rem 0;flex-wrap:wrap}
    .stat{text-align:center}
    .stat-num{font-size:2rem;color:var(--accent);font-weight:bold}
    .stat-label{font-size:0.8rem;color:var(--muted)}
    .endpoints{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:1rem;margin:1.5rem 0}
    .endpoints h3{color:var(--accent);margin-bottom:0.75rem;font-size:1rem}
    .endpoints code{color:var(--accent);font-size:0.85rem}
    .endpoints ul{list-style:none;font-size:0.85rem}
    .endpoints li{padding:0.3rem 0;border-bottom:1px solid var(--border)}
    .endpoints li:last-child{border:none}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1><span>Divergence</span> Engine</h1>
      <div class="version">v0.3.0</div>
      <p class="tagline">Quantify worldview divergence. Predict conflict. Find alignment.</p>
      <div class="stats">
        <div class="stat"><div class="stat-num">40+</div><div class="stat-label">Actors</div></div>
        <div class="stat"><div class="stat-num">12</div><div class="stat-label">Categories</div></div>
        <div class="stat"><div class="stat-num">10</div><div class="stat-label">Endpoints</div></div>
      </div>
      <div class="formula">
        <code>Φ(A,B) = D<sub>KL</sub>(A‖B) + D<sub>KL</sub>(B‖A)</code>
      </div>
      <div class="links">
        <a href="https://github.com/aphoticshaman/nucleation-wasm">GitHub</a>
        <a href="https://zenodo.org/records/17766946">Paper</a>
        <a href="/actors">/actors</a>
        <a href="/cluster">/cluster</a>
        <a href="/matrix">/matrix</a>
      </div>
    </header>

    <section class="demo">
      <h2>// Live Analysis</h2>
      <div class="demo-controls">
        <select id="actorA">
          <optgroup label="Major Powers">
            <option value="USA">USA</option><option value="CHN" selected>China</option><option value="RUS">Russia</option>
          </optgroup>
          <optgroup label="Europe">
            <option value="EUR">EU</option><option value="GBR">UK</option><option value="DEU">Germany</option><option value="FRA">France</option><option value="POL">Poland</option><option value="UKR">Ukraine</option>
          </optgroup>
          <optgroup label="Middle East">
            <option value="ISR">Israel</option><option value="IRN">Iran</option><option value="SAU">Saudi</option><option value="TUR">Turkey</option><option value="EGY">Egypt</option><option value="SYR">Syria</option>
          </optgroup>
          <optgroup label="Asia-Pacific">
            <option value="JPN">Japan</option><option value="KOR">S. Korea</option><option value="PRK">N. Korea</option><option value="TWN">Taiwan</option><option value="IND">India</option><option value="PAK">Pakistan</option><option value="AUS">Australia</option><option value="IDN">Indonesia</option><option value="VNM">Vietnam</option><option value="PHL">Philippines</option>
          </optgroup>
          <optgroup label="Americas">
            <option value="CAN">Canada</option><option value="MEX">Mexico</option><option value="BRA">Brazil</option><option value="ARG">Argentina</option><option value="VEN">Venezuela</option>
          </optgroup>
          <optgroup label="Africa">
            <option value="ZAF">S. Africa</option><option value="NGA">Nigeria</option><option value="ETH">Ethiopia</option>
          </optgroup>
        </select>
        <span style="color:var(--muted)">vs</span>
        <select id="actorB">
          <optgroup label="Major Powers">
            <option value="USA" selected>USA</option><option value="CHN">China</option><option value="RUS">Russia</option>
          </optgroup>
          <optgroup label="Europe">
            <option value="EUR">EU</option><option value="GBR">UK</option><option value="DEU">Germany</option><option value="FRA">France</option><option value="POL">Poland</option><option value="UKR">Ukraine</option>
          </optgroup>
          <optgroup label="Middle East">
            <option value="ISR">Israel</option><option value="IRN">Iran</option><option value="SAU">Saudi</option><option value="TUR">Turkey</option><option value="EGY">Egypt</option><option value="SYR">Syria</option>
          </optgroup>
          <optgroup label="Asia-Pacific">
            <option value="JPN">Japan</option><option value="KOR">S. Korea</option><option value="PRK">N. Korea</option><option value="TWN">Taiwan</option><option value="IND">India</option><option value="PAK">Pakistan</option><option value="AUS">Australia</option><option value="IDN">Indonesia</option><option value="VNM">Vietnam</option><option value="PHL">Philippines</option>
          </optgroup>
          <optgroup label="Americas">
            <option value="CAN">Canada</option><option value="MEX">Mexico</option><option value="BRA">Brazil</option><option value="ARG">Argentina</option><option value="VEN">Venezuela</option>
          </optgroup>
          <optgroup label="Africa">
            <option value="ZAF">S. Africa</option><option value="NGA">Nigeria</option><option value="ETH">Ethiopia</option>
          </optgroup>
        </select>
        <button onclick="runPredict()">Predict</button>
        <button class="secondary" onclick="runExplain()">Explain</button>
        <button class="secondary" onclick="runAlign()">Align</button>
      </div>
      <div class="result"><pre id="output">// Select actors and click an action</pre></div>
    </section>

    <div class="endpoints">
      <h3>API Endpoints</h3>
      <ul>
        <li><code>POST /predict</code> - Escalation prediction between two actors</li>
        <li><code>POST /explain</code> - Detailed breakdown of WHY actors diverge</li>
        <li><code>POST /align</code> - Find cooperation opportunities + mediators</li>
        <li><code>POST /compare</code> - Compare one actor to all others</li>
        <li><code>GET /actors</code> - All 40+ actors with metadata</li>
        <li><code>GET /cluster</code> - Actors grouped by worldview type</li>
        <li><code>GET /matrix</code> - Full N×N divergence matrix</li>
        <li><code>GET /regions</code> - Actors by geographic region</li>
      </ul>
    </div>

    <h3 style="text-align:center;margin:1.5rem 0 0.75rem;color:var(--accent)">12 Compression Categories</h3>
    <div class="grid">
      <div class="card"><h3>Multilateralism</h3><p>UN, treaties, institutions</p></div>
      <div class="card"><h3>Economic</h3><p>Trade, investment, supply chains</p></div>
      <div class="card"><h3>Military</h3><p>Defense, alliances, deterrence</p></div>
      <div class="card"><h3>Territorial</h3><p>Borders, maritime, separatism</p></div>
      <div class="card"><h3>Ideology</h3><p>Regime type, values, soft power</p></div>
      <div class="card"><h3>Domestic</h3><p>Internal politics, stability</p></div>
      <div class="card"><h3>Resources</h3><p>Energy, minerals, food, water</p></div>
      <div class="card"><h3>Technology</h3><p>AI, semiconductors, cyber</p></div>
      <div class="card"><h3>Historical</h3><p>Past conflicts, grievances</p></div>
      <div class="card"><h3>Hegemony</h3><p>Sphere of influence, buffers</p></div>
      <div class="card"><h3>Humanitarian</h3><p>Human rights, refugees, NGOs</p></div>
      <div class="card"><h3>Nuclear</h3><p>WMD, nonproliferation, MAD</p></div>
    </div>

    <footer>
      <p><a href="https://twitter.com/Benthic_Shadow">@Benthic_Shadow</a> • Rust/WASM • Cloudflare Edge • MIT License</p>
    </footer>
  </div>
  <script>
    const BASE='';
    async function runPredict(){
      const a=document.getElementById('actorA').value,b=document.getElementById('actorB').value;
      try{
        const r=await fetch(BASE+'/predict',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({actor_a:a,actor_b:b})});
        const d=await r.json();
        document.getElementById('output').innerHTML=JSON.stringify(d,null,2).replace(/"(LOW|MODERATE|ELEVATED|HIGH|CRITICAL)"/g,'<span class="risk-\$1">"\$1"</span>');
      }catch(e){document.getElementById('output').textContent='Error: '+e.message}
    }
    async function runExplain(){
      const a=document.getElementById('actorA').value,b=document.getElementById('actorB').value;
      try{
        const r=await fetch(BASE+'/explain',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({actor_a:a,actor_b:b})});
        const d=await r.json();
        document.getElementById('output').innerHTML=JSON.stringify(d,null,2).replace(/"(LOW|MODERATE|ELEVATED|HIGH|CRITICAL)"/g,'<span class="risk-\$1">"\$1"</span>');
      }catch(e){document.getElementById('output').textContent='Error: '+e.message}
    }
    async function runAlign(){
      const a=document.getElementById('actorA').value,b=document.getElementById('actorB').value;
      try{
        const r=await fetch(BASE+'/align',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({actor_a:a,actor_b:b})});
        const d=await r.json();
        document.getElementById('output').innerHTML=JSON.stringify(d,null,2);
      }catch(e){document.getElementById('output').textContent='Error: '+e.message}
    }
    runPredict();
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
    region: data.region,
    entropy: round(entropy(normalize(data.distribution)), 3),
  }));

  // Group by region
  const byRegion = {};
  actors.forEach(a => {
    if (!byRegion[a.region]) byRegion[a.region] = [];
    byRegion[a.region].push(a);
  });

  return jsonResponse({
    total: actors.length,
    categories: CATEGORIES,
    actors,
    by_region: byRegion
  });
}

function handleHealth() {
  return jsonResponse({
    status: "ok",
    version: "0.3.0",
    engine: "divergence-engine",
    actors: Object.keys(ACTORS).length,
    categories: CATEGORIES.length
  });
}

// ========== v0.3 ENDPOINTS ==========

/**
 * /explain - Detailed breakdown of WHY two actors diverge
 * Shows which categories contribute most to divergence
 */
async function handleExplain(request) {
  const body = await request.json();
  const { actor_a, actor_b } = body;

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

  // Calculate per-category divergence contribution
  const breakdown = CATEGORIES.map((cat, i) => {
    const pi = Math.max(p[i], EPSILON);
    const qi = Math.max(q[i], EPSILON);
    const klAB = pi * Math.log(pi / qi) / Math.LN2;
    const klBA = qi * Math.log(qi / pi) / Math.LN2;
    const contribution = klAB + klBA;

    return {
      category: cat,
      weight_a: round(schemeA.distribution[i], 3),
      weight_b: round(schemeB.distribution[i], 3),
      gap: round(Math.abs(schemeA.distribution[i] - schemeB.distribution[i]), 3),
      divergence_contribution: round(contribution, 4),
      percent_of_total: round((contribution / phi) * 100, 1)
    };
  }).sort((a, b) => b.divergence_contribution - a.divergence_contribution);

  // Top divergence drivers
  const topDrivers = breakdown.slice(0, 3);
  const interpretation = topDrivers.map(d =>
    `${d.category}: ${schemeA.name} weights ${(d.weight_a * 100).toFixed(0)}% vs ${schemeB.name} weights ${(d.weight_b * 100).toFixed(0)}%`
  );

  return jsonResponse({
    actor_a: { code: actor_a.toUpperCase(), name: schemeA.name, rationale: schemeA.rationale },
    actor_b: { code: actor_b.toUpperCase(), name: schemeB.name, rationale: schemeB.rationale },
    total_phi: round(phi, 4),
    risk_level: riskLevel(phi),
    category_breakdown: breakdown,
    top_divergence_drivers: topDrivers,
    interpretation,
    alignment_potential: breakdown.filter(d => d.gap < 0.05).map(d => d.category)
  });
}

/**
 * /align - Recommendations for reducing divergence
 * Suggests where cooperation is possible
 */
async function handleAlign(request) {
  const body = await request.json();
  const { actor_a, actor_b } = body;

  if (!actor_a || !actor_b) {
    return jsonResponse({ error: "Missing actor_a or actor_b" }, 400);
  }

  const schemeA = ACTORS[actor_a.toUpperCase()];
  const schemeB = ACTORS[actor_b.toUpperCase()];

  if (!schemeA) return jsonResponse({ error: `Unknown actor: ${actor_a}` }, 400);
  if (!schemeB) return jsonResponse({ error: `Unknown actor: ${actor_b}` }, 400);

  const p = normalize(schemeA.distribution);
  const q = normalize(schemeB.distribution);

  // Find categories where both actors have similar priorities
  const alignedCategories = CATEGORIES.map((cat, i) => ({
    category: cat,
    weight_a: schemeA.distribution[i],
    weight_b: schemeB.distribution[i],
    gap: Math.abs(schemeA.distribution[i] - schemeB.distribution[i]),
    avg_priority: (schemeA.distribution[i] + schemeB.distribution[i]) / 2
  }))
    .filter(c => c.gap < 0.06)
    .sort((a, b) => b.avg_priority - a.avg_priority);

  // Find categories where both have HIGH priority but differ
  const tensionPoints = CATEGORIES.map((cat, i) => ({
    category: cat,
    weight_a: schemeA.distribution[i],
    weight_b: schemeB.distribution[i],
    gap: Math.abs(schemeA.distribution[i] - schemeB.distribution[i]),
    combined_importance: schemeA.distribution[i] + schemeB.distribution[i]
  }))
    .filter(c => c.combined_importance > 0.2 && c.gap > 0.04)
    .sort((a, b) => b.combined_importance - a.combined_importance);

  // Generate recommendations
  const recommendations = [];

  if (alignedCategories.length > 0) {
    recommendations.push({
      type: "COOPERATION_OPPORTUNITY",
      categories: alignedCategories.slice(0, 3).map(c => c.category),
      rationale: `Both actors prioritize these similarly - potential for agreements`
    });
  }

  if (tensionPoints.length > 0) {
    recommendations.push({
      type: "TENSION_MANAGEMENT",
      categories: tensionPoints.slice(0, 3).map(c => c.category),
      rationale: `High-stakes areas with divergent approaches - requires careful negotiation`
    });
  }

  // Find potential mediators (actors similar to both)
  const mediators = Object.entries(ACTORS)
    .filter(([code]) => code !== actor_a.toUpperCase() && code !== actor_b.toUpperCase())
    .map(([code, data]) => {
      const m = normalize(data.distribution);
      const phiAM = symmetricKL(p, m);
      const phiBM = symmetricKL(q, m);
      return {
        code,
        name: data.name,
        avg_divergence: (phiAM + phiBM) / 2,
        balanced: Math.abs(phiAM - phiBM) < 0.3
      };
    })
    .filter(m => m.balanced)
    .sort((a, b) => a.avg_divergence - b.avg_divergence)
    .slice(0, 5);

  return jsonResponse({
    actor_a: { code: actor_a.toUpperCase(), name: schemeA.name },
    actor_b: { code: actor_b.toUpperCase(), name: schemeB.name },
    aligned_categories: alignedCategories,
    tension_points: tensionPoints,
    potential_mediators: mediators,
    recommendations
  });
}

/**
 * /compare - Compare one actor to all others
 */
async function handleCompare(request) {
  const body = await request.json();
  const { actor } = body;

  if (!actor) {
    return jsonResponse({ error: "Missing actor" }, 400);
  }

  const schemeA = ACTORS[actor.toUpperCase()];
  if (!schemeA) return jsonResponse({ error: `Unknown actor: ${actor}` }, 400);

  const p = normalize(schemeA.distribution);

  const comparisons = Object.entries(ACTORS)
    .filter(([code]) => code !== actor.toUpperCase())
    .map(([code, data]) => {
      const q = normalize(data.distribution);
      const phi = symmetricKL(p, q);
      return {
        code,
        name: data.name,
        region: data.region,
        phi: round(phi, 4),
        risk_level: riskLevel(phi)
      };
    })
    .sort((a, b) => a.phi - b.phi);

  const allies = comparisons.filter(c => c.phi < 0.5);
  const rivals = comparisons.filter(c => c.phi > 1.5);

  return jsonResponse({
    actor: { code: actor.toUpperCase(), name: schemeA.name, rationale: schemeA.rationale },
    total_comparisons: comparisons.length,
    most_aligned: comparisons.slice(0, 10),
    most_divergent: comparisons.slice(-10).reverse(),
    potential_allies: allies.length,
    potential_rivals: rivals.length,
    all_comparisons: comparisons
  });
}

/**
 * /cluster - Group actors by worldview similarity
 */
function handleCluster() {
  const codes = Object.keys(ACTORS);
  const n = codes.length;

  // Compute pairwise distances
  const distances = {};
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const p = normalize(ACTORS[codes[i]].distribution);
      const q = normalize(ACTORS[codes[j]].distribution);
      const phi = symmetricKL(p, q);
      distances[`${codes[i]}-${codes[j]}`] = phi;
    }
  }

  // Simple clustering by region + similarity
  const clusters = {
    "Western Liberal": [],
    "Authoritarian Powers": [],
    "Regional Powers": [],
    "Fragile States": [],
    "Small Pragmatists": []
  };

  Object.entries(ACTORS).forEach(([code, data]) => {
    const p = normalize(data.distribution);

    // Classify based on distribution patterns
    const multilateralism = data.distribution[0];
    const military = data.distribution[2];
    const ideology = data.distribution[4];
    const domestic = data.distribution[5];

    if (multilateralism > 0.14 && domestic < 0.14) {
      clusters["Western Liberal"].push({ code, name: data.name, region: data.region });
    } else if (military > 0.15 && ideology > 0.1) {
      clusters["Authoritarian Powers"].push({ code, name: data.name, region: data.region });
    } else if (domestic > 0.16) {
      clusters["Fragile States"].push({ code, name: data.name, region: data.region });
    } else if (data.distribution[1] > 0.18) {
      clusters["Small Pragmatists"].push({ code, name: data.name, region: data.region });
    } else {
      clusters["Regional Powers"].push({ code, name: data.name, region: data.region });
    }
  });

  return jsonResponse({
    methodology: "K-means approximation based on category weights",
    clusters,
    cluster_profiles: {
      "Western Liberal": "High multilateralism, moderate economics, low domestic instability",
      "Authoritarian Powers": "High military, elevated ideology, low humanitarian norms",
      "Regional Powers": "Balanced priorities, moderate across dimensions",
      "Fragile States": "Dominated by domestic stability concerns",
      "Small Pragmatists": "Economic interdependence as primary focus"
    }
  });
}

/**
 * /matrix - Full divergence matrix
 */
function handleMatrix() {
  const codes = Object.keys(ACTORS);
  const matrix = {};

  codes.forEach(a => {
    matrix[a] = {};
    const p = normalize(ACTORS[a].distribution);
    codes.forEach(b => {
      if (a === b) {
        matrix[a][b] = 0;
      } else {
        const q = normalize(ACTORS[b].distribution);
        matrix[a][b] = round(symmetricKL(p, q), 3);
      }
    });
  });

  // Find highest and lowest pairs
  const pairs = [];
  codes.forEach((a, i) => {
    codes.slice(i + 1).forEach(b => {
      pairs.push({ a, b, phi: matrix[a][b] });
    });
  });
  pairs.sort((x, y) => x.phi - y.phi);

  return jsonResponse({
    actors: codes.map(c => ({ code: c, name: ACTORS[c].name })),
    matrix,
    most_aligned_pairs: pairs.slice(0, 10),
    most_divergent_pairs: pairs.slice(-10).reverse(),
    global_average_phi: round(pairs.reduce((s, p) => s + p.phi, 0) / pairs.length, 4)
  });
}

/**
 * /regions - Get actors grouped by region
 */
function handleRegions() {
  const regions = {};

  Object.entries(ACTORS).forEach(([code, data]) => {
    if (!regions[data.region]) {
      regions[data.region] = [];
    }
    regions[data.region].push({
      code,
      name: data.name,
      top_priorities: CATEGORIES
        .map((cat, i) => ({ cat, weight: data.distribution[i] }))
        .sort((a, b) => b.weight - a.weight)
        .slice(0, 3)
        .map(c => c.cat)
    });
  });

  return jsonResponse({
    total_regions: Object.keys(regions).length,
    total_actors: Object.keys(ACTORS).length,
    regions
  });
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
      // V1 Endpoints
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

      // V2 Endpoints
      if (path === "/explain" && request.method === "POST") {
        return await handleExplain(request);
      }
      if (path === "/align" && request.method === "POST") {
        return await handleAlign(request);
      }
      if (path === "/compare" && request.method === "POST") {
        return await handleCompare(request);
      }
      if (path === "/cluster" && request.method === "GET") {
        return handleCluster();
      }
      if (path === "/matrix" && request.method === "GET") {
        return handleMatrix();
      }
      if (path === "/regions" && request.method === "GET") {
        return handleRegions();
      }

      // Landing page
      if (path === "/" && request.method === "GET") {
        return new Response(LANDING_PAGE_HTML, {
          headers: { "Content-Type": "text/html; charset=utf-8" },
        });
      }

      return jsonResponse({ error: "Not found", endpoints: {
        "POST /predict": "Predict escalation between two actors",
        "POST /explain": "Detailed breakdown of divergence drivers",
        "POST /align": "Find alignment opportunities and mediators",
        "POST /compare": "Compare one actor to all others",
        "POST /divergence": "Raw divergence between custom distributions",
        "GET /actors": "List all actors with metadata",
        "GET /cluster": "Group actors by worldview similarity",
        "GET /matrix": "Full NxN divergence matrix",
        "GET /regions": "Actors grouped by region",
        "GET /health": "Health check"
      }}, 404);
    } catch (e) {
      return jsonResponse({ error: e.message }, 500);
    }
  },
};
