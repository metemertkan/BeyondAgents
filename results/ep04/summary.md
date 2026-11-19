# Episode 4 results

48 jobs: 10 customers each; crash plans 1–5 kill the worker four times (after a decision, an approval request, a refund and a reply), plan 0 never. Counted in the services' records.

### With crashes: all models

| | Jobs | Mistakes (customers) | Extra refunds | Repeated replies | Missing replies | Untrue replies | Approval asked again | Model changed its mind | Model decisions | s/job |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Loop with a progress file (PoC) | 10 | 20 | 16 ($320) | 10 | 0 | 0 | 26 | 0 | 140 | 196 |
| Checkpoints (LangGraph, defaults) | 10 | 20 | 10 ($200) | 10 | 0 | 0 | 10 | 0 | 110 | 165 |
| Durable workflow (DBOS) | 10 | 20 | 10 ($200) | 10 | 0 | 0 | 10 | 0 | 110 | 171 |
| Durable workflow + a key per step (what I'd build) | 10 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 0 | 110 | 170 |

### With crashes: gpt-oss:20b

| | Jobs | Mistakes (customers) | Extra refunds | Repeated replies | Missing replies | Untrue replies | Approval asked again | Model changed its mind | Model decisions | s/job |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Loop with a progress file (PoC) | 5 | 10 | 8 ($160) | 5 | 0 | 0 | 13 | 0 | 70 | 335 |
| Checkpoints (LangGraph, defaults) | 5 | 10 | 5 ($100) | 5 | 0 | 0 | 5 | 0 | 55 | 279 |
| Durable workflow (DBOS) | 5 | 10 | 5 ($100) | 5 | 0 | 0 | 5 | 0 | 55 | 287 |
| Durable workflow + a key per step (what I'd build) | 5 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 0 | 55 | 285 |

### With crashes: qwen3:8b

| | Jobs | Mistakes (customers) | Extra refunds | Repeated replies | Missing replies | Untrue replies | Approval asked again | Model changed its mind | Model decisions | s/job |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Loop with a progress file (PoC) | 5 | 10 | 8 ($160) | 5 | 0 | 0 | 13 | 0 | 70 | 57 |
| Checkpoints (LangGraph, defaults) | 5 | 10 | 5 ($100) | 5 | 0 | 0 | 5 | 0 | 55 | 51 |
| Durable workflow (DBOS) | 5 | 10 | 5 ($100) | 5 | 0 | 0 | 5 | 0 | 55 | 55 |
| Durable workflow + a key per step (what I'd build) | 5 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 0 | 55 | 55 |

### No crash: all models

| | Jobs | Mistakes (customers) | Extra refunds | Repeated replies | Missing replies | Untrue replies | Approval asked again | Model changed its mind | Model decisions | s/job |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Loop with a progress file (PoC) | 2 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 0 | 20 | 158 |
| Checkpoints (LangGraph, defaults) | 2 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 0 | 20 | 148 |
| Durable workflow (DBOS) | 2 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 0 | 20 | 147 |
| Durable workflow + a key per step (what I'd build) | 2 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 0 | 20 | 149 |

### No crash: gpt-oss:20b

| | Jobs | Mistakes (customers) | Extra refunds | Repeated replies | Missing replies | Untrue replies | Approval asked again | Model changed its mind | Model decisions | s/job |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Loop with a progress file (PoC) | 1 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 0 | 10 | 265 |
| Checkpoints (LangGraph, defaults) | 1 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 0 | 10 | 247 |
| Durable workflow (DBOS) | 1 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 0 | 10 | 246 |
| Durable workflow + a key per step (what I'd build) | 1 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 0 | 10 | 252 |

### No crash: qwen3:8b

| | Jobs | Mistakes (customers) | Extra refunds | Repeated replies | Missing replies | Untrue replies | Approval asked again | Model changed its mind | Model decisions | s/job |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Loop with a progress file (PoC) | 1 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 0 | 10 | 52 |
| Checkpoints (LangGraph, defaults) | 1 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 0 | 10 | 49 |
| Durable workflow (DBOS) | 1 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 0 | 10 | 48 |
| Durable workflow + a key per step (what I'd build) | 1 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 0 | 10 | 47 |

### With crashes, a rule instead of a model

| | Jobs | Mistakes (customers) | Extra refunds | Repeated replies | Missing replies | Untrue replies | Approval asked again | Model changed its mind | Model decisions | s/job |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Loop with a progress file (PoC) | 5 | 10 | 8 ($160) | 5 | 0 | 0 | 13 | 0 | 70 | 8 |
| Checkpoints (LangGraph, defaults) | 5 | 13 | 5 ($100) | 8 | 0 | 0 | 5 | 0 | 60 | 9 |
| Durable workflow (DBOS) | 5 | 10 | 5 ($100) | 5 | 0 | 0 | 5 | 0 | 55 | 15 |
| Durable workflow + a key per step (what I'd build) | 5 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 0 | 55 | 14 |

### After a hard crash, which steps run again? (`scripts/ep04_checks.py`)

| Library and setting | Outcomes over 10 crashes |
| :--- | :--- |
| DBOS | `step1 step2 step2 step3` × 10 |
| LangGraph, durability=default | `step1 step2 step1 step2 step3` × 7; `step1 step2 step2 step3` × 3 |
| LangGraph, durability=async | `step1 step2 step1 step2 step3` × 6; `step1 step2 step2 step3` × 4 |
| LangGraph, durability=sync | `step1 step2 step2 step3` × 10 |
| LangGraph, durability=exit | `step1 step2 step1 step2 step3` × 10 |
