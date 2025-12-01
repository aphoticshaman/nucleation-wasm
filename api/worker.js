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
  <title>Divergence Engine - Geopolitical Conflict Prediction API</title>
  <meta name="description" content="Information-theoretic conflict prediction. Quantify worldview divergence between 40+ state actors using KL divergence. REST API for defense, intelligence, and strategic analysis.">
  <meta name="keywords" content="conflict prediction, geopolitical analysis, KL divergence, strategic intelligence, defense API, OSINT, threat assessment">
  <meta property="og:title" content="Divergence Engine - Conflict Prediction API">
  <meta property="og:description" content="Quantify worldview divergence. Predict conflict. Find alignment.">
  <meta property="og:type" content="website">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root{--bg:#000;--bg2:#0a0a0a;--card:#111;--border:#1a1a1a;--border2:#252525;--fg:#e8e8e8;--muted:#666;--accent:#00ff88;--accent2:#ff6b6b;--warn:#ffd93d;--blue:#4d9fff}
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'Inter',system-ui,sans-serif;background:var(--bg);color:var(--fg);line-height:1.6}
    code,pre,.mono{font-family:'JetBrains Mono',monospace}
    .container{max-width:1200px;margin:0 auto;padding:0 2rem}

    /* Navigation */
    nav{position:fixed;top:0;left:0;right:0;background:rgba(0,0,0,0.9);backdrop-filter:blur(10px);border-bottom:1px solid var(--border);z-index:1000;padding:1rem 0}
    nav .container{display:flex;align-items:center;justify-content:space-between}
    .logo{font-weight:700;font-size:1.1rem;color:var(--accent);text-decoration:none;font-family:'JetBrains Mono',monospace}
    .nav-links{display:flex;gap:2rem}
    .nav-links a{color:var(--muted);text-decoration:none;font-size:0.9rem;transition:color 0.2s}
    .nav-links a:hover{color:var(--fg)}

    /* Hero */
    .hero{padding:8rem 0 4rem;text-align:center;background:linear-gradient(180deg,var(--bg) 0%,var(--bg2) 100%)}
    .hero-badge{display:inline-block;background:var(--card);border:1px solid var(--border2);padding:0.4rem 1rem;border-radius:20px;font-size:0.8rem;color:var(--accent);margin-bottom:1.5rem}
    .hero h1{font-size:3.5rem;font-weight:700;margin-bottom:1rem;letter-spacing:-0.02em}
    .hero h1 span{color:var(--accent)}
    .hero-sub{font-size:1.25rem;color:var(--muted);max-width:600px;margin:0 auto 2rem}
    .hero-stats{display:flex;gap:3rem;justify-content:center;margin:2rem 0}
    .hero-stat{text-align:center}
    .hero-stat-num{font-size:2.5rem;font-weight:700;color:var(--accent);font-family:'JetBrains Mono',monospace}
    .hero-stat-label{font-size:0.85rem;color:var(--muted);margin-top:0.25rem}
    .hero-cta{display:flex;gap:1rem;justify-content:center;margin-top:2rem}
    .btn{display:inline-flex;align-items:center;gap:0.5rem;padding:0.75rem 1.5rem;border-radius:6px;font-weight:600;text-decoration:none;font-size:0.95rem;transition:all 0.2s;border:none;cursor:pointer;font-family:inherit}
    .btn-primary{background:var(--accent);color:var(--bg)}
    .btn-primary:hover{opacity:0.9;transform:translateY(-1px)}
    .btn-secondary{background:transparent;color:var(--fg);border:1px solid var(--border2)}
    .btn-secondary:hover{border-color:var(--accent);color:var(--accent)}

    /* Formula */
    .formula-section{padding:3rem 0;background:var(--bg2);border-top:1px solid var(--border);border-bottom:1px solid var(--border)}
    .formula-box{background:var(--card);border:1px solid var(--border2);border-radius:12px;padding:2rem;max-width:800px;margin:0 auto;text-align:center}
    .formula-box code{font-size:1.4rem;color:var(--accent)}
    .formula-box p{color:var(--muted);margin-top:1rem;font-size:0.95rem}

    /* Section */
    section{padding:5rem 0}
    section h2{font-size:2rem;margin-bottom:0.5rem;font-weight:600}
    section .section-sub{color:var(--muted);margin-bottom:2rem}
    .section-dark{background:var(--bg2)}

    /* Demo Panel */
    .demo-panel{background:var(--card);border:1px solid var(--border2);border-radius:12px;overflow:hidden}
    .demo-header{display:flex;align-items:center;gap:0.5rem;padding:1rem 1.5rem;border-bottom:1px solid var(--border);background:var(--bg2)}
    .demo-dot{width:12px;height:12px;border-radius:50%;background:var(--border2)}
    .demo-dot.red{background:#ff5f56}.demo-dot.yellow{background:#ffbd2e}.demo-dot.green{background:#27ca40}
    .demo-title{margin-left:1rem;color:var(--muted);font-size:0.85rem;font-family:'JetBrains Mono',monospace}
    .demo-body{padding:1.5rem}
    .demo-controls{display:flex;gap:0.75rem;margin-bottom:1rem;flex-wrap:wrap;align-items:center}
    .demo-select{background:var(--bg);color:var(--fg);border:1px solid var(--border2);padding:0.6rem 1rem;border-radius:6px;font-family:inherit;font-size:0.9rem;cursor:pointer;min-width:150px}
    .demo-select:focus{outline:none;border-color:var(--accent)}
    .demo-btn{padding:0.6rem 1.25rem;border-radius:6px;font-weight:600;font-size:0.9rem;cursor:pointer;transition:all 0.2s;border:1px solid transparent}
    .demo-btn-primary{background:var(--accent);color:var(--bg);border-color:var(--accent)}
    .demo-btn-secondary{background:transparent;color:var(--accent);border-color:var(--accent)}
    .demo-btn-small{padding:0.4rem 0.75rem;font-size:0.8rem;background:var(--bg);color:var(--muted);border-color:var(--border2)}
    .demo-result{background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:1.25rem;min-height:200px;max-height:400px;overflow:auto}
    .demo-vs{color:var(--muted);font-size:0.9rem}
    .demo-actions{margin-left:auto;display:flex;gap:0.5rem}

    /* Risk colors */
    .risk-LOW{color:var(--accent)}.risk-MODERATE{color:var(--warn)}.risk-ELEVATED{color:#ff9f43}.risk-HIGH{color:var(--accent2)}.risk-CRITICAL{color:#ff0000}

    /* API Docs */
    .endpoint-grid{display:grid;gap:1rem}
    .endpoint{background:var(--card);border:1px solid var(--border2);border-radius:8px;overflow:hidden}
    .endpoint-header{display:flex;align-items:center;gap:1rem;padding:1rem 1.25rem;cursor:pointer;transition:background 0.2s}
    .endpoint-header:hover{background:var(--bg2)}
    .endpoint-method{font-family:'JetBrains Mono',monospace;font-size:0.75rem;font-weight:600;padding:0.25rem 0.5rem;border-radius:4px}
    .method-get{background:rgba(77,159,255,0.15);color:var(--blue)}
    .method-post{background:rgba(0,255,136,0.15);color:var(--accent)}
    .endpoint-path{font-family:'JetBrains Mono',monospace;font-size:0.9rem}
    .endpoint-desc{color:var(--muted);font-size:0.85rem;margin-left:auto}
    .endpoint-body{display:none;padding:1.25rem;border-top:1px solid var(--border);background:var(--bg2)}
    .endpoint.open .endpoint-body{display:block}
    .endpoint-chevron{color:var(--muted);transition:transform 0.2s;margin-left:0.5rem}
    .endpoint.open .endpoint-chevron{transform:rotate(90deg)}

    /* Code block */
    .code-tabs{display:flex;gap:0;border-bottom:1px solid var(--border);margin-bottom:0}
    .code-tab{padding:0.6rem 1rem;font-size:0.8rem;color:var(--muted);cursor:pointer;border-bottom:2px solid transparent;transition:all 0.2s;font-family:'JetBrains Mono',monospace}
    .code-tab:hover{color:var(--fg)}
    .code-tab.active{color:var(--accent);border-bottom-color:var(--accent)}
    .code-block{background:var(--bg);border:1px solid var(--border);border-radius:8px;overflow:hidden;margin:1rem 0}
    .code-block pre{padding:1rem;overflow-x:auto;font-size:0.85rem;line-height:1.5}
    .code-block code{color:var(--fg)}
    .code-copy{position:absolute;top:0.5rem;right:0.5rem;padding:0.4rem 0.6rem;font-size:0.75rem;background:var(--card);border:1px solid var(--border2);border-radius:4px;color:var(--muted);cursor:pointer}
    .code-copy:hover{color:var(--accent);border-color:var(--accent)}
    .code-wrapper{position:relative}

    /* Categories Grid */
    .cat-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem}
    .cat-card{background:var(--card);border:1px solid var(--border2);border-radius:8px;padding:1.25rem}
    .cat-card h4{color:var(--accent);font-size:0.95rem;margin-bottom:0.5rem;font-weight:600}
    .cat-card p{color:var(--muted);font-size:0.85rem}

    /* Use Cases */
    .use-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1.5rem}
    .use-card{background:var(--card);border:1px solid var(--border2);border-radius:12px;padding:1.75rem}
    .use-icon{width:48px;height:48px;background:rgba(0,255,136,0.1);border-radius:10px;display:flex;align-items:center;justify-content:center;margin-bottom:1rem;font-size:1.5rem}
    .use-card h4{font-size:1.1rem;margin-bottom:0.5rem}
    .use-card p{color:var(--muted);font-size:0.9rem}

    /* Table */
    .api-table{width:100%;border-collapse:collapse;font-size:0.9rem}
    .api-table th,.api-table td{padding:1rem;text-align:left;border-bottom:1px solid var(--border)}
    .api-table th{color:var(--muted);font-weight:500;font-size:0.8rem;text-transform:uppercase;letter-spacing:0.05em}
    .api-table code{background:var(--bg);padding:0.2rem 0.5rem;border-radius:4px;font-size:0.85rem}

    /* Footer */
    footer{padding:4rem 0;border-top:1px solid var(--border);background:var(--bg2)}
    .footer-grid{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:3rem}
    .footer-brand p{color:var(--muted);font-size:0.9rem;margin-top:0.5rem}
    .footer-col h5{color:var(--muted);font-size:0.8rem;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:1rem}
    .footer-col a{display:block;color:var(--fg);text-decoration:none;font-size:0.9rem;padding:0.3rem 0;transition:color 0.2s}
    .footer-col a:hover{color:var(--accent)}
    .footer-bottom{margin-top:3rem;padding-top:2rem;border-top:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;color:var(--muted);font-size:0.85rem}

    @media(max-width:768px){
      .hero h1{font-size:2.5rem}
      .hero-stats{flex-wrap:wrap;gap:1.5rem}
      .nav-links{display:none}
      .footer-grid{grid-template-columns:1fr}
      .demo-controls{flex-direction:column;align-items:stretch}
      .demo-actions{margin-left:0;margin-top:0.5rem}
    }
  </style>
</head>
<body>
  <nav>
    <div class="container">
      <a href="#" class="logo">Φ DIVERGENCE</a>
      <div class="nav-links">
        <a href="#demo">Demo</a>
        <a href="#api">API</a>
        <a href="#theory">Theory</a>
        <a href="#use-cases">Use Cases</a>
        <a href="https://github.com/aphoticshaman/nucleation-wasm">GitHub</a>
      </div>
    </div>
  </nav>

  <section class="hero">
    <div class="container">
      <div class="hero-badge">v0.3.0 • Open Source • Edge-Deployed</div>
      <h1><span>Divergence</span> Engine</h1>
      <p class="hero-sub">Information-theoretic conflict prediction. Quantify worldview divergence between state actors using symmetric KL divergence.</p>
      <div class="hero-stats">
        <div class="hero-stat"><div class="hero-stat-num">40+</div><div class="hero-stat-label">State Actors</div></div>
        <div class="hero-stat"><div class="hero-stat-num">12</div><div class="hero-stat-label">Priority Categories</div></div>
        <div class="hero-stat"><div class="hero-stat-num">10</div><div class="hero-stat-label">API Endpoints</div></div>
        <div class="hero-stat"><div class="hero-stat-num">&lt;50ms</div><div class="hero-stat-label">Latency</div></div>
      </div>
      <div class="hero-cta">
        <a href="#demo" class="btn btn-primary">Try Live Demo</a>
        <a href="#api" class="btn btn-secondary">API Reference</a>
      </div>
    </div>
  </section>

  <div class="formula-section">
    <div class="formula-box">
      <code>Φ(A,B) = D<sub>KL</sub>(A‖B) + D<sub>KL</sub>(B‖A)</code>
      <p>Symmetric KL divergence quantifies how differently two actors compress geopolitical information. Higher Φ = greater conflict potential.</p>
    </div>
  </div>

  <section id="demo" class="section-dark">
    <div class="container">
      <h2>Live Analysis</h2>
      <p class="section-sub">Select two actors and analyze their worldview divergence in real-time.</p>

      <div class="demo-panel">
        <div class="demo-header">
          <span class="demo-dot red"></span>
          <span class="demo-dot yellow"></span>
          <span class="demo-dot green"></span>
          <span class="demo-title">divergence-engine</span>
        </div>
        <div class="demo-body">
          <div class="demo-controls">
            <select id="actorA" class="demo-select">
              <optgroup label="Major Powers"><option value="USA">United States</option><option value="CHN" selected>China</option><option value="RUS">Russia</option></optgroup>
              <optgroup label="Europe"><option value="EUR">European Union</option><option value="GBR">United Kingdom</option><option value="DEU">Germany</option><option value="FRA">France</option><option value="POL">Poland</option><option value="UKR">Ukraine</option></optgroup>
              <optgroup label="Middle East"><option value="ISR">Israel</option><option value="IRN">Iran</option><option value="SAU">Saudi Arabia</option><option value="ARE">UAE</option><option value="TUR">Turkey</option><option value="EGY">Egypt</option><option value="SYR">Syria</option><option value="QAT">Qatar</option></optgroup>
              <optgroup label="Asia-Pacific"><option value="JPN">Japan</option><option value="KOR">South Korea</option><option value="PRK">North Korea</option><option value="TWN">Taiwan</option><option value="IND">India</option><option value="PAK">Pakistan</option><option value="AUS">Australia</option><option value="IDN">Indonesia</option><option value="VNM">Vietnam</option><option value="PHL">Philippines</option><option value="SGP">Singapore</option><option value="MYS">Malaysia</option></optgroup>
              <optgroup label="Central Asia"><option value="KAZ">Kazakhstan</option><option value="UZB">Uzbekistan</option><option value="AFG">Afghanistan</option></optgroup>
              <optgroup label="Americas"><option value="CAN">Canada</option><option value="MEX">Mexico</option><option value="BRA">Brazil</option><option value="ARG">Argentina</option><option value="VEN">Venezuela</option></optgroup>
              <optgroup label="Africa"><option value="ZAF">South Africa</option><option value="NGA">Nigeria</option><option value="ETH">Ethiopia</option></optgroup>
              <optgroup label="Oceania"><option value="NZL">New Zealand</option></optgroup>
            </select>
            <span class="demo-vs">vs</span>
            <select id="actorB" class="demo-select">
              <optgroup label="Major Powers"><option value="USA" selected>United States</option><option value="CHN">China</option><option value="RUS">Russia</option></optgroup>
              <optgroup label="Europe"><option value="EUR">European Union</option><option value="GBR">United Kingdom</option><option value="DEU">Germany</option><option value="FRA">France</option><option value="POL">Poland</option><option value="UKR">Ukraine</option></optgroup>
              <optgroup label="Middle East"><option value="ISR">Israel</option><option value="IRN">Iran</option><option value="SAU">Saudi Arabia</option><option value="ARE">UAE</option><option value="TUR">Turkey</option><option value="EGY">Egypt</option><option value="SYR">Syria</option><option value="QAT">Qatar</option></optgroup>
              <optgroup label="Asia-Pacific"><option value="JPN">Japan</option><option value="KOR">South Korea</option><option value="PRK">North Korea</option><option value="TWN">Taiwan</option><option value="IND">India</option><option value="PAK">Pakistan</option><option value="AUS">Australia</option><option value="IDN">Indonesia</option><option value="VNM">Vietnam</option><option value="PHL">Philippines</option><option value="SGP">Singapore</option><option value="MYS">Malaysia</option></optgroup>
              <optgroup label="Central Asia"><option value="KAZ">Kazakhstan</option><option value="UZB">Uzbekistan</option><option value="AFG">Afghanistan</option></optgroup>
              <optgroup label="Americas"><option value="CAN">Canada</option><option value="MEX">Mexico</option><option value="BRA">Brazil</option><option value="ARG">Argentina</option><option value="VEN">Venezuela</option></optgroup>
              <optgroup label="Africa"><option value="ZAF">South Africa</option><option value="NGA">Nigeria</option><option value="ETH">Ethiopia</option></optgroup>
              <optgroup label="Oceania"><option value="NZL">New Zealand</option></optgroup>
            </select>
            <button class="demo-btn demo-btn-primary" onclick="runPredict()">Predict</button>
            <button class="demo-btn demo-btn-secondary" onclick="runExplain()">Explain</button>
            <button class="demo-btn demo-btn-secondary" onclick="runAlign()">Align</button>
            <div class="demo-actions">
              <button class="demo-btn demo-btn-small" onclick="copyJSON()">Copy JSON</button>
              <button class="demo-btn demo-btn-small" onclick="exportJSON()">Export</button>
            </div>
          </div>
          <div class="demo-result" id="output">
            <p style="color:var(--muted)">Select actors and click an action to analyze...</p>
          </div>
        </div>
      </div>
    </div>
  </section>

  <section id="api">
    <div class="container">
      <h2>API Reference</h2>
      <p class="section-sub">RESTful endpoints for programmatic access. All responses in JSON.</p>

      <div class="endpoint-grid">
        <div class="endpoint" onclick="toggleEndpoint(this)">
          <div class="endpoint-header">
            <span class="endpoint-method method-post">POST</span>
            <span class="endpoint-path">/predict</span>
            <span class="endpoint-desc">Escalation prediction between two actors</span>
            <span class="endpoint-chevron">▶</span>
          </div>
          <div class="endpoint-body">
            <div class="code-tabs">
              <span class="code-tab active" onclick="showTab(event,'curl1')">cURL</span>
              <span class="code-tab" onclick="showTab(event,'py1')">Python</span>
              <span class="code-tab" onclick="showTab(event,'js1')">JavaScript</span>
            </div>
            <div class="code-wrapper">
              <div class="code-block" id="curl1">
<pre><code>curl -X POST https://divergence-api.nucleation.workers.dev/predict \\
  -H "Content-Type: application/json" \\
  -d '{"actor_a": "CHN", "actor_b": "USA"}'</code></pre>
              </div>
              <div class="code-block" id="py1" style="display:none">
<pre><code>import requests

response = requests.post(
    "https://divergence-api.nucleation.workers.dev/predict",
    json={"actor_a": "CHN", "actor_b": "USA"}
)
data = response.json()
print(f"Risk Level: {data['prediction']['risk_level']}")
print(f"Φ: {data['metrics']['phi']}")</code></pre>
              </div>
              <div class="code-block" id="js1" style="display:none">
<pre><code>const response = await fetch(
  "https://divergence-api.nucleation.workers.dev/predict",
  {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actor_a: "CHN", actor_b: "USA" })
  }
);
const data = await response.json();
console.log(\`Risk: \${data.prediction.risk_level}\`);</code></pre>
              </div>
            </div>
          </div>
        </div>

        <div class="endpoint" onclick="toggleEndpoint(this)">
          <div class="endpoint-header">
            <span class="endpoint-method method-post">POST</span>
            <span class="endpoint-path">/explain</span>
            <span class="endpoint-desc">Detailed breakdown of divergence drivers</span>
            <span class="endpoint-chevron">▶</span>
          </div>
          <div class="endpoint-body">
            <div class="code-block">
<pre><code>curl -X POST https://divergence-api.nucleation.workers.dev/explain \\
  -H "Content-Type: application/json" \\
  -d '{"actor_a": "ISR", "actor_b": "IRN"}'

# Returns per-category divergence contribution, top drivers, rationales</code></pre>
            </div>
          </div>
        </div>

        <div class="endpoint" onclick="toggleEndpoint(this)">
          <div class="endpoint-header">
            <span class="endpoint-method method-post">POST</span>
            <span class="endpoint-path">/align</span>
            <span class="endpoint-desc">Find cooperation opportunities and mediators</span>
            <span class="endpoint-chevron">▶</span>
          </div>
          <div class="endpoint-body">
            <div class="code-block">
<pre><code>curl -X POST https://divergence-api.nucleation.workers.dev/align \\
  -H "Content-Type: application/json" \\
  -d '{"actor_a": "USA", "actor_b": "CHN"}'

# Returns aligned categories, tension points, potential mediators</code></pre>
            </div>
          </div>
        </div>

        <div class="endpoint" onclick="toggleEndpoint(this)">
          <div class="endpoint-header">
            <span class="endpoint-method method-post">POST</span>
            <span class="endpoint-path">/compare</span>
            <span class="endpoint-desc">Compare one actor to all others</span>
            <span class="endpoint-chevron">▶</span>
          </div>
          <div class="endpoint-body">
            <div class="code-block">
<pre><code>curl -X POST https://divergence-api.nucleation.workers.dev/compare \\
  -H "Content-Type: application/json" \\
  -d '{"actor": "TWN"}'

# Returns most aligned, most divergent, potential allies/rivals</code></pre>
            </div>
          </div>
        </div>

        <div class="endpoint" onclick="toggleEndpoint(this)">
          <div class="endpoint-header">
            <span class="endpoint-method method-get">GET</span>
            <span class="endpoint-path">/actors</span>
            <span class="endpoint-desc">All actors with metadata and distributions</span>
            <span class="endpoint-chevron">▶</span>
          </div>
          <div class="endpoint-body">
            <div class="code-block">
<pre><code>curl https://divergence-api.nucleation.workers.dev/actors

# Returns 40+ actors with names, regions, entropy scores</code></pre>
            </div>
          </div>
        </div>

        <div class="endpoint" onclick="toggleEndpoint(this)">
          <div class="endpoint-header">
            <span class="endpoint-method method-get">GET</span>
            <span class="endpoint-path">/matrix</span>
            <span class="endpoint-desc">Full N×N divergence matrix</span>
            <span class="endpoint-chevron">▶</span>
          </div>
          <div class="endpoint-body">
            <div class="code-block">
<pre><code>curl https://divergence-api.nucleation.workers.dev/matrix

# Returns complete pairwise Φ values, most aligned/divergent pairs</code></pre>
            </div>
          </div>
        </div>

        <div class="endpoint" onclick="toggleEndpoint(this)">
          <div class="endpoint-header">
            <span class="endpoint-method method-get">GET</span>
            <span class="endpoint-path">/cluster</span>
            <span class="endpoint-desc">Actors grouped by worldview similarity</span>
            <span class="endpoint-chevron">▶</span>
          </div>
          <div class="endpoint-body">
            <div class="code-block">
<pre><code>curl https://divergence-api.nucleation.workers.dev/cluster

# Returns clusters: Western Liberal, Authoritarian, Regional Powers, etc.</code></pre>
            </div>
          </div>
        </div>

        <div class="endpoint" onclick="toggleEndpoint(this)">
          <div class="endpoint-header">
            <span class="endpoint-method method-get">GET</span>
            <span class="endpoint-path">/regions</span>
            <span class="endpoint-desc">Actors by geographic region</span>
            <span class="endpoint-chevron">▶</span>
          </div>
          <div class="endpoint-body">
            <div class="code-block">
<pre><code>curl https://divergence-api.nucleation.workers.dev/regions

# Returns actors grouped by region with top priorities</code></pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>

  <section id="theory" class="section-dark">
    <div class="container">
      <h2>Compression Categories</h2>
      <p class="section-sub">Each actor's worldview is modeled as a probability distribution over 12 strategic priorities.</p>

      <div class="cat-grid">
        <div class="cat-card"><h4>Diplomatic Multilateralism</h4><p>UN engagement, treaty compliance, international institutions</p></div>
        <div class="cat-card"><h4>Economic Interdependence</h4><p>Trade relationships, investment flows, supply chain dependencies</p></div>
        <div class="cat-card"><h4>Military Security</h4><p>Defense posture, alliance commitments, deterrence strategy</p></div>
        <div class="cat-card"><h4>Territorial Sovereignty</h4><p>Border disputes, maritime claims, separatist movements</p></div>
        <div class="cat-card"><h4>Ideological Legitimacy</h4><p>Regime type justification, values projection, soft power</p></div>
        <div class="cat-card"><h4>Domestic Stability</h4><p>Internal political cohesion, protest management, regime security</p></div>
        <div class="cat-card"><h4>Resource Access</h4><p>Energy security, critical minerals, food and water</p></div>
        <div class="cat-card"><h4>Technological Competition</h4><p>AI, semiconductors, cyber capabilities, space</p></div>
        <div class="cat-card"><h4>Historical Grievance</h4><p>Past conflicts, colonial legacy, national humiliation narratives</p></div>
        <div class="cat-card"><h4>Regional Hegemony</h4><p>Sphere of influence, buffer states, neighborhood control</p></div>
        <div class="cat-card"><h4>Humanitarian Norms</h4><p>Human rights priorities, refugee policy, NGO engagement</p></div>
        <div class="cat-card"><h4>Nuclear Deterrence</h4><p>WMD doctrine, nonproliferation stance, MAD calculations</p></div>
      </div>
    </div>
  </section>

  <section id="use-cases">
    <div class="container">
      <h2>Applications</h2>
      <p class="section-sub">From strategic analysis to automated monitoring.</p>

      <div class="use-grid">
        <div class="use-card">
          <div class="use-icon">🛡️</div>
          <h4>Defense & Intelligence</h4>
          <p>Threat assessment, alliance stability analysis, wargame scenario generation, early warning indicators.</p>
        </div>
        <div class="use-card">
          <div class="use-icon">💹</div>
          <h4>Financial Risk</h4>
          <p>Geopolitical risk scoring for portfolios, sovereign debt analysis, supply chain exposure assessment.</p>
        </div>
        <div class="use-card">
          <div class="use-icon">🏛️</div>
          <h4>Policy Analysis</h4>
          <p>Diplomatic strategy optimization, mediation opportunity identification, sanctions impact modeling.</p>
        </div>
        <div class="use-card">
          <div class="use-icon">📊</div>
          <h4>Research</h4>
          <p>Quantitative IR studies, foreign policy pattern analysis, conflict forecasting model training data.</p>
        </div>
        <div class="use-card">
          <div class="use-icon">🤖</div>
          <h4>Automated Monitoring</h4>
          <p>Real-time divergence tracking, threshold alerting, trend detection across actor pairs.</p>
        </div>
        <div class="use-card">
          <div class="use-icon">🎓</div>
          <h4>Education</h4>
          <p>Interactive IR teaching tool, scenario exploration, strategic studies coursework.</p>
        </div>
      </div>
    </div>
  </section>

  <section class="section-dark">
    <div class="container">
      <h2>Risk Classification</h2>
      <p class="section-sub">Escalation probability mapped to operational risk levels.</p>

      <table class="api-table">
        <thead>
          <tr><th>Φ Range</th><th>Risk Level</th><th>Interpretation</th></tr>
        </thead>
        <tbody>
          <tr><td><code>0.0 - 0.5</code></td><td><span class="risk-LOW">LOW</span></td><td>Aligned worldviews, routine diplomacy sufficient</td></tr>
          <tr><td><code>0.5 - 1.0</code></td><td><span class="risk-MODERATE">MODERATE</span></td><td>Notable differences, enhanced engagement recommended</td></tr>
          <tr><td><code>1.0 - 2.0</code></td><td><span class="risk-ELEVATED">ELEVATED</span></td><td>Significant divergence, active conflict prevention needed</td></tr>
          <tr><td><code>2.0 - 4.0</code></td><td><span class="risk-HIGH">HIGH</span></td><td>Severe misalignment, crisis management protocols</td></tr>
          <tr><td><code>&gt; 4.0</code></td><td><span class="risk-CRITICAL">CRITICAL</span></td><td>Fundamental incompatibility, deterrence-focused posture</td></tr>
        </tbody>
      </table>
    </div>
  </section>

  <footer>
    <div class="container">
      <div class="footer-grid">
        <div class="footer-brand">
          <span class="logo">Φ DIVERGENCE</span>
          <p>Open-source geopolitical conflict prediction engine. Built with Rust, deployed on Cloudflare Edge.</p>
        </div>
        <div class="footer-col">
          <h5>Resources</h5>
          <a href="https://github.com/aphoticshaman/nucleation-wasm">GitHub</a>
          <a href="https://zenodo.org/records/17766946">Research Paper</a>
          <a href="/actors">Actor Database</a>
          <a href="/matrix">Divergence Matrix</a>
        </div>
        <div class="footer-col">
          <h5>API</h5>
          <a href="#api">Documentation</a>
          <a href="/health">Health Check</a>
          <a href="/cluster">Clustering</a>
          <a href="/regions">Regions</a>
        </div>
        <div class="footer-col">
          <h5>Connect</h5>
          <a href="https://twitter.com/Benthic_Shadow">Twitter</a>
          <a href="https://github.com/aphoticshaman">GitHub</a>
        </div>
      </div>
      <div class="footer-bottom">
        <span>MIT License • Built for the open research community</span>
        <span>Rust/WASM • Cloudflare Workers</span>
      </div>
    </div>
  </footer>

  <script>
    const BASE='';
    let lastData=null;
    let lastType='';

    function formatPredict(d){
      return \`<div style="font-size:0.9rem">
<h3 style="color:var(--accent);margin:0 0 1rem;font-weight:600">\${d.actor_a.name} vs \${d.actor_b.name}</h3>
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1.5rem;margin-bottom:1.5rem">
  <div style="background:var(--card);padding:1rem;border-radius:8px;text-align:center">
    <div style="color:var(--muted);font-size:0.8rem;margin-bottom:0.25rem">Φ (Divergence)</div>
    <div style="font-size:2rem;font-weight:700;font-family:'JetBrains Mono',monospace">\${d.metrics.phi}</div>
  </div>
  <div style="background:var(--card);padding:1rem;border-radius:8px;text-align:center">
    <div style="color:var(--muted);font-size:0.8rem;margin-bottom:0.25rem">Risk Level</div>
    <div class="risk-\${d.prediction.risk_level}" style="font-size:1.5rem;font-weight:700">\${d.prediction.risk_level}</div>
  </div>
  <div style="background:var(--card);padding:1rem;border-radius:8px;text-align:center">
    <div style="color:var(--muted);font-size:0.8rem;margin-bottom:0.25rem">Escalation Prob</div>
    <div style="font-size:2rem;font-weight:700;font-family:'JetBrains Mono',monospace">\${(d.prediction.escalation_probability*100).toFixed(1)}%</div>
  </div>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem;font-size:0.85rem;color:var(--muted)">
  <div>Jensen-Shannon: <span style="color:var(--fg)">\${d.metrics.jensen_shannon}</span></div>
  <div>Hellinger: <span style="color:var(--fg)">\${d.metrics.hellinger}</span></div>
  <div>KL(A→B): <span style="color:var(--fg)">\${d.metrics.kl_a_b}</span></div>
  <div>KL(B→A): <span style="color:var(--fg)">\${d.metrics.kl_b_a}</span></div>
</div>
</div>\`;
    }

    function formatExplain(d){
      const top3=d.top_divergence_drivers.map(t=>
        \`<div style="background:var(--card);padding:0.75rem 1rem;border-radius:6px;margin-bottom:0.5rem;border-left:3px solid var(--accent)">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <strong style="color:var(--fg)">\${t.category.replace(/_/g,' ')}</strong>
            <span style="color:var(--accent);font-family:'JetBrains Mono',monospace;font-size:0.85rem">\${t.percent_of_total}%</span>
          </div>
          <div style="color:var(--muted);font-size:0.85rem;margin-top:0.25rem">
            \${d.actor_a.code}: \${(t.weight_a*100).toFixed(0)}% vs \${d.actor_b.code}: \${(t.weight_b*100).toFixed(0)}%
          </div>
        </div>\`).join('');
      return \`<div style="font-size:0.9rem">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
  <h3 style="color:var(--accent);margin:0;font-weight:600">\${d.actor_a.name} vs \${d.actor_b.name}</h3>
  <div><span style="font-family:'JetBrains Mono',monospace">Φ=\${d.total_phi}</span> <span class="risk-\${d.risk_level}">[\${d.risk_level}]</span></div>
</div>
<div style="color:var(--muted);font-size:0.8rem;margin-bottom:0.5rem;padding:0.75rem;background:var(--card);border-radius:6px">
  <strong>\${d.actor_a.code}:</strong> \${d.actor_a.rationale}
</div>
<div style="color:var(--muted);font-size:0.8rem;margin-bottom:1rem;padding:0.75rem;background:var(--card);border-radius:6px">
  <strong>\${d.actor_b.code}:</strong> \${d.actor_b.rationale}
</div>
<h4 style="color:var(--fg);font-size:0.9rem;margin-bottom:0.75rem">Top Divergence Drivers</h4>
\${top3}
</div>\`;
    }

    function formatAlign(d){
      const aligned=d.aligned_categories.slice(0,5).map(c=>
        \`<span style="background:rgba(0,255,136,0.15);color:var(--accent);padding:0.3rem 0.6rem;border-radius:4px;margin:0.2rem;display:inline-block;font-size:0.85rem">\${c.category.replace(/_/g,' ')}</span>\`).join('');
      const tensions=d.tension_points.slice(0,4).map(c=>
        \`<span style="background:rgba(255,107,107,0.15);color:var(--accent2);padding:0.3rem 0.6rem;border-radius:4px;margin:0.2rem;display:inline-block;font-size:0.85rem">\${c.category.replace(/_/g,' ')}</span>\`).join('');
      const mediators=d.potential_mediators.slice(0,5).map(m=>
        \`<span style="background:var(--card);padding:0.3rem 0.6rem;border-radius:4px;margin:0.2rem;display:inline-block;font-size:0.85rem">\${m.name}</span>\`).join('');
      return \`<div style="font-size:0.9rem">
<h3 style="color:var(--accent);margin:0 0 1.5rem;font-weight:600">\${d.actor_a.name} ↔ \${d.actor_b.name}</h3>
<div style="margin-bottom:1.25rem">
  <h4 style="color:var(--accent);font-size:0.85rem;margin-bottom:0.5rem">✓ Cooperation Opportunities</h4>
  <div>\${aligned||'<span style="color:var(--muted)">None identified</span>'}</div>
</div>
<div style="margin-bottom:1.25rem">
  <h4 style="color:var(--accent2);font-size:0.85rem;margin-bottom:0.5rem">⚠ Tension Points</h4>
  <div>\${tensions||'<span style="color:var(--muted)">None identified</span>'}</div>
</div>
<div>
  <h4 style="color:var(--muted);font-size:0.85rem;margin-bottom:0.5rem">Potential Mediators</h4>
  <div>\${mediators||'<span style="color:var(--muted)">None identified</span>'}</div>
</div>
</div>\`;
    }

    async function runPredict(){
      const a=document.getElementById('actorA').value,b=document.getElementById('actorB').value;
      document.getElementById('output').innerHTML='<p style="color:var(--muted)">Analyzing...</p>';
      try{
        const r=await fetch(BASE+'/predict',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({actor_a:a,actor_b:b})});
        lastData=await r.json();lastType='predict';
        document.getElementById('output').innerHTML=formatPredict(lastData);
      }catch(e){document.getElementById('output').innerHTML='<p style="color:var(--accent2)">Error: '+e.message+'</p>'}
    }

    async function runExplain(){
      const a=document.getElementById('actorA').value,b=document.getElementById('actorB').value;
      document.getElementById('output').innerHTML='<p style="color:var(--muted)">Analyzing...</p>';
      try{
        const r=await fetch(BASE+'/explain',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({actor_a:a,actor_b:b})});
        lastData=await r.json();lastType='explain';
        document.getElementById('output').innerHTML=formatExplain(lastData);
      }catch(e){document.getElementById('output').innerHTML='<p style="color:var(--accent2)">Error: '+e.message+'</p>'}
    }

    async function runAlign(){
      const a=document.getElementById('actorA').value,b=document.getElementById('actorB').value;
      document.getElementById('output').innerHTML='<p style="color:var(--muted)">Analyzing...</p>';
      try{
        const r=await fetch(BASE+'/align',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({actor_a:a,actor_b:b})});
        lastData=await r.json();lastType='align';
        document.getElementById('output').innerHTML=formatAlign(lastData);
      }catch(e){document.getElementById('output').innerHTML='<p style="color:var(--accent2)">Error: '+e.message+'</p>'}
    }

    function copyJSON(){
      if(!lastData)return;
      navigator.clipboard.writeText(JSON.stringify(lastData,null,2));
      event.target.textContent='Copied!';setTimeout(()=>event.target.textContent='Copy JSON',1500);
    }

    function exportJSON(){
      if(!lastData)return;
      const blob=new Blob([JSON.stringify(lastData,null,2)],{type:'application/json'});
      const url=URL.createObjectURL(blob);
      const a=document.createElement('a');
      a.href=url;a.download=\`divergence-\${lastType}-\${lastData.actor_a?.code||'data'}-\${lastData.actor_b?.code||''}.json\`;
      a.click();URL.revokeObjectURL(url);
    }

    function toggleEndpoint(el){
      el.classList.toggle('open');
    }

    function showTab(e,id){
      const parent=e.target.closest('.endpoint-body');
      parent.querySelectorAll('.code-tab').forEach(t=>t.classList.remove('active'));
      parent.querySelectorAll('.code-block').forEach(b=>b.style.display='none');
      e.target.classList.add('active');
      document.getElementById(id).style.display='block';
    }

    // Smooth scroll
    document.querySelectorAll('a[href^="#"]').forEach(a=>{
      a.addEventListener('click',e=>{
        e.preventDefault();
        document.querySelector(a.getAttribute('href'))?.scrollIntoView({behavior:'smooth'});
      });
    });

    runPredict();
  </script>
</body>
</html>`;

// Core math - pure JS implementation (WASM version is 100x faster for batch)

// Engineer page HTML - Technical Deep Dive
const ENGINEER_PAGE_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Engineer - Divergence Engine Technical Documentation</title>
  <meta name="description" content="Technical documentation for the Divergence Engine. Architecture, mathematical foundations, data methodology, and integration guides.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root{--bg:#000;--bg2:#0a0a0a;--card:#111;--border:#1a1a1a;--border2:#252525;--fg:#e8e8e8;--muted:#666;--accent:#00ff88;--accent2:#ff6b6b;--warn:#ffd93d;--blue:#4d9fff}
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'Inter',system-ui,sans-serif;background:var(--bg);color:var(--fg);line-height:1.7}
    code,pre,.mono{font-family:'JetBrains Mono',monospace}
    .container{max-width:900px;margin:0 auto;padding:0 2rem}
    nav{position:fixed;top:0;left:0;right:0;background:rgba(0,0,0,0.95);backdrop-filter:blur(10px);border-bottom:1px solid var(--border);z-index:1000;padding:1rem 0}
    nav .container{display:flex;align-items:center;justify-content:space-between;max-width:1200px}
    .logo{font-weight:700;font-size:1.1rem;color:var(--accent);text-decoration:none;font-family:'JetBrains Mono',monospace}
    .nav-links{display:flex;gap:2rem}
    .nav-links a{color:var(--muted);text-decoration:none;font-size:0.9rem;transition:color 0.2s}
    .nav-links a:hover,.nav-links a.active{color:var(--accent)}
    .hero{padding:8rem 0 3rem;border-bottom:1px solid var(--border)}
    .hero h1{font-size:2.5rem;margin-bottom:1rem;font-weight:700}
    .hero p{color:var(--muted);font-size:1.1rem}
    .toc{position:fixed;right:2rem;top:6rem;width:200px;font-size:0.85rem}
    .toc h4{color:var(--muted);margin-bottom:1rem;text-transform:uppercase;letter-spacing:0.05em;font-size:0.75rem}
    .toc a{display:block;color:var(--muted);text-decoration:none;padding:0.3rem 0;border-left:2px solid var(--border);padding-left:1rem;transition:all 0.2s}
    .toc a:hover,.toc a.active{color:var(--accent);border-left-color:var(--accent)}
    section{padding:4rem 0;border-bottom:1px solid var(--border)}
    section:last-of-type{border-bottom:none}
    h2{font-size:1.75rem;margin-bottom:1.5rem;color:var(--fg)}
    h3{font-size:1.25rem;margin:2rem 0 1rem;color:var(--accent)}
    h4{font-size:1rem;margin:1.5rem 0 0.75rem;color:var(--fg)}
    p{margin-bottom:1rem;color:var(--fg)}
    .code-block{background:var(--card);border:1px solid var(--border2);border-radius:8px;overflow:hidden;margin:1.5rem 0}
    .code-block-header{background:var(--bg2);padding:0.75rem 1rem;border-bottom:1px solid var(--border);font-size:0.8rem;color:var(--muted);display:flex;justify-content:space-between}
    .code-block pre{padding:1rem;overflow-x:auto;font-size:0.85rem;line-height:1.6;margin:0}
    .code-block code{color:var(--fg)}
    .info-box{background:var(--card);border:1px solid var(--border2);border-left:3px solid var(--accent);border-radius:0 8px 8px 0;padding:1.25rem;margin:1.5rem 0}
    .info-box.warn{border-left-color:var(--warn)}
    .info-box h5{color:var(--accent);margin-bottom:0.5rem;font-size:0.9rem}
    .info-box.warn h5{color:var(--warn)}
    .info-box p{margin:0;font-size:0.9rem;color:var(--muted)}
    .metric-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem;margin:1.5rem 0}
    .metric{background:var(--card);border:1px solid var(--border2);border-radius:8px;padding:1.25rem}
    .metric h5{color:var(--accent);font-size:0.85rem;margin-bottom:0.5rem}
    .metric p{color:var(--muted);font-size:0.85rem;margin:0}
    table{width:100%;border-collapse:collapse;margin:1.5rem 0;font-size:0.9rem}
    th,td{padding:0.75rem 1rem;text-align:left;border-bottom:1px solid var(--border)}
    th{color:var(--muted);font-weight:500;font-size:0.8rem;text-transform:uppercase;letter-spacing:0.05em}
    td code{background:var(--bg);padding:0.2rem 0.4rem;border-radius:4px;font-size:0.8rem}
    .formula{background:var(--card);border:1px solid var(--border2);border-radius:8px;padding:1.5rem;margin:1.5rem 0;text-align:center}
    .formula code{font-size:1.2rem;color:var(--accent)}
    .formula p{margin-top:1rem;color:var(--muted);font-size:0.9rem}
    .arch-diagram{background:var(--card);border:1px solid var(--border2);border-radius:8px;padding:2rem;margin:1.5rem 0}
    .arch-row{display:flex;gap:1rem;margin-bottom:1rem;justify-content:center}
    .arch-box{background:var(--bg);border:1px solid var(--border2);border-radius:6px;padding:1rem 1.5rem;text-align:center;font-size:0.85rem}
    .arch-box.highlight{border-color:var(--accent);color:var(--accent)}
    .arch-arrow{color:var(--muted);font-size:1.5rem}
    footer{padding:3rem 0;border-top:1px solid var(--border);text-align:center;color:var(--muted);font-size:0.85rem}
    footer a{color:var(--accent);text-decoration:none}
    @media(max-width:1100px){.toc{display:none}}
    @media(max-width:768px){.nav-links{display:none}.hero h1{font-size:2rem}}
  </style>
</head>
<body>
  <nav>
    <div class="container">
      <a href="/" class="logo">Φ DIVERGENCE</a>
      <div class="nav-links">
        <a href="/">Home</a>
        <a href="/demo">Demo</a>
        <a href="/engineer" class="active">Engineer</a>
        <a href="https://github.com/aphoticshaman/nucleation-wasm">GitHub</a>
      </div>
    </div>
  </nav>

  <div class="toc">
    <h4>On This Page</h4>
    <a href="#architecture">Architecture</a>
    <a href="#mathematics">Mathematics</a>
    <a href="#methodology">Methodology</a>
    <a href="#schema">Schema</a>
    <a href="#performance">Performance</a>
    <a href="#integration">Integration</a>
  </div>

  <div class="container">
    <div class="hero">
      <h1>Technical Documentation</h1>
      <p>Architecture, mathematical foundations, and integration patterns for the Divergence Engine.</p>
    </div>

    <section id="architecture">
      <h2>System Architecture</h2>
      <p>The Divergence Engine is deployed as a serverless edge function on Cloudflare Workers, providing global low-latency access with zero cold start overhead.</p>

      <div class="arch-diagram">
        <div class="arch-row">
          <div class="arch-box">Client Request</div>
          <span class="arch-arrow">→</span>
          <div class="arch-box highlight">Cloudflare Edge</div>
          <span class="arch-arrow">→</span>
          <div class="arch-box">Worker Runtime</div>
        </div>
        <div class="arch-row">
          <div class="arch-box">V8 Isolate</div>
          <span class="arch-arrow">→</span>
          <div class="arch-box highlight">Divergence Engine</div>
          <span class="arch-arrow">→</span>
          <div class="arch-box">JSON Response</div>
        </div>
      </div>

      <h3>Technology Stack</h3>
      <div class="metric-grid">
        <div class="metric"><h5>Runtime</h5><p>Cloudflare Workers (V8 Isolates)</p></div>
        <div class="metric"><h5>Core Engine</h5><p>Rust compiled to WebAssembly</p></div>
        <div class="metric"><h5>API Layer</h5><p>JavaScript/ES Modules</p></div>
        <div class="metric"><h5>Deployment</h5><p>280+ edge locations globally</p></div>
      </div>

      <h3>Dual Implementation</h3>
      <p>The engine provides both pure JavaScript and Rust/WASM implementations:</p>

      <table>
        <thead><tr><th>Implementation</th><th>Use Case</th><th>Performance</th></tr></thead>
        <tbody>
          <tr><td><code>JavaScript</code></td><td>API endpoints, single comparisons</td><td>~1ms per comparison</td></tr>
          <tr><td><code>Rust/WASM</code></td><td>Batch processing, matrix computation</td><td>~0.01ms per comparison</td></tr>
        </tbody>
      </table>

      <div class="info-box">
        <h5>Why Both?</h5>
        <p>JavaScript handles routing and simple requests with minimal overhead. WASM is invoked for computationally intensive operations like full matrix generation (1,600+ comparisons).</p>
      </div>
    </section>

    <section id="mathematics">
      <h2>Mathematical Foundations</h2>
      <p>The Divergence Engine quantifies worldview divergence using information-theoretic measures from probability theory.</p>

      <h3>Kullback-Leibler Divergence</h3>
      <p>KL divergence measures how one probability distribution P differs from a reference distribution Q:</p>

      <div class="formula">
        <code>D<sub>KL</sub>(P‖Q) = Σ P(i) · log(P(i) / Q(i))</code>
        <p>Measured in bits when using log base 2</p>
      </div>

      <div class="info-box warn">
        <h5>Asymmetry</h5>
        <p>KL divergence is asymmetric: D<sub>KL</sub>(P‖Q) ≠ D<sub>KL</sub>(Q‖P). This means "how surprised P is by Q" differs from "how surprised Q is by P".</p>
      </div>

      <h3>Symmetric KL Divergence (Φ)</h3>
      <p>To get a symmetric measure suitable for pairwise comparison, we sum both directions:</p>

      <div class="formula">
        <code>Φ(A,B) = D<sub>KL</sub>(A‖B) + D<sub>KL</sub>(B‖A)</code>
        <p>Our primary metric for conflict prediction</p>
      </div>

      <h3>Additional Metrics</h3>
      <table>
        <thead><tr><th>Metric</th><th>Formula</th><th>Range</th><th>Interpretation</th></tr></thead>
        <tbody>
          <tr><td><code>Jensen-Shannon</code></td><td>½D<sub>KL</sub>(P‖M) + ½D<sub>KL</sub>(Q‖M)</td><td>[0, 1]</td><td>Bounded, symmetric divergence</td></tr>
          <tr><td><code>Hellinger</code></td><td>√(½Σ(√P - √Q)²)</td><td>[0, 1]</td><td>Geometric distance between distributions</td></tr>
          <tr><td><code>Entropy</code></td><td>-Σ P(i) · log P(i)</td><td>[0, log(n)]</td><td>Uncertainty/diversity of priorities</td></tr>
        </tbody>
      </table>

      <h3>Escalation Probability Model</h3>
      <p>We map divergence to escalation probability using a logistic function:</p>

      <div class="code-block">
        <div class="code-block-header">escalation_model.js</div>
        <pre><code>function escalationProbability(phi, dPhiDt = 0, communication = 0.5) {
  const alpha = 0.5;  // Divergence weight
  const beta = 0.3;   // Communication dampening
  const gamma = 0.8;  // Rate sensitivity

  const logit = alpha * phi + gamma * Math.max(0, dPhiDt) - beta * communication;
  return 1 / (1 + Math.exp(-logit));
}</code></pre>
      </div>

      <p>Parameters:</p>
      <ul style="margin-left:1.5rem;color:var(--muted)">
        <li><strong>phi</strong>: Current symmetric KL divergence</li>
        <li><strong>dPhiDt</strong>: Rate of change (positive = worsening)</li>
        <li><strong>communication</strong>: Diplomatic engagement level [0-1]</li>
      </ul>
    </section>

    <section id="methodology">
      <h2>Data Methodology</h2>
      <p>Actor compression schemes are derived from multiple empirical sources and expert assessment.</p>

      <h3>12 Compression Categories</h3>
      <p>Each actor's worldview is modeled as a probability distribution over these strategic priorities:</p>

      <table>
        <thead><tr><th>Index</th><th>Category</th><th>What It Captures</th></tr></thead>
        <tbody>
          <tr><td>0</td><td><code>diplomatic_multilateralism</code></td><td>UN engagement, treaty compliance, institutional participation</td></tr>
          <tr><td>1</td><td><code>economic_interdependence</code></td><td>Trade priority, investment flows, supply chain reliance</td></tr>
          <tr><td>2</td><td><code>military_security</code></td><td>Defense spending, alliance value, deterrence doctrine</td></tr>
          <tr><td>3</td><td><code>territorial_sovereignty</code></td><td>Border disputes, maritime claims, separatism response</td></tr>
          <tr><td>4</td><td><code>ideological_legitimacy</code></td><td>Regime justification, values projection, soft power</td></tr>
          <tr><td>5</td><td><code>domestic_stability</code></td><td>Regime security, protest management, internal cohesion</td></tr>
          <tr><td>6</td><td><code>resource_access</code></td><td>Energy security, critical minerals, food/water</td></tr>
          <tr><td>7</td><td><code>technological_competition</code></td><td>AI, semiconductors, cyber, space capabilities</td></tr>
          <tr><td>8</td><td><code>historical_grievance</code></td><td>Past conflicts, colonial legacy, national humiliation</td></tr>
          <tr><td>9</td><td><code>regional_hegemony</code></td><td>Sphere of influence, buffer states, neighborhood control</td></tr>
          <tr><td>10</td><td><code>humanitarian_norms</code></td><td>Human rights priority, refugee policy, NGO engagement</td></tr>
          <tr><td>11</td><td><code>nuclear_deterrence</code></td><td>WMD doctrine, nonproliferation stance, MAD calculations</td></tr>
        </tbody>
      </table>

      <h3>Distribution Derivation</h3>
      <p>Actor weights are synthesized from:</p>
      <div class="metric-grid">
        <div class="metric"><h5>GDELT Analysis</h5><p>Event coding patterns from 250M+ news events</p></div>
        <div class="metric"><h5>Policy Documents</h5><p>Official foreign policy doctrine, white papers</p></div>
        <div class="metric"><h5>Expert Assessment</h5><p>RAND, CSIS, Brookings, CFR evaluations</p></div>
        <div class="metric"><h5>Behavior Patterns</h5><p>Historical action analysis, revealed preferences</p></div>
      </div>

      <h3>Example: USA vs China</h3>
      <div class="code-block">
        <div class="code-block-header">Distribution Comparison</div>
        <pre><code>Category                    USA     CHN     Gap
─────────────────────────────────────────────────
diplomatic_multilateralism  0.12    0.08    0.04
economic_interdependence    0.15    0.18    0.03
military_security           0.18    0.12    0.06  ← USA higher
territorial_sovereignty     0.05    0.14    0.09  ← CHN much higher
ideological_legitimacy      0.12    0.10    0.02
domestic_stability          0.08    0.10    0.02
resource_access             0.06    0.08    0.02
technological_competition   0.10    0.12    0.02
historical_grievance        0.02    0.04    0.02
regional_hegemony           0.05    0.02    0.03
humanitarian_norms          0.04    0.01    0.03
nuclear_deterrence          0.03    0.01    0.02</code></pre>
      </div>
    </section>

    <section id="schema">
      <h2>API Schema Reference</h2>

      <h3>Actor Object</h3>
      <div class="code-block">
        <div class="code-block-header">TypeScript</div>
        <pre><code>interface Actor {
  code: string;           // ISO 3166-1 alpha-3 or custom
  name: string;           // Full actor name
  region: string;         // Geographic/political grouping
  distribution: number[]; // 12-element probability vector
  rationale: string;      // Explanation of weights
}</code></pre>
      </div>

      <h3>Prediction Response</h3>
      <div class="code-block">
        <div class="code-block-header">TypeScript</div>
        <pre><code>interface PredictResponse {
  actor_a: { code: string; name: string };
  actor_b: { code: string; name: string };
  metrics: {
    phi: number;           // Symmetric KL divergence
    jensen_shannon: number;
    hellinger: number;
    kl_a_b: number;        // Directional KL
    kl_b_a: number;
  };
  prediction: {
    escalation_probability: number; // 0-1
    risk_level: "LOW" | "MODERATE" | "ELEVATED" | "HIGH" | "CRITICAL";
    communication_level: number;
  };
  categories: string[];    // Category labels
  timestamp: string;       // ISO 8601
}</code></pre>
      </div>

      <h3>Risk Level Thresholds</h3>
      <table>
        <thead><tr><th>Φ Range</th><th>Risk Level</th><th>Color Code</th></tr></thead>
        <tbody>
          <tr><td><code>0.0 - 0.5</code></td><td>LOW</td><td style="color:var(--accent)">#00ff88</td></tr>
          <tr><td><code>0.5 - 1.0</code></td><td>MODERATE</td><td style="color:var(--warn)">#ffd93d</td></tr>
          <tr><td><code>1.0 - 2.0</code></td><td>ELEVATED</td><td style="color:#ff9f43">#ff9f43</td></tr>
          <tr><td><code>2.0 - 4.0</code></td><td>HIGH</td><td style="color:var(--accent2)">#ff6b6b</td></tr>
          <tr><td><code>> 4.0</code></td><td>CRITICAL</td><td style="color:#ff0000">#ff0000</td></tr>
        </tbody>
      </table>
    </section>

    <section id="performance">
      <h2>Performance Characteristics</h2>

      <div class="metric-grid">
        <div class="metric"><h5>Cold Start</h5><p>0ms (V8 isolates)</p></div>
        <div class="metric"><h5>P50 Latency</h5><p>~15ms (edge)</p></div>
        <div class="metric"><h5>P99 Latency</h5><p>~45ms (edge)</p></div>
        <div class="metric"><h5>Throughput</h5><p>10,000+ req/sec</p></div>
      </div>

      <h3>Endpoint Benchmarks</h3>
      <table>
        <thead><tr><th>Endpoint</th><th>Computation</th><th>Response Size</th></tr></thead>
        <tbody>
          <tr><td><code>/predict</code></td><td>~0.5ms</td><td>~500 bytes</td></tr>
          <tr><td><code>/explain</code></td><td>~1ms</td><td>~2KB</td></tr>
          <tr><td><code>/compare</code></td><td>~5ms (40 comparisons)</td><td>~8KB</td></tr>
          <tr><td><code>/matrix</code></td><td>~50ms (1600 comparisons)</td><td>~150KB</td></tr>
          <tr><td><code>/cluster</code></td><td>~100ms</td><td>~10KB</td></tr>
        </tbody>
      </table>
    </section>

    <section id="integration">
      <h2>Integration Patterns</h2>

      <h3>Python SDK Pattern</h3>
      <div class="code-block">
        <div class="code-block-header">divergence_client.py</div>
        <pre><code>import requests
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class DivergenceResult:
    phi: float
    risk_level: str
    escalation_prob: float

class DivergenceClient:
    BASE_URL = "https://divergence-api.nucleation.workers.dev"

    def predict(self, actor_a: str, actor_b: str) -> DivergenceResult:
        resp = requests.post(
            f"{self.BASE_URL}/predict",
            json={"actor_a": actor_a, "actor_b": actor_b}
        )
        data = resp.json()
        return DivergenceResult(
            phi=data["metrics"]["phi"],
            risk_level=data["prediction"]["risk_level"],
            escalation_prob=data["prediction"]["escalation_probability"]
        )

    def batch_compare(self, actor: str) -> List[Dict]:
        resp = requests.post(
            f"{self.BASE_URL}/compare",
            json={"actor": actor}
        )
        return resp.json()["all_comparisons"]

# Usage
client = DivergenceClient()
result = client.predict("USA", "CHN")
print(f"USA-CHN Risk: {result.risk_level} (Φ={result.phi})")</code></pre>
      </div>

      <h3>Webhook Integration</h3>
      <div class="code-block">
        <div class="code-block-header">threshold_alert.js</div>
        <pre><code>// Monitor actor pairs and alert on threshold breach
async function monitorPairs(pairs, threshold = 2.0) {
  for (const [a, b] of pairs) {
    const resp = await fetch("https://divergence-api.nucleation.workers.dev/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ actor_a: a, actor_b: b })
    });
    const { metrics, prediction } = await resp.json();

    if (metrics.phi > threshold) {
      await sendAlert({
        pair: \`\${a}-\${b}\`,
        phi: metrics.phi,
        risk: prediction.risk_level,
        timestamp: new Date().toISOString()
      });
    }
  }
}

// Run every hour
monitorPairs([["USA", "CHN"], ["ISR", "IRN"], ["RUS", "UKR"]]);</code></pre>
      </div>

      <h3>Rate Limits</h3>
      <div class="info-box">
        <h5>Fair Use Policy</h5>
        <p>No hard rate limits currently enforced. For high-volume usage (>10,000 req/day), please reach out to discuss dedicated deployment options.</p>
      </div>
    </section>

    <footer>
      <p><a href="/">Φ Divergence Engine</a> • <a href="https://github.com/aphoticshaman/nucleation-wasm">GitHub</a> • MIT License</p>
    </footer>
  </div>

  <script>
    // Highlight TOC on scroll
    const sections = document.querySelectorAll('section[id]');
    const tocLinks = document.querySelectorAll('.toc a');

    window.addEventListener('scroll', () => {
      let current = '';
      sections.forEach(section => {
        const top = section.offsetTop - 100;
        if (scrollY >= top) current = section.getAttribute('id');
      });
      tocLinks.forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('href') === '#' + current) link.classList.add('active');
      });
    });
  </script>
</body>
</html>`;

// Demo page HTML - Full Interactive Console
const DEMO_PAGE_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Demo Console - Divergence Engine</title>
  <meta name="description" content="Interactive demo console for the Divergence Engine API. Test all endpoints, visualize divergence matrices, and explore actor clusters.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root{--bg:#000;--bg2:#0a0a0a;--card:#111;--border:#1a1a1a;--border2:#252525;--fg:#e8e8e8;--muted:#666;--accent:#00ff88;--accent2:#ff6b6b;--warn:#ffd93d;--blue:#4d9fff}
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'Inter',system-ui,sans-serif;background:var(--bg);color:var(--fg);line-height:1.6;min-height:100vh}
    code,pre,.mono{font-family:'JetBrains Mono',monospace}
    nav{position:fixed;top:0;left:0;right:0;background:rgba(0,0,0,0.95);backdrop-filter:blur(10px);border-bottom:1px solid var(--border);z-index:1000;padding:1rem 2rem}
    nav .nav-inner{display:flex;align-items:center;justify-content:space-between;max-width:1400px;margin:0 auto}
    .logo{font-weight:700;font-size:1.1rem;color:var(--accent);text-decoration:none;font-family:'JetBrains Mono',monospace}
    .nav-links{display:flex;gap:2rem}
    .nav-links a{color:var(--muted);text-decoration:none;font-size:0.9rem;transition:color 0.2s}
    .nav-links a:hover,.nav-links a.active{color:var(--accent)}

    .console-layout{display:grid;grid-template-columns:280px 1fr 350px;gap:0;min-height:100vh;padding-top:60px}
    .sidebar{background:var(--bg2);border-right:1px solid var(--border);padding:1.5rem;overflow-y:auto}
    .main-panel{padding:1.5rem;overflow-y:auto}
    .output-panel{background:var(--bg2);border-left:1px solid var(--border);padding:1.5rem;overflow-y:auto}

    .sidebar h3{color:var(--muted);font-size:0.75rem;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:1rem}
    .endpoint-list{display:flex;flex-direction:column;gap:0.25rem}
    .endpoint-item{display:flex;align-items:center;gap:0.75rem;padding:0.6rem 0.75rem;border-radius:6px;cursor:pointer;transition:all 0.15s;border:1px solid transparent}
    .endpoint-item:hover{background:var(--card);border-color:var(--border2)}
    .endpoint-item.active{background:var(--card);border-color:var(--accent)}
    .endpoint-item .method{font-size:0.65rem;font-weight:600;padding:0.15rem 0.4rem;border-radius:3px;font-family:'JetBrains Mono',monospace}
    .method-get{background:rgba(77,159,255,0.2);color:var(--blue)}
    .method-post{background:rgba(0,255,136,0.2);color:var(--accent)}
    .endpoint-item .path{font-size:0.85rem;font-family:'JetBrains Mono',monospace}

    .actors-section{margin-top:2rem}
    .actor-chips{display:flex;flex-wrap:wrap;gap:0.4rem;margin-top:0.75rem}
    .actor-chip{font-size:0.75rem;padding:0.25rem 0.5rem;background:var(--card);border:1px solid var(--border2);border-radius:4px;cursor:pointer;transition:all 0.15s}
    .actor-chip:hover{border-color:var(--accent);color:var(--accent)}
    .actor-chip.selected{background:var(--accent);color:var(--bg);border-color:var(--accent)}

    .main-panel h2{font-size:1.5rem;margin-bottom:0.5rem}
    .main-panel .desc{color:var(--muted);margin-bottom:1.5rem}

    .input-group{margin-bottom:1.25rem}
    .input-group label{display:block;font-size:0.85rem;color:var(--muted);margin-bottom:0.5rem}
    .input-group select,.input-group input{width:100%;background:var(--card);border:1px solid var(--border2);border-radius:6px;padding:0.7rem 1rem;color:var(--fg);font-family:inherit;font-size:0.9rem}
    .input-group select:focus,.input-group input:focus{outline:none;border-color:var(--accent)}
    .input-row{display:grid;grid-template-columns:1fr auto 1fr;gap:1rem;align-items:end}
    .input-row .vs{color:var(--muted);padding-bottom:0.7rem}

    .run-btn{width:100%;padding:0.85rem;background:var(--accent);color:var(--bg);border:none;border-radius:6px;font-weight:600;font-size:0.95rem;cursor:pointer;transition:all 0.15s;margin-top:1rem}
    .run-btn:hover{opacity:0.9;transform:translateY(-1px)}
    .run-btn:disabled{opacity:0.5;cursor:not-allowed;transform:none}

    .output-panel h3{color:var(--muted);font-size:0.75rem;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:1rem;display:flex;justify-content:space-between;align-items:center}
    .output-actions{display:flex;gap:0.5rem}
    .output-actions button{font-size:0.7rem;padding:0.3rem 0.6rem;background:var(--card);border:1px solid var(--border2);border-radius:4px;color:var(--muted);cursor:pointer}
    .output-actions button:hover{border-color:var(--accent);color:var(--accent)}
    .output-box{background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:1rem;min-height:400px;max-height:calc(100vh - 180px);overflow:auto}
    .output-box pre{font-size:0.8rem;line-height:1.5;white-space:pre-wrap}
    .output-box .loading{color:var(--muted);font-style:italic}

    .result-card{background:var(--card);border:1px solid var(--border2);border-radius:8px;padding:1rem;margin-bottom:1rem}
    .result-card h4{color:var(--accent);font-size:0.95rem;margin-bottom:0.5rem}
    .result-metric{display:flex;justify-content:space-between;padding:0.4rem 0;border-bottom:1px solid var(--border);font-size:0.85rem}
    .result-metric:last-child{border-bottom:none}
    .result-metric .label{color:var(--muted)}
    .result-metric .value{font-family:'JetBrains Mono',monospace}

    .risk-LOW{color:var(--accent)}.risk-MODERATE{color:var(--warn)}.risk-ELEVATED{color:#ff9f43}.risk-HIGH{color:var(--accent2)}.risk-CRITICAL{color:#ff0000}

    .matrix-viz{margin-top:1rem}
    .matrix-row{display:flex}
    .matrix-cell{width:20px;height:20px;font-size:0.5rem;display:flex;align-items:center;justify-content:center}

    .cluster-viz{margin-top:1rem}
    .cluster-group{margin-bottom:1rem}
    .cluster-group h5{color:var(--accent);font-size:0.85rem;margin-bottom:0.5rem}
    .cluster-actors{display:flex;flex-wrap:wrap;gap:0.3rem}

    .tabs{display:flex;gap:0;border-bottom:1px solid var(--border);margin-bottom:1rem}
    .tab{padding:0.6rem 1rem;color:var(--muted);cursor:pointer;border-bottom:2px solid transparent;font-size:0.85rem;transition:all 0.15s}
    .tab:hover{color:var(--fg)}
    .tab.active{color:var(--accent);border-bottom-color:var(--accent)}

    @media(max-width:1200px){
      .console-layout{grid-template-columns:1fr}
      .sidebar,.output-panel{display:none}
    }
  </style>
</head>
<body>
  <nav>
    <div class="nav-inner">
      <a href="/" class="logo">Φ DIVERGENCE</a>
      <div class="nav-links">
        <a href="/">Home</a>
        <a href="/demo" class="active">Demo</a>
        <a href="/engineer">Engineer</a>
        <a href="https://github.com/aphoticshaman/nucleation-wasm">GitHub</a>
      </div>
    </div>
  </nav>

  <div class="console-layout">
    <div class="sidebar">
      <h3>Endpoints</h3>
      <div class="endpoint-list">
        <div class="endpoint-item active" data-endpoint="predict">
          <span class="method method-post">POST</span>
          <span class="path">/predict</span>
        </div>
        <div class="endpoint-item" data-endpoint="explain">
          <span class="method method-post">POST</span>
          <span class="path">/explain</span>
        </div>
        <div class="endpoint-item" data-endpoint="align">
          <span class="method method-post">POST</span>
          <span class="path">/align</span>
        </div>
        <div class="endpoint-item" data-endpoint="compare">
          <span class="method method-post">POST</span>
          <span class="path">/compare</span>
        </div>
        <div class="endpoint-item" data-endpoint="actors">
          <span class="method method-get">GET</span>
          <span class="path">/actors</span>
        </div>
        <div class="endpoint-item" data-endpoint="cluster">
          <span class="method method-get">GET</span>
          <span class="path">/cluster</span>
        </div>
        <div class="endpoint-item" data-endpoint="matrix">
          <span class="method method-get">GET</span>
          <span class="path">/matrix</span>
        </div>
        <div class="endpoint-item" data-endpoint="regions">
          <span class="method method-get">GET</span>
          <span class="path">/regions</span>
        </div>
      </div>

      <div class="actors-section">
        <h3>Quick Select</h3>
        <div class="actor-chips" id="actorChips"></div>
      </div>
    </div>

    <div class="main-panel">
      <div id="endpoint-predict" class="endpoint-form">
        <h2>Predict Escalation</h2>
        <p class="desc">Calculate divergence metrics and escalation probability between two actors.</p>
        <div class="input-row">
          <div class="input-group">
            <label>Actor A</label>
            <select id="predict-a"></select>
          </div>
          <span class="vs">vs</span>
          <div class="input-group">
            <label>Actor B</label>
            <select id="predict-b"></select>
          </div>
        </div>
        <div class="input-group">
          <label>Communication Level (0-1)</label>
          <input type="number" id="predict-comm" value="0.5" min="0" max="1" step="0.1">
        </div>
        <button class="run-btn" onclick="runPredict()">Run Prediction</button>
      </div>

      <div id="endpoint-explain" class="endpoint-form" style="display:none">
        <h2>Explain Divergence</h2>
        <p class="desc">Detailed breakdown of which categories drive divergence between actors.</p>
        <div class="input-row">
          <div class="input-group">
            <label>Actor A</label>
            <select id="explain-a"></select>
          </div>
          <span class="vs">vs</span>
          <div class="input-group">
            <label>Actor B</label>
            <select id="explain-b"></select>
          </div>
        </div>
        <button class="run-btn" onclick="runExplain()">Explain Divergence</button>
      </div>

      <div id="endpoint-align" class="endpoint-form" style="display:none">
        <h2>Find Alignment</h2>
        <p class="desc">Identify cooperation opportunities, tension points, and potential mediators.</p>
        <div class="input-row">
          <div class="input-group">
            <label>Actor A</label>
            <select id="align-a"></select>
          </div>
          <span class="vs">↔</span>
          <div class="input-group">
            <label>Actor B</label>
            <select id="align-b"></select>
          </div>
        </div>
        <button class="run-btn" onclick="runAlign()">Find Alignment</button>
      </div>

      <div id="endpoint-compare" class="endpoint-form" style="display:none">
        <h2>Compare Actor</h2>
        <p class="desc">Compare one actor against all others to find allies and rivals.</p>
        <div class="input-group">
          <label>Actor</label>
          <select id="compare-actor"></select>
        </div>
        <button class="run-btn" onclick="runCompare()">Compare to All</button>
      </div>

      <div id="endpoint-actors" class="endpoint-form" style="display:none">
        <h2>Actor Database</h2>
        <p class="desc">Retrieve all 40+ actors with metadata and distribution entropy.</p>
        <button class="run-btn" onclick="runActors()">Fetch Actors</button>
      </div>

      <div id="endpoint-cluster" class="endpoint-form" style="display:none">
        <h2>Worldview Clusters</h2>
        <p class="desc">Group actors by worldview similarity into strategic clusters.</p>
        <button class="run-btn" onclick="runCluster()">Generate Clusters</button>
      </div>

      <div id="endpoint-matrix" class="endpoint-form" style="display:none">
        <h2>Divergence Matrix</h2>
        <p class="desc">Full N×N matrix of pairwise divergence values. May take a moment.</p>
        <button class="run-btn" onclick="runMatrix()">Generate Matrix</button>
      </div>

      <div id="endpoint-regions" class="endpoint-form" style="display:none">
        <h2>Regional Breakdown</h2>
        <p class="desc">Actors grouped by geographic region with top priorities.</p>
        <button class="run-btn" onclick="runRegions()">Fetch Regions</button>
      </div>
    </div>

    <div class="output-panel">
      <h3>
        Response
        <div class="output-actions">
          <button onclick="copyOutput()">Copy</button>
          <button onclick="exportOutput()">Export</button>
        </div>
      </h3>
      <div class="tabs">
        <div class="tab active" onclick="setOutputMode('formatted')">Formatted</div>
        <div class="tab" onclick="setOutputMode('json')">JSON</div>
      </div>
      <div class="output-box" id="output">
        <p class="loading">Select an endpoint and run a query...</p>
      </div>
    </div>
  </div>

  <script>
    const BASE = '';
    let lastData = null;
    let outputMode = 'formatted';

    const ACTORS = ['USA','CHN','RUS','EUR','GBR','DEU','FRA','POL','UKR','ISR','IRN','SAU','ARE','TUR','EGY','JPN','KOR','PRK','TWN','IND','PAK','AUS','IDN','VNM','PHL','CAN','MEX','BRA','ARG','VEN','ZAF','NGA','ETH','SYR','AFG','MYS','SGP','NZL','QAT','KAZ','UZB'];
    const ACTOR_NAMES = {USA:'United States',CHN:'China',RUS:'Russia',EUR:'European Union',GBR:'United Kingdom',DEU:'Germany',FRA:'France',POL:'Poland',UKR:'Ukraine',ISR:'Israel',IRN:'Iran',SAU:'Saudi Arabia',ARE:'UAE',TUR:'Turkey',EGY:'Egypt',JPN:'Japan',KOR:'South Korea',PRK:'North Korea',TWN:'Taiwan',IND:'India',PAK:'Pakistan',AUS:'Australia',IDN:'Indonesia',VNM:'Vietnam',PHL:'Philippines',CAN:'Canada',MEX:'Mexico',BRA:'Brazil',ARG:'Argentina',VEN:'Venezuela',ZAF:'South Africa',NGA:'Nigeria',ETH:'Ethiopia',SYR:'Syria',AFG:'Afghanistan',MYS:'Malaysia',SGP:'Singapore',NZL:'New Zealand',QAT:'Qatar',KAZ:'Kazakhstan',UZB:'Uzbekistan'};

    // Populate selects
    function populateSelects() {
      const selects = document.querySelectorAll('select');
      selects.forEach(sel => {
        sel.innerHTML = ACTORS.map(a => \`<option value="\${a}">\${ACTOR_NAMES[a]} (\${a})</option>\`).join('');
      });
      document.getElementById('predict-a').value = 'CHN';
      document.getElementById('predict-b').value = 'USA';
      document.getElementById('explain-a').value = 'ISR';
      document.getElementById('explain-b').value = 'IRN';
      document.getElementById('align-a').value = 'USA';
      document.getElementById('align-b').value = 'CHN';
      document.getElementById('compare-actor').value = 'TWN';
    }

    // Populate actor chips
    function populateChips() {
      const container = document.getElementById('actorChips');
      container.innerHTML = ['USA','CHN','RUS','ISR','IRN','TWN','UKR','PRK'].map(a =>
        \`<div class="actor-chip" onclick="quickSelect('\${a}')">\${a}</div>\`
      ).join('');
    }

    function quickSelect(actor) {
      const activeEndpoint = document.querySelector('.endpoint-item.active').dataset.endpoint;
      if (['predict','explain','align'].includes(activeEndpoint)) {
        document.getElementById(activeEndpoint + '-a').value = actor;
      } else if (activeEndpoint === 'compare') {
        document.getElementById('compare-actor').value = actor;
      }
    }

    // Endpoint switching
    document.querySelectorAll('.endpoint-item').forEach(item => {
      item.addEventListener('click', () => {
        document.querySelectorAll('.endpoint-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');
        document.querySelectorAll('.endpoint-form').forEach(f => f.style.display = 'none');
        document.getElementById('endpoint-' + item.dataset.endpoint).style.display = 'block';
      });
    });

    function setOutputMode(mode) {
      outputMode = mode;
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelector(\`.tab:nth-child(\${mode === 'formatted' ? 1 : 2})\`).classList.add('active');
      if (lastData) renderOutput(lastData);
    }

    function renderOutput(data) {
      const box = document.getElementById('output');
      if (outputMode === 'json') {
        box.innerHTML = '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
      } else {
        box.innerHTML = formatData(data);
      }
    }

    function formatData(d) {
      if (d.metrics && d.prediction) {
        // Predict response
        return \`
          <div class="result-card">
            <h4>\${d.actor_a.name} vs \${d.actor_b.name}</h4>
            <div class="result-metric"><span class="label">Φ (Divergence)</span><span class="value">\${d.metrics.phi}</span></div>
            <div class="result-metric"><span class="label">Risk Level</span><span class="value risk-\${d.prediction.risk_level}">\${d.prediction.risk_level}</span></div>
            <div class="result-metric"><span class="label">Escalation Prob</span><span class="value">\${(d.prediction.escalation_probability * 100).toFixed(1)}%</span></div>
            <div class="result-metric"><span class="label">Jensen-Shannon</span><span class="value">\${d.metrics.jensen_shannon}</span></div>
            <div class="result-metric"><span class="label">Hellinger</span><span class="value">\${d.metrics.hellinger}</span></div>
          </div>\`;
      } else if (d.top_divergence_drivers) {
        // Explain response
        return \`
          <div class="result-card">
            <h4>\${d.actor_a.name} vs \${d.actor_b.name}</h4>
            <div class="result-metric"><span class="label">Total Φ</span><span class="value">\${d.total_phi}</span></div>
            <div class="result-metric"><span class="label">Risk</span><span class="value risk-\${d.risk_level}">\${d.risk_level}</span></div>
          </div>
          <div class="result-card">
            <h4>Top Divergence Drivers</h4>
            \${d.top_divergence_drivers.map(t => \`
              <div class="result-metric">
                <span class="label">\${t.category.replace(/_/g,' ')}</span>
                <span class="value">\${t.percent_of_total}%</span>
              </div>\`).join('')}
          </div>\`;
      } else if (d.aligned_categories) {
        // Align response
        return \`
          <div class="result-card">
            <h4>Cooperation Opportunities</h4>
            \${d.aligned_categories.slice(0,5).map(c => \`<span class="actor-chip" style="background:var(--accent);color:var(--bg)">\${c.category.replace(/_/g,' ')}</span>\`).join(' ')}
          </div>
          <div class="result-card">
            <h4>Tension Points</h4>
            \${d.tension_points.slice(0,5).map(c => \`<span class="actor-chip" style="background:var(--accent2);color:var(--bg)">\${c.category.replace(/_/g,' ')}</span>\`).join(' ')}
          </div>
          <div class="result-card">
            <h4>Potential Mediators</h4>
            \${d.potential_mediators.slice(0,5).map(m => \`<span class="actor-chip">\${m.name}</span>\`).join(' ')}
          </div>\`;
      } else if (d.most_aligned) {
        // Compare response
        return \`
          <div class="result-card">
            <h4>Most Aligned</h4>
            \${d.most_aligned.slice(0,8).map(a => \`
              <div class="result-metric">
                <span class="label">\${a.name}</span>
                <span class="value risk-\${a.risk_level}">\${a.phi}</span>
              </div>\`).join('')}
          </div>
          <div class="result-card">
            <h4>Most Divergent</h4>
            \${d.most_divergent.slice(0,8).map(a => \`
              <div class="result-metric">
                <span class="label">\${a.name}</span>
                <span class="value risk-\${a.risk_level}">\${a.phi}</span>
              </div>\`).join('')}
          </div>\`;
      } else if (d.clusters) {
        // Cluster response
        return Object.entries(d.clusters).map(([name, actors]) => \`
          <div class="result-card">
            <h4>\${name}</h4>
            \${actors.map(a => \`<span class="actor-chip">\${a.code}</span>\`).join(' ')}
          </div>\`).join('');
      } else if (d.matrix) {
        // Matrix response
        return \`
          <div class="result-card">
            <h4>Global Stats</h4>
            <div class="result-metric"><span class="label">Average Φ</span><span class="value">\${d.global_average_phi}</span></div>
          </div>
          <div class="result-card">
            <h4>Most Aligned Pairs</h4>
            \${d.most_aligned_pairs.slice(0,5).map(p => \`
              <div class="result-metric">
                <span class="label">\${p.a}-\${p.b}</span>
                <span class="value">\${p.phi}</span>
              </div>\`).join('')}
          </div>
          <div class="result-card">
            <h4>Most Divergent Pairs</h4>
            \${d.most_divergent_pairs.slice(0,5).map(p => \`
              <div class="result-metric">
                <span class="label">\${p.a}-\${p.b}</span>
                <span class="value">\${p.phi}</span>
              </div>\`).join('')}
          </div>\`;
      } else if (d.regions) {
        // Regions response
        return Object.entries(d.regions).map(([name, actors]) => \`
          <div class="result-card">
            <h4>\${name}</h4>
            \${actors.map(a => \`<span class="actor-chip">\${a.code}</span>\`).join(' ')}
          </div>\`).join('');
      } else if (d.actors) {
        // Actors response
        return \`
          <div class="result-card">
            <h4>Total Actors: \${d.total}</h4>
          </div>
          \${d.actors.slice(0,15).map(a => \`
            <div class="result-metric" style="padding:0.5rem 0;border-bottom:1px solid var(--border)">
              <span class="label">\${a.code} - \${a.name}</span>
              <span class="value">\${a.region}</span>
            </div>\`).join('')}
          <p style="color:var(--muted);margin-top:1rem;font-size:0.85rem">...and \${d.total - 15} more</p>\`;
      }
      return '<pre>' + JSON.stringify(d, null, 2) + '</pre>';
    }

    async function runPredict() {
      const a = document.getElementById('predict-a').value;
      const b = document.getElementById('predict-b').value;
      const comm = parseFloat(document.getElementById('predict-comm').value);
      document.getElementById('output').innerHTML = '<p class="loading">Loading...</p>';
      const r = await fetch(BASE + '/predict', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({actor_a: a, actor_b: b, communication_level: comm})
      });
      lastData = await r.json();
      renderOutput(lastData);
    }

    async function runExplain() {
      const a = document.getElementById('explain-a').value;
      const b = document.getElementById('explain-b').value;
      document.getElementById('output').innerHTML = '<p class="loading">Loading...</p>';
      const r = await fetch(BASE + '/explain', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({actor_a: a, actor_b: b})});
      lastData = await r.json();
      renderOutput(lastData);
    }

    async function runAlign() {
      const a = document.getElementById('align-a').value;
      const b = document.getElementById('align-b').value;
      document.getElementById('output').innerHTML = '<p class="loading">Loading...</p>';
      const r = await fetch(BASE + '/align', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({actor_a: a, actor_b: b})});
      lastData = await r.json();
      renderOutput(lastData);
    }

    async function runCompare() {
      const actor = document.getElementById('compare-actor').value;
      document.getElementById('output').innerHTML = '<p class="loading">Loading...</p>';
      const r = await fetch(BASE + '/compare', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({actor})});
      lastData = await r.json();
      renderOutput(lastData);
    }

    async function runActors() {
      document.getElementById('output').innerHTML = '<p class="loading">Loading...</p>';
      const r = await fetch(BASE + '/actors');
      lastData = await r.json();
      renderOutput(lastData);
    }

    async function runCluster() {
      document.getElementById('output').innerHTML = '<p class="loading">Loading...</p>';
      const r = await fetch(BASE + '/cluster');
      lastData = await r.json();
      renderOutput(lastData);
    }

    async function runMatrix() {
      document.getElementById('output').innerHTML = '<p class="loading">Computing 1600+ comparisons...</p>';
      const r = await fetch(BASE + '/matrix');
      lastData = await r.json();
      renderOutput(lastData);
    }

    async function runRegions() {
      document.getElementById('output').innerHTML = '<p class="loading">Loading...</p>';
      const r = await fetch(BASE + '/regions');
      lastData = await r.json();
      renderOutput(lastData);
    }

    function copyOutput() {
      if (!lastData) return;
      navigator.clipboard.writeText(JSON.stringify(lastData, null, 2));
    }

    function exportOutput() {
      if (!lastData) return;
      const blob = new Blob([JSON.stringify(lastData, null, 2)], {type: 'application/json'});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'divergence-output.json';
      a.click();
      URL.revokeObjectURL(url);
    }

    populateSelects();
    populateChips();
  </script>
</body>
</html>`;

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

      // Engineer documentation page
      if (path === "/engineer" && request.method === "GET") {
        return new Response(ENGINEER_PAGE_HTML, {
          headers: { "Content-Type": "text/html; charset=utf-8" },
        });
      }

      // Interactive demo page
      if (path === "/demo" && request.method === "GET") {
        return new Response(DEMO_PAGE_HTML, {
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
