# NLU evaluation — `qwen3-4b-hybrid` parser

Eval file: `ai\nlu\eval_set.jsonl` · rows evaluated: 150 of 150

## Overall

| Metric | Value |
|---|---|
| Exact match (all 7 fields) | 99.3% |
| is_property_query accuracy | 100.0% |
| bhk accuracy | 100.0% |
| locality accuracy | 99.3% |
| property_type accuracy | 100.0% |
| price_min accuracy | 100.0% |
| price_max accuracy | 100.0% |
| keywords accuracy | 100.0% |
| keywords F1 (micro) | 100.0% |
| Valid model output (no fallback) | 100.0% |
| Latency mean / median / p95 (ms) | 8043.0 / 7962.2 / 9416.9 |

## By tag

| Tag | n | Exact | is_prop | bhk | locality | type | price_min | price_max | keywords |
|---|---|---|---|---|---|---|---|---|---|
| approx | 6 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| edge-case | 5 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| gujarati | 14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| hinglish | 18 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| keywords | 14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
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

- line 91 [typo, source=hybrid] `flat near dumas bech 1 cr` — locality: expected `Dumas Beach` got `Dumas`
