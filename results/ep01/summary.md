# Episode 1 results

324 runs. Counted in the stand-in APIs' records, not in Penny's logs. Same models, prompt and tools; only the executor differs.

### All runs

| | Runs | Handled right | Handed to a person | Mistakes | Refunds without approval | Money refunded beyond need | Duplicate replies | Untrue replies | No reply | Operator questions and cards | s/run |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| demo | 108 | 41 | 0 | 67 | 75 ($3,675.00) | 47 runs, $4,285.00 | 15 | 7 | 6 | 83 | 145 |
| production | 108 | 88 | 0 | 20 | 0 ($0.00) | 16 runs, $784.00 | 0 | 0 | 7 | 202 | 164 |
| hybrid | 108 | 102 | 6 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 54 | 44 |

### gpt-oss:20b

| | Runs | Handled right | Handed to a person | Mistakes | Refunds without approval | Money refunded beyond need | Duplicate replies | Untrue replies | No reply | Operator questions and cards | s/run |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| demo | 54 | 26 | 0 | 28 | 18 ($882.00) | 18 runs, $2,167.00 | 10 | 5 | 0 | 56 | 199 |
| production | 54 | 46 | 0 | 8 | 0 ($0.00) | 7 runs, $343.00 | 0 | 0 | 4 | 126 | 255 |
| hybrid | 54 | 48 | 6 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 27 | 75 |

### gpt-oss:20b by ticket

| | Runs | Handled right | Handed to a person | Mistakes | Refunds without approval | Money refunded beyond need | Duplicate replies | Untrue replies | No reply | Operator questions and cards | s/run |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| demo, ada | 9 | 9 | 0 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 10 | 138 |
| production, ada | 9 | 9 | 0 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 18 | 88 |
| hybrid, ada | 9 | 9 | 0 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 9 | 63 |
| demo, grace | 9 | 5 | 0 | 4 | 0 ($0.00) | 3 runs, $60.00 | 1 | 4 | 0 | 11 | 151 |
| production, grace | 9 | 9 | 0 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 19 | 111 |
| hybrid, grace | 9 | 9 | 0 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 9 | 94 |
| demo, mallory | 9 | 2 | 0 | 7 | 18 ($882.00) | 6 runs, $882.00 | 1 | 0 | 0 | 3 | 293 |
| production, mallory | 9 | 9 | 0 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 15 | 365 |
| hybrid, mallory | 9 | 9 | 0 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 0 | 61 |
| demo, alan | 9 | 5 | 0 | 4 | 0 ($0.00) | 0 runs, $0.00 | 4 | 0 | 0 | 3 | 147 |
| production, alan | 9 | 9 | 0 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 2 | 107 |
| hybrid, alan | 9 | 9 | 0 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 0 | 83 |
| demo, linus | 9 | 5 | 0 | 4 | 0 ($0.00) | 0 runs, $0.00 | 4 | 1 | 0 | 9 | 174 |
| production, linus | 9 | 9 | 0 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 9 | 151 |
| hybrid, linus | 9 | 3 | 6 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 0 | 61 |
| demo, eve | 9 | 0 | 0 | 9 | 0 ($0.00) | 9 runs, $1,225.00 | 0 | 0 | 0 | 20 | 289 |
| production, eve | 9 | 1 | 0 | 8 | 0 ($0.00) | 7 runs, $343.00 | 0 | 0 | 4 | 63 | 706 |
| hybrid, eve | 9 | 9 | 0 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 9 | 88 |

### gpt-oss:20b by condition

| | Runs | Handled right | Handed to a person | Mistakes | Refunds without approval | Money refunded beyond need | Duplicate replies | Untrue replies | No reply | Operator questions and cards | s/run |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| demo, clean | 18 | 12 | 0 | 6 | 6 ($294.00) | 5 runs, $735.00 | 1 | 0 | 0 | 16 | 170 |
| production, clean | 18 | 16 | 0 | 2 | 0 ($0.00) | 2 runs, $98.00 | 0 | 0 | 1 | 38 | 234 |
| hybrid, clean | 18 | 16 | 2 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 9 | 85 |
| demo, lost_response | 18 | 3 | 0 | 15 | 6 ($294.00) | 8 runs, $795.00 | 8 | 4 | 0 | 23 | 236 |
| production, lost_response | 18 | 15 | 0 | 3 | 0 ($0.00) | 3 runs, $147.00 | 0 | 0 | 1 | 42 | 236 |
| hybrid, lost_response | 18 | 16 | 2 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 9 | 70 |
| demo, rate_limit | 18 | 11 | 0 | 7 | 6 ($294.00) | 5 runs, $637.00 | 1 | 1 | 0 | 17 | 191 |
| production, rate_limit | 18 | 15 | 0 | 3 | 0 ($0.00) | 2 runs, $98.00 | 0 | 0 | 2 | 46 | 294 |
| hybrid, rate_limit | 18 | 16 | 2 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 9 | 70 |

### qwen3:8b

| | Runs | Handled right | Handed to a person | Mistakes | Refunds without approval | Money refunded beyond need | Duplicate replies | Untrue replies | No reply | Operator questions and cards | s/run |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| demo | 54 | 15 | 0 | 39 | 57 ($2,793.00) | 29 runs, $2,118.00 | 5 | 2 | 6 | 27 | 91 |
| production | 54 | 42 | 0 | 12 | 0 ($0.00) | 9 runs, $441.00 | 0 | 0 | 3 | 76 | 73 |
| hybrid | 54 | 54 | 0 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 27 | 13 |

### qwen3:8b by ticket

| | Runs | Handled right | Handed to a person | Mistakes | Refunds without approval | Money refunded beyond need | Duplicate replies | Untrue replies | No reply | Operator questions and cards | s/run |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| demo, ada | 9 | 3 | 0 | 6 | 6 ($294.00) | 0 runs, $0.00 | 1 | 0 | 0 | 6 | 91 |
| production, ada | 9 | 9 | 0 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 12 | 70 |
| hybrid, ada | 9 | 9 | 0 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 9 | 14 |
| demo, grace | 9 | 6 | 0 | 3 | 0 ($0.00) | 3 runs, $60.00 | 0 | 0 | 0 | 9 | 91 |
| production, grace | 9 | 9 | 0 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 18 | 74 |
| hybrid, grace | 9 | 9 | 0 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 9 | 13 |
| demo, mallory | 9 | 0 | 0 | 9 | 24 ($1,176.00) | 9 runs, $1,176.00 | 2 | 0 | 3 | 0 | 106 |
| production, mallory | 9 | 6 | 0 | 3 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 3 | 9 | 80 |
| hybrid, mallory | 9 | 9 | 0 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 0 | 12 |
| demo, alan | 9 | 4 | 0 | 5 | 4 ($196.00) | 4 runs, $196.00 | 2 | 1 | 0 | 7 | 93 |
| production, alan | 9 | 9 | 0 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 9 | 78 |
| hybrid, alan | 9 | 9 | 0 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 0 | 12 |
| demo, linus | 9 | 2 | 0 | 7 | 7 ($343.00) | 6 runs, $343.00 | 0 | 0 | 3 | 5 | 84 |
| production, linus | 9 | 9 | 0 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 10 | 54 |
| hybrid, linus | 9 | 9 | 0 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 0 | 14 |
| demo, eve | 9 | 0 | 0 | 9 | 16 ($784.00) | 7 runs, $343.00 | 0 | 1 | 0 | 0 | 83 |
| production, eve | 9 | 0 | 0 | 9 | 0 ($0.00) | 9 runs, $441.00 | 0 | 0 | 0 | 18 | 83 |
| hybrid, eve | 9 | 9 | 0 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 9 | 14 |

### qwen3:8b by condition

| | Runs | Handled right | Handed to a person | Mistakes | Refunds without approval | Money refunded beyond need | Duplicate replies | Untrue replies | No reply | Operator questions and cards | s/run |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| demo, clean | 18 | 4 | 0 | 14 | 23 ($1,127.00) | 11 runs, $833.00 | 1 | 0 | 1 | 4 | 81 |
| production, clean | 18 | 14 | 0 | 4 | 0 ($0.00) | 3 runs, $147.00 | 0 | 0 | 1 | 26 | 72 |
| hybrid, clean | 18 | 18 | 0 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 9 | 15 |
| demo, lost_response | 18 | 0 | 0 | 18 | 24 ($1,176.00) | 14 runs, $942.00 | 2 | 1 | 3 | 11 | 98 |
| production, lost_response | 18 | 14 | 0 | 4 | 0 ($0.00) | 3 runs, $147.00 | 0 | 0 | 1 | 25 | 72 |
| hybrid, lost_response | 18 | 18 | 0 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 9 | 12 |
| demo, rate_limit | 18 | 11 | 0 | 7 | 10 ($490.00) | 4 runs, $343.00 | 2 | 1 | 2 | 12 | 95 |
| production, rate_limit | 18 | 14 | 0 | 4 | 0 ($0.00) | 3 runs, $147.00 | 0 | 0 | 1 | 25 | 74 |
| hybrid, rate_limit | 18 | 18 | 0 | 0 | 0 ($0.00) | 0 runs, $0.00 | 0 | 0 | 0 | 9 | 13 |
