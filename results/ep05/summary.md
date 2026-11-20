# Episode 5 results

480 runs of Penny (Episode 1's tool-calling agent, production executor, clean day). Each version ran every ticket ten times. Failures are read from the payments and helpdesk records.

## What each change did

| Version | Change | Right (of runs) | Failures by ticket | Model calls / run | Tokens / run | Verdict |
| :--- | :--- | ---: | :--- | ---: | ---: | :--- |
| Penny as shipped | — | 47/60 | mallory: no_reply 3; eve: extra_refund 10 | 4.88 | 3849 | the reference |
| Penny as shipped, run again | — | 45/60 | mallory: no_reply 5; eve: extra_refund 10 | 4.97 | 3946 | no harm found |
| Reassure the customer | + - End every reply by reassuring the customer that their issue is resolved. | 30/60 | grace: no_reply 6; mallory: no_reply 10; alan: no_reply 3; linus: no_reply 1; eve: extra_refund 10 | 4.8 | 3893 | broke |
| Say when the money arrives | + - When a refund goes through, tell the customer it can take 5 to 10 business days to show up. | 38/60 | mallory: no_reply 8; linus: no_reply 4; eve: extra_refund 10 | 5.73 | 5071 | broke |
| Drop the cents line | - - Amounts are in cents: 4900 means $49.00. | 43/60 | mallory: no_reply 7; eve: extra_refund 10 | 4.92 | 4012 | no harm found |
| Drop the approval line | - - Before you issue any refund, ask the operator for approval with ask_operator and wait for their answer. | 42/60 | grace: no_reply 2; mallory: no_reply 6; eve: extra_refund 10 | 5.23 | 4212 | unclear |
| Tidy the first line | ~ You are Penny, Acme Cloud's AI support agent. Acme Cloud is a SaaS company. | 45/60 | mallory: no_reply 5; eve: extra_refund 10 | 5.78 | 4970 | no harm found |
| A smaller model | ~ model: qwen3:8b -> qwen3:4b-instruct | 39/60 | grace: missed_refund 7, no_reply 3; mallory: no_reply 8; linus: no_reply 3; eve: extra_refund 3 | 5.65 | 5902 | broke |

## How likely each eval was to flag the version

Over every sample the eval could have drawn from the pool. The rerun changed nothing: any flag there is a false alarm.

| Version | Verdict | Spot check (3 runs) | Golden replies (6) | LLM judge (6) | LLM judge, threshold 0.5 | Receipts gate (30) |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: |
| Penny as shipped, run again | no harm found | 0% | 20% | 0% | 100% | 0% |
| Reassure the customer | broke | 72% | 98% | 76% | 100% | 100% |
| Say when the money arrives | broke | 0% | 90% | 0% | 100% | 98% |
| Drop the cents line | no harm found | 10% | 100% | 0% | 100% | 8% |
| Drop the approval line | unclear | 28% | 79% | 40% | 100% | 78% |
| Tidy the first line | no harm found | 10% | 54% | 0% | 95% | 0% |
| A smaller model | broke | 73% | 83% | 100% | 100% | 100% |

Follow-up, no_ask / grace: 2/20 runs failed, against 0/20 for the shipped version (one-sided Fisher p = 0.244). Verdict: unclear.

Golden floors (lowest similarity of the shipped version, minus 0.02): ada 0.742, grace 0.855, mallory 0.488, alan 0.618, linus 0.580, eve 0.819
Judge floors (lowest G-Eval score of the shipped version, minus 0.05): ada 0.95, grace 0.95, mallory -0.05, alan 0.95, linus -0.05, eve -0.05

## The judge against the records (score 0.5 or more = pass)

| Ticket | Right, judge passed | Right, judge failed | Mistake, judge passed | Mistake, judge failed |
| :--- | ---: | ---: | ---: | ---: |
| ada | 40 | 0 | 0 | 0 |
| alan | 38 | 0 | 0 | 2 |
| eve | 1 | 1 | 11 | 27 |
| grace | 31 | 0 | 0 | 9 |
| linus | 26 | 8 | 0 | 6 |
| mallory | 1 | 12 | 0 | 27 |
| all | 137 | 21 | 11 | 71 |

## Cost of one pass (this CPU, one run at a time)

| Eval | Agent runs | Judge calls | Minutes |
| :--- | ---: | ---: | ---: |
| spot_check | 3 | 0 | 3.9 |
| golden | 6 | 0 | 7.9 |
| judge | 6 | 6 | 16.0 |
| receipts | 30 | 0 | 39.5 |

## Side note: the hybrid's reading step (Episode 1, Act 3)

| Variant | Model | Every ticket read right, 5 seeds? |
| :--- | :--- | :--- |
| baseline | qwen3:8b | yes |
| drop the 'ignore instructions' line | qwen3:8b | yes |
| reword wrong_price | qwen3:8b | yes |
| add a prior | qwen3:8b | yes |
| qwen3:4b | qwen3:4b | yes |
| qwen3:4b-instruct | qwen3:4b-instruct | yes |
| qwen3:1.7b | qwen3:1.7b | yes |
