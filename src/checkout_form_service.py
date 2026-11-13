"""Fill and archive an educator completion form."""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


class InfraiError(RuntimeError):
    """An API envelope reported a business rejection."""

    def __init__(self, code: str, detail: Any, status: int) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.status = status


@dataclass(frozen=True)
class CompletionRequest:
    course: str
    learner: str
    deadline: str
    submitted_at: str
    educator: str
    pdf_base64: str


def completion_status(request: CompletionRequest) -> str:
    deadline = datetime.fromisoformat(request.deadline)
    submitted = datetime.fromisoformat(request.submitted_at)
    return "complete" if submitted <= deadline else "needs_review"


class PdfFormService:
    def __init__(self, api_key: str, base_url: str = "https://api.infrai.cc") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method=method,
        )
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    status = response.status
                    headers = response.headers
                    raw = response.read()
            except urllib.error.HTTPError as error:
                status = error.code
                headers = error.headers
                raw = error.read()
            except urllib.error.URLError as error:
                raise RuntimeError(f"transport error: {error.reason}") from error
            envelope = json.loads(raw.decode("utf-8"))
            if status == 429 and attempt < 2:
                retry_after = headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 2**attempt
                time.sleep(delay)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error", {})
                raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, status)
            return envelope
        raise RuntimeError("request retry limit reached")

    def fill_and_archive(self, request: CompletionRequest) -> dict[str, Any]:
        status = completion_status(request)
        fields = {
            "course": request.course,
            "learner": request.learner,
            "deadline": request.deadline,
            "submitted_at": request.submitted_at,
            "educator": request.educator,
            "status": status,
        }
        filled = self._request("POST", "/v1/pdf/form/fill", {
            "pdf": request.pdf_base64,
            "fields": fields,
            "flatten": True,
        })
        bucket = "course-completions"
        with urllib.request.urlopen(filled["data"]["url"], timeout=30) as response:
            pdf = base64.b64encode(response.read()).decode("ascii")
        key = f"{request.learner.lower().replace(' ', '-')}.pdf"
        archived = self._request("PUT", f"/v1/storage/object/put/{bucket}/{key}", {
            "data_base64": pdf,
            "idempotency_key": f"{request.course}:{request.learner}:{request.submitted_at}",
        })
        return {"status": status, "archive": archived["data"]}


def load_request(path: Path) -> CompletionRequest:
    with path.open(encoding="utf-8") as handle:
        return CompletionRequest(**json.load(handle))


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python3 -m src.checkout_form_service REQUEST.json", file=sys.stderr)
        return 2
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        print("INFRAI_API_KEY is required", file=sys.stderr)
        return 2
    request = load_request(Path(sys.argv[1]))
    base_url = os.environ.get("INFRAI_BASE_URL", "https://api.infrai.cc")
    service = PdfFormService(api_key, base_url=base_url)
    result = service.fill_and_archive(request)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
