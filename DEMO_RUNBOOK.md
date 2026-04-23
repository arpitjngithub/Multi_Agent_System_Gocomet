# Demo Runbook

## Suggested 2-3 Minute Flow

1. Start the app:

```bash
uvicorn backend.main:app --reload
```

2. Open `http://localhost:8000`.

3. Use the `Use Sample PDF` button.
   Expected outcome:
   - Extractor returns all required fields
   - Validator shows all required rules as `match`
   - Router returns `auto_approve`

4. Upload `sample_docs/messy_bol.jpg`.
   Expected outcome:
   - `port_of_discharge` is a required mismatch against `Nhava Sheva`
   - `hs_code` is uncertain because the sample OCR sidecar leaves it blank
   - Router returns `draft_amendment_request`

5. Run these queries in the query box:
   - `How many shipments were flagged this week?`
   - `What is the most common validation failure?`
   - `Show all auto-approved shipments`

## Expected Example Outputs

### Clean Sample

- Decision: `auto_approve`
- Reasoning: `All required fields matched the customer rules with strong confidence and no uncertain values.`

### Messy Sample

- Decision: `draft_amendment_request`
- Reasoning includes:
  - `port of discharge mismatch (found: Mumbai, expected: Nhava Sheva)`
  - `hs code uncertain (confidence: 0.0)`

## Notes

- If you add an OpenAI or Anthropic key, the extractor and query layer can use live LLM calls.
- Without API keys, the demo still works through the local heuristic fallback.
