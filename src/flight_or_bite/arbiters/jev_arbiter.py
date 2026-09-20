"""JevArbiter (SPEC §4.3): one Choice question over EAT / ESCAPE / IDLE, three state modes."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any, Literal

import httpx
import yaml
from pydantic import BaseModel, ConfigDict

from flight_or_bite.arbiters.base import ACTIONS, TimedArbiter
from flight_or_bite.arbiters.jev_client import (
    ChoiceQuestion,
    JevClientProtocol,
    JevHTTPError,
    JevResponseError,
)
from flight_or_bite.types import Action, Observation

PROMPT_DIR = Path("configs/jev_prompts")
MODES = ("naive", "informed", "bucketed", "informed_bucketed")
QUESTION_ID = "action"
FIELDS = ("sugar", "bitter", "looming", "hunger")


class JevPrompt(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: Literal["naive", "informed", "bucketed", "informed_bucketed"]
    version: str
    instructions: str
    criteria: dict[str, str | None]
    decimals: int = 2
    rules: str | None = None
    buckets: list[tuple[float, str]] | None = None
    zero_label: str | None = None

    def question(self) -> ChoiceQuestion:
        if set(self.criteria) != {a.value for a in ACTIONS}:
            raise ValueError(f"criteria must name exactly {[a.value for a in ACTIONS]}")
        return ChoiceQuestion(self.full_instructions, self.criteria)

    @property
    def full_instructions(self) -> str:
        """Rules, when the mode has them, go into `instructions` before the question (D46)."""
        return f"{self.rules.strip()}\n\n{self.instructions}" if self.rules else self.instructions

    def level(self, value: float) -> str:
        assert self.buckets is not None
        if value == 0 and self.zero_label is not None:
            return self.zero_label
        return next((name for upper, name in self.buckets if value < upper), self.buckets[-1][1])

    def state(self, obs: Observation) -> dict[str, Any]:
        values = {f: getattr(obs, f) for f in FIELDS}
        if self.buckets is not None:
            return {f: self.level(v) for f, v in values.items()}
        return {f: round(v, self.decimals) for f, v in values.items()}

    def state_key(self, obs: Observation) -> tuple:
        """Observations with the same key produce byte-identical requests (bucketed modes)."""
        return tuple(self.state(obs).values())


def load_prompt(mode: str, directory: Path = PROMPT_DIR) -> JevPrompt:
    prompt = JevPrompt.model_validate(yaml.safe_load((directory / f"{mode}.yaml").read_text()))
    if prompt.mode != mode:
        raise ValueError(f"{mode}.yaml declares mode {prompt.mode!r}")
    if ("informed" in prompt.mode) != bool(prompt.rules):
        raise ValueError(f"`rules` must be present exactly in the informed modes ({mode})")
    if ("bucketed" in prompt.mode) != bool(prompt.buckets):
        raise ValueError(f"`buckets` must be present exactly in the bucketed modes ({mode})")
    return prompt


def prompt_hash(mode: str, directory: Path = PROMPT_DIR) -> str:
    """SHA-256 of the template file, for PREREG.md (SPEC §8)."""
    return hashlib.sha256((directory / f"{mode}.yaml").read_bytes()).hexdigest()


class JevArbiter(TimedArbiter):
    """t_wall covers building the request, the HTTP exchange, parsing and sampling."""

    RETRYABLE = frozenset({429, 500, 502, 503, 524, 529})

    def __init__(self, client: JevClientProtocol, prompt: JevPrompt, *, retries: int = 0) -> None:
        """`retries` > 0 is for long unattended runs (tables, episodes). A retried decision is
        flagged `retried` and must never enter latency statistics; timing runs use retries = 0."""
        self.client = client
        self.prompt = prompt
        self.retries = retries
        self.name = f"jev_{prompt.mode}"
        self._question = prompt.question()

    def policy(self, obs: Observation) -> tuple[dict[Action, float], dict[str, Any]]:
        response, attempts = None, 0
        while response is None:
            try:
                response = self.client.evaluate(
                    self.prompt.state(obs), {QUESTION_ID: self._question}
                )
            except (JevHTTPError, httpx.TransportError) as e:
                status = getattr(e, "status", None)
                if attempts >= self.retries or (
                    status is not None and status not in self.RETRYABLE
                ):
                    raise
                attempts += 1
                time.sleep(min(30.0, 2.0**attempts))
        answer = response.choice(QUESTION_ID)
        if set(answer.probabilities) != {a.value for a in ACTIONS}:
            raise JevResponseError(f"unexpected options in the answer: {answer.probabilities}")
        total = sum(answer.probabilities.values())
        if total <= 0:
            raise JevResponseError(f"probabilities sum to {total}")
        probs = {a: answer.probabilities[a.value] / total for a in ACTIONS}
        return probs, {
            "native_action": Action(answer.choice),  # D27: Jev acts with its own `choice`
            "retried": attempts,
            "mode": self.prompt.mode, "prompt_version": self.prompt.version,
            "model_version": response.model, "generation_id": response.request_id,
            "cache_hit": response.cache_hit, "raw_probability_sum": total,
            "t_http_ns": response.t_wall_ns, "cost_usd": response.meta.get("cost_usd"),
        }  # fmt: skip
