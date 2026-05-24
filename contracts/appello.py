# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import json
import typing


class Appello(gl.Contract):
    cases_json: str
    stakes_json: str

    def __init__(self) -> None:
        self.cases_json = "[]"
        self.stakes_json = "{}"

    def _load(self) -> list:
        return json.loads(self.cases_json)

    def _save(self, cases: list) -> None:
        self.cases_json = json.dumps(cases)

    def _load_stakes(self) -> dict:
        return json.loads(self.stakes_json)

    def _save_stakes(self, stakes: dict) -> None:
        self.stakes_json = json.dumps(stakes)

    @gl.public.write
    def submit_case(self, title: str, body: str) -> dict[str, typing.Any]:
        if not title.strip():
            raise gl.vm.UserError("Title is required")
        if not body.strip():
            raise gl.vm.UserError("Body is required")

        cases = self._load()
        idx = len(cases)

        cases.append({
            "id": idx,
            "submitter": gl.message.sender_address.as_hex,
            "title": title.strip()[:200],
            "body": body.strip()[:1000],
            "status": "OPEN",
            "verdict": "",
            "reasoning": "",
            "appeal": "",
            "final_verdict": ""
        })

        self._save(cases)
        return {"case_id": idx, "status": "OPEN"}

    @gl.public.write
    def judge_case(self, case_id: int) -> dict[str, typing.Any]:
        cases = self._load()
        if case_id < 0 or case_id >= len(cases):
            raise gl.vm.UserError("Case not found")

        case = cases[case_id]
        if case["status"] != "OPEN":
            raise gl.vm.UserError("Case is not open")

        _title = case["title"]
        _body = case["body"]

        def get_verdict() -> str:
            prompt = f"""You are an impartial judge. Read the following dispute case and deliver a verdict.

Case Title: {_title}
Case Details: {_body}

Respond with ONLY this JSON, no markdown, no explanation:
{{
    "verdict": "CLAIMANT_WINS" or "RESPONDENT_WINS" or "INSUFFICIENT_EVIDENCE",
    "reasoning": "your reasoning in 2-3 sentences"
}}

Output must be valid JSON only."""
            return gl.nondet.exec_prompt(prompt).replace("```json", "").replace("```", "").strip()

        raw = gl.eq_principle.prompt_comparative(
            get_verdict,
            "The 'verdict' field must be identical across all responses. Ignore any differences in the 'reasoning' field — wording may vary."
        )

        try:
            result = json.loads(raw)
        except json.JSONDecodeError as e:
            raise gl.vm.UserError(f"LLM did not return valid JSON: {e}")

        verdict = str(result.get("verdict", "INSUFFICIENT_EVIDENCE"))
        reasoning = str(result.get("reasoning", ""))

        if verdict not in ("CLAIMANT_WINS", "RESPONDENT_WINS", "INSUFFICIENT_EVIDENCE"):
            verdict = "INSUFFICIENT_EVIDENCE"

        case["verdict"] = verdict
        case["reasoning"] = reasoning
        case["status"] = "JUDGED"
        cases[case_id] = case
        self._save(cases)

        return {
            "case_id": case_id,
            "verdict": verdict,
            "reasoning": reasoning,
            "status": "JUDGED"
        }

    @gl.public.write
    def appeal_case(self, case_id: int, counter_argument: str) -> dict[str, typing.Any]:
        if not counter_argument.strip():
            raise gl.vm.UserError("Counter argument is required")

        cases = self._load()
        if case_id < 0 or case_id >= len(cases):
            raise gl.vm.UserError("Case not found")

        case = cases[case_id]
        if case["status"] != "JUDGED":
            raise gl.vm.UserError("Case is not in JUDGED status")

        if case["appeal"]:
            raise gl.vm.UserError("Appeal already filed for this case")

        appellant = gl.message.sender_address.as_hex

        stakes = self._load_stakes()
        stake_key = str(case_id)
        stakes[stake_key] = {
            "appellant": appellant,
            "amount": 100
        }
        self._save_stakes(stakes)

        case["appeal"] = counter_argument.strip()[:2000]
        case["status"] = "APPEALED"
        cases[case_id] = case
        self._save(cases)

        return {
            "case_id": case_id,
            "status": "APPEALED",
            "appellant": appellant,
            "stake_locked": 100
        }

    @gl.public.write
    def final_verdict(self, case_id: int) -> dict[str, typing.Any]:
        cases = self._load()
        if case_id < 0 or case_id >= len(cases):
            raise gl.vm.UserError("Case not found")

        case = cases[case_id]
        if case["status"] != "APPEALED":
            raise gl.vm.UserError("Case is not in APPEALED status")

        _title = case["title"]
        _body = case["body"]
        _first_verdict = case["verdict"]
        _first_reasoning = case["reasoning"]
        _appeal = case["appeal"]

        def get_final_verdict() -> str:
            prompt = f"""You are a senior appellate judge reviewing a dispute case.

ORIGINAL CASE
Title: {_title}
Details: {_body}

FIRST VERDICT
Decision: {_first_verdict}
Reasoning: {_first_reasoning}

APPEAL
Counter-argument submitted by the losing party: {_appeal}

Your task: Review all of the above and deliver a final binding verdict.
Consider whether the appeal counter-argument raises valid points that
justify overturning the first verdict.

Respond with ONLY this JSON, no markdown, no explanation:
{{
    "final_verdict": "CLAIMANT_WINS" or "RESPONDENT_WINS" or "INSUFFICIENT_EVIDENCE",
    "reasoning": "your final reasoning in 2-3 sentences",
    "overturned": true or false
}}

Output must be valid JSON only."""
            return gl.nondet.exec_prompt(prompt).replace("```json", "").replace("```", "").strip()

        raw = gl.eq_principle.prompt_comparative(
            get_final_verdict,
            "The 'final_verdict' field and 'overturned' boolean must be identical across all responses. Ignore differences in 'reasoning' field — wording may vary."
        )

        try:
            result = json.loads(raw)
        except json.JSONDecodeError as e:
            raise gl.vm.UserError(f"LLM did not return valid JSON: {e}")

        fv = str(result.get("final_verdict", "INSUFFICIENT_EVIDENCE"))
        reasoning = str(result.get("reasoning", ""))
        overturned = bool(result.get("overturned", False))

        if fv not in ("CLAIMANT_WINS", "RESPONDENT_WINS", "INSUFFICIENT_EVIDENCE"):
            fv = "INSUFFICIENT_EVIDENCE"

        stakes = self._load_stakes()
        stake_key = str(case_id)
        stake_returned = False
        if stake_key in stakes:
            if overturned:
                stake_returned = True
            stakes.pop(stake_key)
        self._save_stakes(stakes)

        case["final_verdict"] = fv
        case["reasoning"] = reasoning
        case["status"] = "FINAL"
        cases[case_id] = case
        self._save(cases)

        return {
            "case_id": case_id,
            "final_verdict": fv,
            "reasoning": reasoning,
            "overturned": overturned,
            "stake_returned": stake_returned,
            "status": "FINAL"
        }

    @gl.public.view
    def get_case_count(self) -> int:
        return len(self._load())

    @gl.public.view
    def get_all_cases(self) -> str:
        return self.cases_json

    @gl.public.view
    def get_case(self, case_id: int) -> dict[str, typing.Any]:
        cases = self._load()
        if case_id < 0 or case_id >= len(cases):
            raise gl.vm.UserError("Case not found")
        return cases[case_id]

    @gl.public.view
    def get_cases_by_status(self, status: str) -> str:
        s = status.strip().upper()
        if s not in ("OPEN", "JUDGED", "APPEALED", "FINAL"):
            raise gl.vm.UserError("status must be OPEN, JUDGED, APPEALED, or FINAL")
        return json.dumps([c for c in self._load() if c["status"] == s])

    @gl.public.view
    def get_stake(self, case_id: int) -> dict[str, typing.Any]:
        cases = self._load()
        if case_id < 0 or case_id >= len(cases):
            raise gl.vm.UserError("Case not found")
        stakes = self._load_stakes()
        stake_key = str(case_id)
        if stake_key not in stakes:
            return {
                "case_id": case_id,
                "staked": False,
                "appellant": "",
                "amount": 0
            }
        s = stakes[stake_key]
        return {
            "case_id": case_id,
            "staked": True,
            "appellant": str(s["appellant"]),
            "amount": int(s["amount"])
        }