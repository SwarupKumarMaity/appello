# Appello — Multi-Round Appeal Verdict System on GenLayer

A GenLayer Intelligent Contract implementing a dispute resolution system with a built-in appeal phase. The core novelty is that the second consensus round consumes **new input** — it is not a re-run of the same prompt.

## What Appello Does

Appello is a verdict system where any dispute can be submitted, judged by LLM consensus, appealed with a counter-argument, and finally re-judged in a second independent consensus round that can overturn the first verdict.

## State Machine

OPEN → JUDGED → APPEALED → FINAL

| Status | Trigger | Description |
|--------|---------|-------------|
| `OPEN` | `submit_case` | Case submitted, awaiting judgment |
| `JUDGED` | `judge_case` | First LLM consensus verdict delivered |
| `APPEALED` | `appeal_case` | Losing side appeals with counter-argument, stake locked |
| `FINAL` | `final_verdict` | Second LLM consensus re-judges with new input |

## Flow

1. **Submit** — user submits a case (title + body). Status: `OPEN`
2. **Judge** — LLM consensus reads the case and delivers a verdict (`CLAIMANT_WINS` / `RESPONDENT_WINS` / `INSUFFICIENT_EVIDENCE`) plus reasoning. Status: `JUDGED`
3. **Appeal** — losing side appeals once, supplying a counter-argument (new context not present in round 1). Stake of 100 units locked. Status: `APPEALED`
4. **Final Verdict** — a fresh consensus round re-judges using:
   - Original case
   - First verdict + reasoning
   - New counter-argument

   Can overturn or uphold. Status: `FINAL`
   - Appeal succeeds (overturned) → stake returned
   - Appeal fails (upheld) → stake forfeited

## Why This Design

### Multi-round consensus where round 2 ingests new input
This is distinct from a simple re-run. The appellate LLM sees information that did not exist in round 1 (the counter-argument), making the second round genuinely independent and additive. This aligns with what GenLayer's Bradbury testnet stress-tests: adversarial and multi-round appeal scenarios.

### Stake-forfeit logic
Game-theoretic answer to frivolous appeals. If the appeal fails, the stake is forfeited. This discourages parties from appealing without genuine grounds.

### One appeal maximum
Prevents exploitation loops and preserves finality. Once a case reaches `FINAL` status it cannot be re-opened.

### Full audit trail on-chain
Every stage — original case, first verdict, reasoning, counter-argument, final verdict — is stored on-chain and queryable via view methods.

## Contract Methods

### Write Methods

| Method | Description |
|--------|-------------|
| `submit_case(title, body)` | Submit a new dispute case |
| `judge_case(case_id)` | Trigger first LLM consensus verdict |
| `appeal_case(case_id, counter_argument)` | File appeal with counter-argument |
| `final_verdict(case_id)` | Trigger second LLM consensus verdict |

### Read Methods

| Method | Description |
|--------|-------------|
| `get_case(case_id)` | Get full case details |
| `get_all_cases()` | Get all cases as JSON string |
| `get_case_count()` | Get total number of cases |
| `get_cases_by_status(status)` | Filter cases by status |
| `get_stake(case_id)` | Check stake status for a case |

## GenLayer Technical Notes

- Contract uses `gl.eq_principle.prompt_comparative` for both consensus rounds with explicit criteria strings that tell validators which fields must match and which to ignore
- LLM closure does not capture `self` — all needed state is rebound to local variables before the closure
- Storage uses JSON-serialized strings (`cases_json`, `stakes_json`) since GenLayer storage does not support `list`, `dict`, or `float` field types directly
- All LLM output is stripped of markdown and type-coerced at the boundary before storing to avoid calldata encoding failures

## Known Limitations (Out of Scope — Not Bugs)

These are intentional prototype constraints, not defects:

| Limitation | Notes |
|------------|-------|
| **Evidence authenticity** | Submitted text is unverified — anyone can claim anything |
| **Real-world enforcement** | Contract verdicts have no legal standing or enforcement mechanism |
| **Legal/regulatory standing** | Not a substitute for formal arbitration or court proceedings |
| **AI inconsistency** | LLM outputs may vary across reruns; consensus mitigates but does not eliminate this |
| **Prompt manipulation** | Submitted case text could attempt to manipulate the LLM verdict |
| **Stake is symbolic** | The 100-unit stake does not involve real token transfers in this prototype |
| **Single appeal only** | By design — prevents loops, but means one bad appeal exhausts the right |

## Project Structure
appello/
└── contracts/
    └── appello.py    ← Intelligent Contract

## Deployment

Deployed and tested on GenLayer Studionet.

Built using GenLayer Studio at [studio.genlayer.com](https://studio.genlayer.com)

## Relationship to Prior Work

This is my second GenLayer Intelligent Contract. My first, **Predikt** (SignalJudge), is a two-phase crypto trading signal evaluator using live web-fetch + LLM consensus. Appello is a separate contribution focused on multi-round appeal mechanics rather than data sourcing.

## Author

Built as a GenLayer ecosystem contribution for the Bradbury testnet contributor program.