"""Seed interests for the first ranking; feedback on briefings adds to these (see rank.score_all)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Topic:
    category: str
    label: str  # shown as the reason an article was picked
    text: str


TOPICS = (
    Topic("invest", "반도체", "반도체와 메모리 업황, HBM, 삼성전자와 SK하이닉스 실적"),
    Topic("invest", "미국 빅테크", "미국 빅테크 실적과 주가: 엔비디아, 애플, 마이크로소프트, 알파벳, 아마존, 메타, 테슬라"),
    Topic("invest", "금리·환율·물가", "기준금리, 연준과 한국은행 통화정책, 환율, 물가와 고용 지표"),
    Topic("invest", "배당 ETF", "배당 ETF와 배당주 투자, 분배금"),
    Topic("realestate", "수도권 아파트", "서울과 수도권 아파트 매매가와 전세가 동향"),
    Topic("realestate", "대출·세금 정책", "주택담보대출 규제, DSR, 부동산 세금과 주택 공급 정책"),
    Topic("realestate", "경기 남부 개발", "경기 남부 개발 호재: 신도시, GTX와 철도, 반도체 클러스터"),
    Topic("tech", "AI 코딩 도구", "AI 코딩 에이전트와 개발 도구, LLM 활용 소프트웨어 개발"),
    Topic("tech", "오픈소스 AI", "오픈소스 AI 모델과 언어 모델 출시, 벤치마크"),
)
