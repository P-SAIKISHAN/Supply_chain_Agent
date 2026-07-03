# API Credentials Guide

This platform is built to work in two modes:

1. `DEMO_MODE=true`, where mock providers and seeded data keep every workflow usable.
2. Real provider mode, where you add credentials in `backend/.env` and the ingestion layer switches to live APIs.

## Required vs optional

### Core credentials

| Layer | Provider | Required env vars | Notes |
| --- | --- | --- | --- |
| LLM / summaries | Gemini | `GEMINI_API_KEY`, optional `GEMINI_BASE_URL`, `GEMINI_MODEL` | Used for report generation and RAG summaries |
| LLM / summaries | Groq | `GROQ_API_KEY`, optional `GROQ_BASE_URL`, `LLM_MODEL` | Fast fallback-compatible reasoning |
| Geopolitical news | GDELT | usually none | Public source, no key typically needed |
| Sanctions | OFAC | usually none | Public lists, may require parsing or export handling |
| AIS / shipping | MarineTraffic | `MARINETRAFFIC_API_KEY`, `MARINETRAFFIC_BASE_URL` | Primary AIS provider |
| AIS / shipping | VesselFinder | `VESSELFINDER_API_KEY`, `VESSELFINDER_BASE_URL` | Alternative AIS provider |
| Prices | Alpha Vantage | `ALPHAVANTAGE_API_KEY`, `ALPHAVANTAGE_BASE_URL` | Commodity benchmark series |
| Prices | EIA | `EIA_API_KEY`, `EIA_BASE_URL` | Good fallback for energy series |

### Optional enrichment

| Layer | Provider | Env vars |
| --- | --- | --- |
| News enrichment | NewsAPI | `NEWSAPI_API_KEY`, `NEWSAPI_BASE_URL` |
| News enrichment | Event Registry | `EVENT_REGISTRY_API_KEY` |
| AIS fallback | Datalastic | `DATALASTIC_API_KEY`, `DATALASTIC_BASE_URL` |
| Prices fallback | Crude Price API | `CRUDEPRICE_API_KEY`, `CRUDEPRICE_BASE_URL` |

## What to fill in first

If you want the fastest real-data setup, add these first:

1. `GEMINI_API_KEY` or `GROQ_API_KEY`
2. `ALPHAVANTAGE_API_KEY`
3. `MARINETRAFFIC_API_KEY` or `VESSELFINDER_API_KEY`

You can leave the rest blank and the app will continue using demo data.

## Behavior when keys are missing

- If `DEMO_MODE=true`, the app always uses mock providers.
- If `DEMO_MODE=false` but a provider key is missing, the registry falls back to mock providers.
- If a live provider fails at runtime, ingestion falls back to seeded data and logs the failure.
- Reports and summaries still work because the RAG layer has a template-based fallback.

## Suggested rollout

1. Start with demo mode and confirm the UI and API workflows work.
2. Add LLM credentials for summaries.
3. Add price data credentials.
4. Add AIS credentials.
5. Add enrichment sources later if needed.

## Example minimal `.env`

```env
DEMO_MODE=true
LLM_PROVIDER=gemini
AIS_PROVIDER=mock
PRICE_PROVIDER=mock
GDELT_ENABLED=true
OFAC_ENABLED=true
```

## Example real-data `.env`

```env
DEMO_MODE=false
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
AIS_PROVIDER=marinetraffic
MARINETRAFFIC_API_KEY=your_key_here
PRICE_PROVIDER=alphavantage
ALPHAVANTAGE_API_KEY=your_key_here
```

## Notes

- Keep provider keys in `backend/.env`, not in frontend code.
- Use the backend API only; the frontend should never talk directly to third-party providers.
- If you are unsure whether a provider works, leave demo mode on and add one provider at a time.
