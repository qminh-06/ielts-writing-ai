# Rubric Data Format

Each line in `ielts_task2_band_descriptors.jsonl` is a JSON object with this schema:

```json
{
  "criterion": "TR",        // One of: TR, CC, LR, GRA
  "band": 7,                // Integer band level (0-9)
  "text": "...",            // The band descriptor text (official IELTS source)
  "source": "IELTS 2024 ..." // Source citation (page, edition, URL)
}
```

## Criteria
- `TR` = Task Response
- `CC` = Coherence & Cohesion
- `LR` = Lexical Resource
- `GRA` = Grammatical Range & Accuracy

## How to Add Descriptors
1. Get the official band descriptors from IELTS/Cambridge materials (Teammate B)
2. Add one JSON object per line for each criterion × band combination
3. Run `make index` to build the ChromaDB index
4. CI uses the in-memory keyword fallback (no index needed)

## Current Status
⚠️ All entries are PLACEHOLDERS. Teammate B (task B1) must replace them with official content.
