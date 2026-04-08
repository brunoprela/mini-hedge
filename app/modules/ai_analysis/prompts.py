"""Prompt templates for each AI analysis type."""

from __future__ import annotations

import json
from typing import Any

from app.modules.ai_analysis.interface import AnalysisType

PROMPTS: dict[AnalysisType, str] = {
    AnalysisType.MARKET_COMMENTARY: (
        "You are a senior market strategist at a hedge fund.\n"
        "Write a concise market commentary based on the following data.\n\n"
        "Context:\n{context}\n\n"
        "Return your response as JSON with these fields:\n"
        '- "summary": 2-3 sentence overview\n'
        '- "key_points": list of 3-5 bullet points\n'
        '- "sentiment": one of very_bearish, bearish, neutral, bullish, very_bullish\n'
        '- "confidence": decimal 0.0 to 1.0\n'
        '- "body": full analysis text (2-3 paragraphs)\n'
    ),
    AnalysisType.PORTFOLIO_REVIEW: (
        "You are a portfolio analyst at a hedge fund.\n"
        "Review the following portfolio data and provide actionable insights.\n\n"
        "Context:\n{context}\n\n"
        "Return your response as JSON with these fields:\n"
        '- "summary": 2-3 sentence overview\n'
        '- "key_points": list of 3-5 bullet points\n'
        '- "sentiment": one of very_bearish, bearish, neutral, bullish, very_bullish\n'
        '- "confidence": decimal 0.0 to 1.0\n'
        '- "body": full analysis text (2-3 paragraphs)\n'
    ),
    AnalysisType.RISK_ASSESSMENT: (
        "You are the chief risk officer at a hedge fund.\n"
        "Assess the risk profile based on the following data.\n\n"
        "Context:\n{context}\n\n"
        "Return your response as JSON with these fields:\n"
        '- "summary": 2-3 sentence overview of key risks\n'
        '- "key_points": list of 3-5 risk factors\n'
        '- "sentiment": one of very_bearish, bearish, neutral, bullish, very_bullish\n'
        '- "confidence": decimal 0.0 to 1.0\n'
        '- "body": full risk assessment text (2-3 paragraphs)\n'
    ),
    AnalysisType.TRADE_RATIONALE: (
        "You are a senior trader at a hedge fund.\n"
        "Provide a rationale for the following trade or trade idea.\n\n"
        "Context:\n{context}\n\n"
        "Return your response as JSON with these fields:\n"
        '- "summary": 2-3 sentence trade thesis\n'
        '- "key_points": list of 3-5 supporting arguments\n'
        '- "sentiment": one of very_bearish, bearish, neutral, bullish, very_bullish\n'
        '- "confidence": decimal 0.0 to 1.0\n'
        '- "body": full rationale text (2-3 paragraphs)\n'
    ),
    AnalysisType.EARNINGS_SUMMARY: (
        "You are an equity research analyst.\n"
        "Summarize the following earnings data and provide key takeaways.\n\n"
        "Context:\n{context}\n\n"
        "Return your response as JSON with these fields:\n"
        '- "summary": 2-3 sentence earnings overview\n'
        '- "key_points": list of 3-5 earnings highlights\n'
        '- "sentiment": one of very_bearish, bearish, neutral, bullish, very_bullish\n'
        '- "confidence": decimal 0.0 to 1.0\n'
        '- "body": full earnings analysis text (2-3 paragraphs)\n'
    ),
    AnalysisType.NEWS_DIGEST: (
        "You are a financial news analyst.\n"
        "Digest the following news items and assess their market impact.\n\n"
        "Context:\n{context}\n\n"
        "Return your response as JSON with these fields:\n"
        '- "summary": 2-3 sentence news digest\n'
        '- "key_points": list of 3-5 key developments\n'
        '- "sentiment": one of very_bearish, bearish, neutral, bullish, very_bullish\n'
        '- "confidence": decimal 0.0 to 1.0\n'
        '- "body": full news analysis text (2-3 paragraphs)\n'
    ),
    AnalysisType.FACTOR_COMMENTARY: (
        "You are a quantitative strategist at a hedge fund.\n"
        "Provide commentary on the following factor exposures and performance.\n\n"
        "Context:\n{context}\n\n"
        "Return your response as JSON with these fields:\n"
        '- "summary": 2-3 sentence factor overview\n'
        '- "key_points": list of 3-5 factor insights\n'
        '- "sentiment": one of very_bearish, bearish, neutral, bullish, very_bullish\n'
        '- "confidence": decimal 0.0 to 1.0\n'
        '- "body": full factor commentary text (2-3 paragraphs)\n'
    ),
}


def build_prompt(analysis_type: AnalysisType, context: dict[str, Any]) -> str:
    """Build a prompt from template and context data."""
    template = PROMPTS[analysis_type]
    context_str = json.dumps(context, indent=2, default=str)
    return template.format(context=context_str)
