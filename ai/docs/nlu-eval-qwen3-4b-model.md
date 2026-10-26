# NLU evaluation — `qwen3-4b-model` parser

Eval file: `ai\nlu\eval_set.jsonl` · rows evaluated: 150 of 150

## Overall

| Metric | Value |
|---|---|
| Exact match (all 7 fields) | 96.7% |
| is_property_query accuracy | 100.0% |
| bhk accuracy | 100.0% |
| locality accuracy | 98.7% |
| property_type accuracy | 100.0% |
| price_min accuracy | 100.0% |
| price_max accuracy | 100.0% |
| keywords accuracy | 98.0% |
| keywords F1 (micro) | 96.8% |
| Valid model output (no fallback) | 100.0% |
| Latency mean / median / p95 (ms) | 8159.2 / 8122.7 / 9916.4 |

## By tag

| Tag | n | Exact | is_prop | bhk | locality | type | price_min | price_max | keywords |
|---|---|---|---|---|---|---|---|---|---|
| approx | 6 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| edge-case | 5 | 80.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 80.0% |
| gujarati | 14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| hinglish | 18 | 88.9% | 100.0% | 100.0% | 94.4% | 100.0% | 100.0% | 100.0% | 94.4% |
| keywords | 14 | 92.9% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 92.9% |
| landmark | 10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| no-filters | 6 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| normal | 18 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| offtopic | 12 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| price-max | 6 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| price-min | 6 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| price-only | 5 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| price-range | 6 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| property-type | 10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| typo | 14 | 92.9% | 100.0% | 100.0% | 92.9% | 100.0% | 100.0% | 100.0% | 100.0% |

## Worst failures (up to 15)

- line 58 [hinglish, source=model] `varachha me new construction flat hai koi 45 lakh tak` — keywords: expected `['new construction']` got `[]`
- line 63 [hinglish, source=model] `rander me 2bhk flat dikhao` — locality: expected `Rander` got `None`
- line 91 [typo, source=model] `flat near dumas bech 1 cr` — locality: expected `Dumas Beach` got `Dumas`
- line 127 [keywords, source=model] `new project in jahangirpura with 2bhk` — keywords: expected `['new construction']` got `[]`
- line 148 [edge-case, source=model] `big family flat in vesu under 1.2 cr` — keywords: expected `['spacious']` got `[]`
