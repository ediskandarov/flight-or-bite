"""LIF parameters of the Shiu et al. model, loaded from configs/lif.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, PositiveFloat


class LIFParams(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    connectome_version: int
    v_0_mv: float
    v_rst_mv: float
    v_th_mv: float
    t_mbr_ms: PositiveFloat
    tau_ms: PositiveFloat
    t_rfc_ms: PositiveFloat
    t_dly_ms: PositiveFloat
    w_syn_mv: float
    f_poi: float
    dt_ms: PositiveFloat

    @property
    def delay_steps(self) -> int:
        return round(self.t_dly_ms / self.dt_ms)

    @property
    def refractory_steps(self) -> int:
        return round(self.t_rfc_ms / self.dt_ms)

    @property
    def poisson_kick_mv(self) -> float:
        return self.w_syn_mv * self.f_poi


def load_params(path: Path = Path("configs/lif.yaml")) -> LIFParams:
    return LIFParams.model_validate(yaml.safe_load(path.read_text()))
