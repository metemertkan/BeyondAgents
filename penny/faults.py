"""The bad day: faults injected in the network between the executor and the APIs.

Both executors get the same faults; only how they react differs.

- "clean":          nothing goes wrong
- "lost_response":  the first write reaches the API and succeeds, then its response is lost
                    (the caller sees a read timeout and can't know whether it worked)
- "rate_limit":     the first write is refused with 429 and Retry-After: 1, before it reaches the API
"""
from __future__ import annotations

import httpx

CONDITIONS = ("clean", "lost_response", "rate_limit")


class FaultyTransport(httpx.BaseTransport):
    def __init__(self, condition: str, inner: httpx.BaseTransport | None = None):
        if condition not in CONDITIONS:
            raise ValueError(f"unknown condition {condition!r}")
        self.condition = condition
        self.inner = inner or httpx.HTTPTransport()
        self.fired = False

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        is_write = request.method == "POST"
        if is_write and not self.fired and self.condition == "rate_limit":
            self.fired = True
            return httpx.Response(429, headers={"Retry-After": "1"}, request=request,
                                  json={"error": {"type": "rate_limit_error", "code": "rate_limit",
                                                  "message": "Too many requests. Retry after 1 second."}})
        response = self.inner.handle_request(request)
        if is_write and not self.fired and self.condition == "lost_response":
            response.read()
            if response.status_code < 400:
                self.fired = True
                response.close()
                raise httpx.ReadTimeout("The read operation timed out", request=request)
        return response

    def close(self) -> None:
        self.inner.close()
