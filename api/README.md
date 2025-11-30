# Divergence Engine API

Cloudflare Worker API for conflict prediction.

## Deploy

```bash
# Install wrangler
npm install -g wrangler

# Login to Cloudflare
wrangler login

# Deploy
cd api
wrangler deploy
```

Your API will be live at `https://divergence-api.<your-subdomain>.workers.dev`

## Custom Domain (Optional)

1. Go to Cloudflare Dashboard → Workers → divergence-api → Triggers
2. Add Custom Domain: `api.yourdomain.com`

## Endpoints

### POST /predict
Predict escalation between two actors.

```bash
curl -X POST https://your-api.workers.dev/predict \
  -H "Content-Type: application/json" \
  -d '{"actor_a": "USA", "actor_b": "CHN", "communication_level": 0.5}'
```

### POST /divergence
Compute divergence between custom distributions.

```bash
curl -X POST https://your-api.workers.dev/divergence \
  -H "Content-Type: application/json" \
  -d '{"p": [0.4, 0.3, 0.2, 0.1], "q": [0.25, 0.25, 0.25, 0.25]}'
```

### GET /actors
List available pre-configured actors.

### GET /health
Health check.

## Landing Page

Open `index.html` in a browser or deploy to:
- Cloudflare Pages: `wrangler pages deploy .`
- Vercel: `vercel`
- Netlify: drag & drop

## Stripe Integration

1. Create products in Stripe Dashboard
2. Get payment links
3. Replace `YOUR_STRIPE_LINK` in index.html

## Rate Limiting

Configure in Cloudflare Dashboard → Workers → Settings → Rate Limiting
