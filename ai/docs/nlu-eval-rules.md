# NLU evaluation — `rules` parser

Eval file: `ai\nlu\eval_set.jsonl` · rows evaluated: 150 of 150

## Overall

| Metric | Value |
|---|---|
| Exact match (all 7 fields) | 91.3% |
| is_property_query accuracy | 96.7% |
| bhk accuracy | 100.0% |
| locality accuracy | 98.0% |
| property_type accuracy | 98.7% |
| price_min accuracy | 100.0% |
| price_max accuracy | 98.7% |
| keywords accuracy | 97.3% |
| keywords F1 (micro) | 95.7% |
| Valid model output (no fallback) | n/a |
| Latency mean / median / p95 (ms) | 0.4 / 0.2 / 1.5 |

## By tag

| Tag | n | Exact | is_prop | bhk | locality | type | price_min | price_max | keywords |
|---|---|---|---|---|---|---|---|---|---|
| approx | 6 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| edge-case | 5 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| gujarati | 14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| hinglish | 18 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| keywords | 14 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| landmark | 10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| no-filters | 6 | 83.3% | 83.3% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| normal | 18 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| offtopic | 12 | 66.7% | 66.7% | 100.0% | 83.3% | 100.0% | 100.0% | 100.0% | 100.0% |
| price-max | 6 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| price-min | 6 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| price-only | 5 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| price-range | 6 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| property-type | 10 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| typo | 14 | 42.9% | 100.0% | 100.0% | 92.9% | 85.7% | 100.0% | 85.7% | 71.4% |

## Worst failures (up to 15)

- line 84 [typo, source=rules] `appartment in pipload under 70 laks` — property_type: expected `flat` got `None`, price_max: expected `7000000.0` got `None`
- line 135 [offtopic, source=rules] `what are the best vegetarian restaurants in vesu surat?` — is_property_query: expected `False` got `True`, locality: expected `None` got `Vesu`
- line 136 [offtopic, source=rules] `how far is surat airport from railway station?` — is_property_query: expected `False` got `True`, locality: expected `None` got `Surat Airport`
- line 82 [typo, source=rules] `bunglow in athwalines above 2 cr` — property_type: expected `house_land` got `None`
- line 85 [typo, source=rules] `plot in katargaam with cornor plot` — keywords: expected `['corner plot']` got `[]`
- line 87 [typo, source=rules] `penthouse in ghoddod rd with gymancium` — keywords: expected `['gym']` got `[]`
- line 88 [typo, source=rules] `3bhk flat in palanpor near skool` — keywords: expected `['near school']` got `[]`
- line 91 [typo, source=rules] `flat near dumas bech 1 cr` — locality: expected `Dumas Beach` got `Dumas`
- line 92 [typo, source=rules] `plot in sachin area 40 laks` — price_max: expected `4000000.0` got `None`
- line 93 [typo, source=rules] `2bhk flat in udhana with balcany` — keywords: expected `['balcony']` got `[]`
- line 133 [offtopic, source=rules] `tell me a funny joke about real estate agents` — is_property_query: expected `False` got `True`
- line 138 [offtopic, source=rules] `how do i make surati locho at home?` — is_property_query: expected `False` got `True`
- line 140 [no-filters, source=rules] `show me what you've got` — is_property_query: expected `True` got `False`
