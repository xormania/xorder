import copy
import importlib.util
import io
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("failure_triage", ROOT / "examples/jev/failure_triage.py")
jev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jev)


class FakeOpener:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        return io.BytesIO(json.dumps(self.response).encode())


class JevTriageTests(unittest.TestCase):
    def setUp(self):
        self.env = {"TYPESAFE_API_KEY": "private-provider-key", "OTHER_TOKEN": "private-log-token"}
        self.receipt = {"exit_code": 1, "started_at": "2026-10-11T02:00:00Z",
                        "host_start": {"load": 17, "cpus": 4},
                        "resolved_projects": [{"name": "webkit", "base_url": "https://php"}],
                        "diagnostic_context": {"test_output": "assertion failed private-log-token",
                                               "server_logs": "password=server-password Authorization: Bearer header-secret"}}
        criteria = jev.questions(self.env)["failure_cause"]["criteria"]
        self.response = {"model": "jev-1.13.0", "answers": {"failure_cause": {
            "type": "choice", "choice": "application", "confidence": 0.7,
            "probabilities": {name: 1.0 if name == "application" else 0.0 for name in criteria}}}}

    def test_primary_api_shape_redaction_and_structured_advisory(self):
        opener = FakeOpener(self.response)
        result = jev.triage(self.receipt, self.env, opener)
        request, timeout = opener.calls[0]
        self.assertEqual(request.full_url, "https://api.typesafe.ai/v1/systemone")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer private-provider-key")
        self.assertEqual(timeout, 15)
        payload = json.loads(request.data)
        self.assertEqual(set(payload), {"state", "model", "questions"})
        self.assertEqual(payload["model"], "jev-latest")
        for secret in ("private-log-token", "server-password", "header-secret", "private-provider-key"):
            self.assertNotIn(secret, json.dumps(payload["state"]))
            self.assertNotIn(secret, json.dumps(result))
        self.assertEqual(result["model"], self.response["model"])
        self.assertTrue(result["advisory"])
        self.assertEqual(result["answers"], self.response["answers"])
        self.assertIn("2026-10-11T02:00:00Z", json.dumps(payload["state"]))
        state = payload["state"]
        self.assertEqual(state["attempt"]["host_start"], {"load": 17, "cpus": 4})
        self.assertEqual(state["attempt"]["resolved_projects"], self.receipt["resolved_projects"])

    def test_missing_key_does_not_contact_provider(self):
        opener = FakeOpener(self.response)
        self.assertEqual(jev.triage(self.receipt, {}, opener)["status"], "unavailable")
        self.assertEqual(opener.calls, [])

    def test_invalid_provider_answers_are_rejected(self):
        for mutation in ("missing", "unknown_choice", "nan", "incomplete"):
            with self.subTest(mutation=mutation):
                response = copy.deepcopy(self.response)
                answer = response["answers"]["failure_cause"]
                if mutation == "missing": response["answers"] = {}
                elif mutation == "unknown_choice": answer["choice"] = "invented"
                elif mutation == "nan": answer["confidence"] = float("nan")
                elif mutation == "incomplete": answer["probabilities"] = {"application": 1}
                with self.assertRaises(ValueError):
                    jev.triage(self.receipt, self.env, FakeOpener(response))

    def test_authentication_cannot_follow_a_redirect(self):
        with self.assertRaises(jev.HTTPError):
            jev.NoRedirect().redirect_request(NoneRequest(), None, 302, "redirect", {}, "https://other.example")


class NoneRequest:
    full_url = jev.ENDPOINT
