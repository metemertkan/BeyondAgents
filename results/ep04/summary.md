# Episode 4 results

48 jobs: 10 customers each; crash plans 1–5 kill the worker four times (after a decision, an approval request, a refund and a reply), plan 0 never. Counted in the services' records.

### With crashes: all models

| | Jobs | Mistakes (customers) | Extra refunds | Repeated replies | Missing replies | Approval asked again | Model changed its mind | Model decisions | s/job |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Loop with a progress file (PoC) | 10 | 20 | 16 ($320) | 10 | 0 | 26 | 0 | 140 | 193 |
| Checkpoints (LangGraph, defaults) | 10 | 20 | 10 ($200) | 10 | 0 | 10 | 0 | 110 | 163 |
| Durable workflow (DBOS) | 10 | 20 | 10 ($200) | 10 | 0 | 10 | 0 | 110 | 171 |
| Durable workflow + a key per step (what I'd build) | 10 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 110 | 167 |

### With crashes: gpt-oss:20b

| | Jobs | Mistakes (customers) | Extra refunds | Repeated replies | Missing replies | Approval asked again | Model changed its mind | Model decisions | s/job |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Loop with a progress file (PoC) | 5 | 10 | 8 ($160) | 5 | 0 | 13 | 0 | 70 | 330 |
| Checkpoints (LangGraph, defaults) | 5 | 10 | 5 ($100) | 5 | 0 | 5 | 0 | 55 | 277 |
| Durable workflow (DBOS) | 5 | 10 | 5 ($100) | 5 | 0 | 5 | 0 | 55 | 287 |
| Durable workflow + a key per step (what I'd build) | 5 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 55 | 280 |

### With crashes: qwen3:8b

| | Jobs | Mistakes (customers) | Extra refunds | Repeated replies | Missing replies | Approval asked again | Model changed its mind | Model decisions | s/job |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Loop with a progress file (PoC) | 5 | 10 | 8 ($160) | 5 | 0 | 13 | 0 | 70 | 56 |
| Checkpoints (LangGraph, defaults) | 5 | 10 | 5 ($100) | 5 | 0 | 5 | 0 | 55 | 50 |
| Durable workflow (DBOS) | 5 | 10 | 5 ($100) | 5 | 0 | 5 | 0 | 55 | 54 |
| Durable workflow + a key per step (what I'd build) | 5 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 55 | 54 |

### No crash: all models

| | Jobs | Mistakes (customers) | Extra refunds | Repeated replies | Missing replies | Approval asked again | Model changed its mind | Model decisions | s/job |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Loop with a progress file (PoC) | 2 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 20 | 154 |
| Checkpoints (LangGraph, defaults) | 2 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 20 | 143 |
| Durable workflow (DBOS) | 2 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 20 | 143 |
| Durable workflow + a key per step (what I'd build) | 2 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 20 | 142 |

### No crash: gpt-oss:20b

| | Jobs | Mistakes (customers) | Extra refunds | Repeated replies | Missing replies | Approval asked again | Model changed its mind | Model decisions | s/job |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Loop with a progress file (PoC) | 1 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 10 | 256 |
| Checkpoints (LangGraph, defaults) | 1 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 10 | 238 |
| Durable workflow (DBOS) | 1 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 10 | 239 |
| Durable workflow + a key per step (what I'd build) | 1 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 10 | 239 |

### No crash: qwen3:8b

| | Jobs | Mistakes (customers) | Extra refunds | Repeated replies | Missing replies | Approval asked again | Model changed its mind | Model decisions | s/job |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Loop with a progress file (PoC) | 1 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 10 | 51 |
| Checkpoints (LangGraph, defaults) | 1 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 10 | 48 |
| Durable workflow (DBOS) | 1 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 10 | 47 |
| Durable workflow + a key per step (what I'd build) | 1 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 10 | 45 |

### With crashes, a rule instead of a model

| | Jobs | Mistakes (customers) | Extra refunds | Repeated replies | Missing replies | Approval asked again | Model changed its mind | Model decisions | s/job |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Loop with a progress file (PoC) | 5 | 10 | 8 ($160) | 5 | 0 | 13 | 0 | 70 | 9 |
| Checkpoints (LangGraph, defaults) | 5 | 12 | 5 ($100) | 7 | 0 | 5 | 0 | 58 | 12 |
| Durable workflow (DBOS) | 5 | 10 | 5 ($100) | 5 | 0 | 5 | 0 | 55 | 16 |
| Durable workflow + a key per step (what I'd build) | 5 | 0 | 0 ($0) | 0 | 0 | 0 | 0 | 55 | 15 |

### After a hard crash, which steps run again? (`scripts/ep04_checks.py`)

| Library and setting | Outcomes over 10 crashes |
| :--- | :--- |
| DBOS | `step1 step2 step2 step3` × 10 |
| LangGraph, durability=default | `step1 step2 step1 step2 step3` × 7; `step1 step2 step2 step3` × 3 |
| LangGraph, durability=async | `step1 step2 step1 step2 step3` × 6; `step1 step2 step2 step3` × 4 |
| LangGraph, durability=sync | `step1 step2 step2 step3` × 10 |
| LangGraph, durability=exit | `step1 step2 step1 step2 step3` × 10 |
