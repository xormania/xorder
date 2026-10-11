#!/usr/bin/env python3
"""Opt-in Jev candidate selection for a failed attempt's bounded receipt."""
import json
import math
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MAX_INPUT_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 256 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        raise HTTPError(request.full_url, code, "API redirects are unsupported", headers, fp)


def redact(text, env):
    values = {value for key, value in env.items() if len(value) >= 4 and
              re.search(r"KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL", key, re.I)}
    for value in sorted(values, key=len, reverse=True):
        text = text.replace(value, "[REDACTED]")
    text = re.sub(r"(?i)(authorization\s*[:=]\s*(?:bearer|basic)\s+)\S+", r"\1[REDACTED]", text)
    text = re.sub(r"(?i)((?:password|passwd|api[_-]?key|access[_-]?token|secret)\s*[:=]\s*)[^\s,;]+", r"\1[REDACTED]", text)
    return re.sub(r"(https?://)[^/\s:@]+:[^/\s@]+@", r"\1[REDACTED]@", text)


def redact_state(value, env):
    if isinstance(value, str):
        return redact(value, env)
    if isinstance(value, dict):
        return {key: redact_state(item, env) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_state(item, env) for item in value]
    return value


def questions(env):
    path = Path(env.get("XORDER_JEV_QUESTIONS", str(Path(__file__).with_name("failure-questions.json"))))
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or not value:
        raise ValueError("Jev questions must be a nonempty JSON object")
    for question in value.values():
        if not isinstance(question, dict) or question.get("type") != "choice" or not question.get("instructions"):
            raise ValueError("Failure triage questions must use the Choice request structure")
        criteria = question.get("criteria")
        if not isinstance(criteria, dict) or not 2 <= len(criteria) <= 255:
            raise ValueError("Each triage question needs 2 to 255 candidate descriptions")
    return value


def valid_probability(number):
    return isinstance(number, (float, int)) and not isinstance(number, bool) and 0 <= number <= 1 and math.isfinite(number)


def triage(receipt, env, opener=None):
    key = env.get("TYPESAFE_API_KEY")
    if not key:
        return {"status": "unavailable", "reason": "TYPESAFE_API_KEY is not set", "advisory": True}
    if not isinstance(receipt, dict) or not isinstance(receipt.get("diagnostic_context"), dict):
        raise ValueError("Run receipt must include diagnostic_context with bounded attempt logs")
    context = receipt["diagnostic_context"]
    if not isinstance(context.get("test_output"), str) or not isinstance(context.get("server_logs"), str):
        raise ValueError("diagnostic_context must include test_output and server_logs strings")
    selected = questions(env)
    metadata = {name: value for name, value in receipt.items()
                if name != "diagnostic_context" and not isinstance(value, (dict, list))}
    for name in ("requested_arguments", "effective_arguments", "host_start", "host_end",
                 "resolved_projects", "container_environment"):
        if name in receipt:
            metadata[name] = receipt[name]
    state = {"diagnostic_context": context, "attempt": metadata}
    payload = {"state": redact_state(state, env),
               "model": env.get("XORDER_JEV_MODEL") or "jev-latest", "questions": selected}
    request = Request(ENDPOINT, data=json.dumps(payload).encode("utf-8"), method="POST",
                      headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with (opener or build_opener(NoRedirect())).open(request, timeout=15) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("TypeSafe response exceeds the 256 KiB limit")
    response = json.loads(raw)
    if not isinstance(response, dict) or not isinstance(response.get("model"), str) or not isinstance(response.get("answers"), dict):
        raise ValueError("TypeSafe returned an invalid response structure")
    answers = {}
    for name, question in selected.items():
        answer = response["answers"].get(name)
        if not isinstance(answer, dict) or answer.get("type") != "choice" or answer.get("choice") not in question["criteria"]:
            raise ValueError("TypeSafe returned an invalid choice")
        confidence, probabilities = answer.get("confidence"), answer.get("probabilities")
        if (not valid_probability(confidence) or not isinstance(probabilities, dict)
                or set(probabilities) != set(question["criteria"])
                or any(not valid_probability(number) for number in probabilities.values())
                or not math.isclose(sum(probabilities.values()), 1, abs_tol=0.01)):
            raise ValueError("TypeSafe returned an invalid probability distribution")
        answers[name] = {"type": "choice", "choice": answer["choice"],
                         "confidence": confidence, "probabilities": probabilities}
    return {"status": "triaged", "advisory": True, "model": response["model"], "answers": answers}


def main():
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("Run receipt exceeds the 1 MiB input limit")
    return triage(json.loads(raw), dict(os.environ))


if __name__ == "__main__":
    try:
        result = main()
    except HTTPError as error:
        result = {"status": "unavailable", "advisory": True, "reason": f"TypeSafe HTTP request failed (status {error.code})"}
    except (OSError, URLError, ValueError, TypeError, RecursionError):
        result = {"status": "unavailable", "advisory": True, "reason": "Jev triage could not read its inputs or obtain a valid response"}
    print(json.dumps(result))
