# Sample traces: what one request leaves behind

Five real requests, captured live on 2026-11-01 from the running API (`gpt-5`, reasoning effort low). For each: the **step timeline** the server streams as it works, the **`meta`** block returned with every response (model, tokens, cost, latency, prompt versions, what the guards did), and the **claims with their citations**.

How to read the timeline: each row is a graph step, stamped with the seconds since the request started when it *finished*, so "Took" is that step's own duration. `LLM` steps are model calls, `tool` steps call a supplied tool, `rules` is the deterministic policy engine.

**About trace ids.** Every response carries `meta.trace_id`, and each LLM call is recorded as a LangSmith span. These captures ran with tracing off, so `trace_id` is `null`. In the one run with tracing on, uploads to LangSmith returned `403 Forbidden` with the key available, so no trace has been viewed there. Tokens, cost and latency do not depend on LangSmith: they are in every response and in the eval reports. See the README ("What I would not trust").

| # | Request (customer) | What it shows | Total | Tokens in / out | Cost |
|---|---|---|---|---|---|
| 1 | Hi (CUST-2007) | no model call at all | 0.0 s | 0 / 0 | $0.0000 |
| 2 | Who is the Prime Minister of India? (CUST-2007) | scope gate: one small model call, no account lookup, no human review | 4.2 s | 767 / 30 | $0.0013 |
| 3 | Markup in Singapore? (CUST-2007) | a grounded, cited answer | 9.9 s | 3,497 / 547 | $0.0098 |
| 4 | A card used at a shop I never visited (CUST-2002) | a tool call that raises a request | 19.2 s | 3,623 / 1,486 | $0.0194 |
| 5 | Increase my limit to 3 lakh (CUST-2003) | the rules engine decides; the model only explains | 17.4 s | 3,806 / 1,265 | $0.0174 |

## 1. No model call at all

**Customer CUST-2007:** "Hi"

| Step | Kind | Done at (s) | Took (s) |
|---|---|---|---|
| `input_guard` | logic | 0.04 | 0.04 |
| `short_circuit` | logic | 0.04 | 0.00 |

| | |
|---|---|
| Behaviour | answer |
| Model | no model call |
| Tokens | 0 in, 0 out |
| Cost | $0.0000 |
| Latency | 0.0 s |
| Rules fired | none |
| Reason codes | none |
| Repaired / fallback model / safe fallback | False / False / False |
| Retrieval miss | False |
| Request raised | none |
| Prompts | classify@3+f837e3a5, generate@5+e18e45b5, repair@1+92a88c5c |

**Claims and citations**

_No factual claims: nothing to cite._

**Reply**

> Hello! I'm your card assistant. I can help with your credit limit, fees and charges, payments, disputes and how our card policies work. What would you like to know?


## 2. Scope gate: one small model call, no account lookup, no human review

**Customer CUST-2007:** "Who is the Prime Minister of India?"

| Step | Kind | Done at (s) | Took (s) |
|---|---|---|---|
| `input_guard` | logic | 0.01 | 0.01 |
| `classify` | LLM | 4.18 | 4.17 |
| `short_circuit` | logic | 4.19 | 0.01 |

| | |
|---|---|
| Behaviour | refuse |
| Model | no model call |
| Tokens | 767 in, 30 out |
| Cost | $0.0013 |
| Latency | 4.2 s |
| Rules fired | none |
| Reason codes | none |
| Repaired / fallback model / safe fallback | False / False / False |
| Retrieval miss | False |
| Request raised | none |
| Prompts | classify@3+f837e3a5, generate@5+e18e45b5, repair@1+92a88c5c |

**Claims and citations**

_No factual claims: nothing to cite._

**Reply**

> I can only help with questions about your card, credit and payments, so I can't help with that one. I'm glad to help with things like your credit limit, fees, a payment you don't recognise or how our card policies work.


## 3. A grounded, cited answer

**Customer CUST-2007:** "What is the markup if I use my card in Singapore?"

| Step | Kind | Done at (s) | Took (s) |
|---|---|---|---|
| `input_guard` | logic | 0.01 | 0.01 |
| `classify` | LLM | 3.42 | 3.41 |
| `load_account` | tool | 4.08 | 0.66 |
| `retrieve` | retrieval | 4.08 | 0.00 |
| `policy` | rules | 4.08 | 0.00 |
| `generate` | LLM | 9.89 | 5.81 |
| `validate` | logic | 9.89 | 0.00 |
| `act` | tool | 9.89 | 0.00 |

| | |
|---|---|
| Behaviour | answer |
| Model | openai:gpt-5-2025-08-07 |
| Tokens | 3,497 in, 547 out |
| Cost | $0.0098 |
| Latency | 9.9 s |
| Rules fired | FEE_WAIVER_MET |
| Reason codes | none |
| Repaired / fallback model / safe fallback | False / False / False |
| Retrieval miss | False |
| Request raised | none |
| Prompts | classify@3+f837e3a5, generate@5+e18e45b5, repair@1+92a88c5c |

**Claims and citations**

- The foreign currency markup is 3.5%. → `POL-FEE-007#body`

**Reply**

> The foreign currency markup on your card is **3.5%**.
>
> This is the standard foreign currency markup listed in the Fees and Charges Schedule for your card.


## 4. A tool call that raises a request

**Customer CUST-2002:** "Someone used my card at a shop I have never been to."

| Step | Kind | Done at (s) | Took (s) |
|---|---|---|---|
| `input_guard` | logic | 0.01 | 0.01 |
| `classify` | LLM | 2.37 | 2.36 |
| `load_account` | tool | 2.79 | 0.42 |
| `retrieve` | retrieval | 2.79 | 0.00 |
| `policy` | rules | 2.79 | 0.00 |
| `generate` | LLM | 19.25 | 16.46 |
| `validate` | logic | 19.25 | 0.00 |
| `act` | tool | 19.25 | 0.00 |

| | |
|---|---|
| Behaviour | raise_request |
| Model | openai:gpt-5-2025-08-07 |
| Tokens | 3,623 in, 1,486 out |
| Cost | $0.0194 |
| Latency | 19.2 s |
| Rules fired | none |
| Reason codes | none |
| Repaired / fallback model / safe fallback | False / False / False |
| Retrieval miss | False |
| Request raised | SR-F951B343 to DISPUTES, SLA 16 h |
| Prompts | classify@3+f837e3a5, generate@5+e18e45b5, repair@1+92a88c5c |

**Claims and citations**

- The dispute has been sent to the disputes team who will start work within 2 working days. → `POL-SVC-006#body`
- Provisional credit is applied within 5 working days for card-present fraud claims and within 10 working days for other categories. → `POL-SVC-005#body`
- A dispute may be raised within 60 days of the statement on which the transaction appears. → `POL-SVC-005#body`
- While a dispute is open, no credit limit increase may be processed, the disputed amount is excluded from utilisation calculations, and the customer is contacted at least once every 15 days with a status update. → `POL-SVC-005#body`

**Reply**

> I’ve raised a dispute for that transaction and sent it to our disputes team, who will start work within **2 working days**.
>
> For refunds during investigation: if it was an in‑person (card‑present) fraud, a provisional credit is applied within **5 working days**; for all other cases it’s within **10 working days**.
>
> A dispute must be raised within **60 days** of the statement on which the transaction appears. While your dispute is open, we won’t process any credit limit increase on the account, the disputed amount won’t count towards your utilisation, and we’ll update you at least once every **15 days**.
>
> If you’d also like me to block and replace your card, tell me and I can submit that too.
>
> I've raised request SR-F951B343 (transaction dispute). You can expect an update within 2 working days.


## 5. The rules engine decides; the model only explains

**Customer CUST-2003:** "I want my credit limit increased to 3 lakh."

| Step | Kind | Done at (s) | Took (s) |
|---|---|---|---|
| `input_guard` | logic | 0.01 | 0.01 |
| `classify` | LLM | 2.67 | 2.66 |
| `load_account` | tool | 3.08 | 0.41 |
| `retrieve` | retrieval | 3.08 | 0.00 |
| `policy` | rules | 3.08 | 0.00 |
| `generate` | LLM | 17.37 | 14.29 |
| `validate` | logic | 17.37 | 0.00 |
| `act` | tool | 17.37 | 0.00 |

| | |
|---|---|
| Behaviour | decline_with_reason |
| Model | openai:gpt-5-2025-08-07 |
| Tokens | 3,806 in, 1,265 out |
| Cost | $0.0174 |
| Latency | 17.4 s |
| Rules fired | DECLINE_OPEN_DISPUTE |
| Reason codes | AA04 |
| Repaired / fallback model / safe fallback | False / False / False |
| Retrieval miss | False |
| Request raised | none |
| Prompts | classify@3+f837e3a5, generate@5+e18e45b5, repair@1+92a88c5c |

**Claims and citations**

- Your request is declined because there is an open dispute on your account. → `rule.DECLINE_OPEN_DISPUTE`, `account.open_dispute`, `POL-CRD-001#3`
- While a dispute is open, no credit limit increase may be processed. → `POL-SVC-005#body`

**Reply**

> I can’t approve a credit limit increase right now because there is an open dispute on your account.
>
> While a dispute is open, no credit limit increase can be processed under our policy. Once your dispute is resolved, you can ask us again.

## Reading across the five

- **The model is the cost and the time.** In the three requests that call it for generation, `generate` takes 5.8 s of 9.9 s, 16.5 s of 19.2 s and 14.3 s of 17.4 s (the rest is the classifier, about 2.4 to 3.4 s, and a 0.4 to 0.7 s account lookup). Everything the system does itself (retrieval, rules, validation) is well under a second.
- **The scope gate pays off.** The out-of-scope question cost $0.0013 and 4.2 s; the greeting cost nothing. Neither touched the account tool, retrieval or the rules.
- **Credit decisions do not depend on the model.** In request 5 the rule `DECLINE_OPEN_DISPUTE` fired and produced reason code `AA04` before the model wrote a word; the model's job was to explain it, and the validator checked that every claim traces to a rule or a policy chunk.
- **Per-turn cost is about a cent or two** for a real question (mean $0.017 over the 31 eval conversations).
