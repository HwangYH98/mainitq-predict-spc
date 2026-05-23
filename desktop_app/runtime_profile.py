from __future__ import annotations

import os


FULL_PROFILE = "full"
LITE_PROFILE = "lite"


def runtime_profile() -> str:
    value = os.environ.get("MAINTIQ_RUNTIME_PROFILE", FULL_PROFILE).strip().lower()
    return LITE_PROFILE if value == LITE_PROFILE else FULL_PROFILE


def is_lite_runtime() -> bool:
    return runtime_profile() == LITE_PROFILE


def profile_label() -> str:
    return "빠른 점검 모드" if is_lite_runtime() else "정밀 분석 모드"


def score_method_label() -> str:
    return "경량 운영 점수" if is_lite_runtime() else "정밀 예측 엔진"


def profile_note() -> str:
    if is_lite_runtime():
        return "작은 설치본에서 빠르게 위험도를 점검하는 모드입니다. 정밀 분석 모드 결과와 다를 수 있습니다."
    return "XGBoost 기반 예측과 상세 설명을 사용하는 정밀 분석 경로입니다."
