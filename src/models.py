from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


SourceType = Literal["youtube", "podcast"]


class TranscriptResult(BaseModel):
    source_type: SourceType
    source_url: str
    text: str


class ContentSummary(BaseModel):
    title: str = Field(description="影音內容的繁體中文主題標題")
    key_points: list[str] = Field(description="繁體中文重點條列")
    investment_observations: list[str] = Field(description="投資相關觀察，若無則回傳空陣列")


class StockAspects(BaseModel):
    business_model: str
    revenue_structure: str
    growth_drivers: str
    end_markets: str
    customers: str
    competitive_advantages: str
    management_guidance: str
    technical_analysis: str


class MentionedStock(BaseModel):
    company_name: str = Field(description="公司名稱，台股優先使用中文常用名稱")
    ticker: str = Field(description="股票代號；未知時填入 unknown")
    market: str = Field(description="市場或交易所，例如 TWSE、TPEx、NASDAQ、NYSE、unknown")
    mention_reason: str = Field(description="逐字稿提到此股票的原因或上下文")
    aspects: StockAspects


class AnalysisResult(BaseModel):
    summary: ContentSummary
    stocks: list[MentionedStock]

