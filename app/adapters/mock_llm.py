"""Mock LLM adapter — deterministic template-based responses for testing."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.shared.adapters import LLMResponse

# ---------------------------------------------------------------------------
# Mock responses keyed by analysis type substring
# ---------------------------------------------------------------------------

_MOCK_RESPONSES: dict[str, dict[str, object]] = {
    "market strategist": {
        "summary": (
            "Markets showed mixed signals this session with tech leading gains "
            "while energy lagged. Volatility remains elevated amid macro uncertainty."
        ),
        "key_points": [
            "S&P 500 gained 0.4% driven by mega-cap tech",
            "Treasury yields rose 5bps on strong labor data",
            "VIX remains above 20, signaling continued caution",
            "Dollar strengthened against major currencies",
        ],
        "sentiment": "neutral",
        "confidence": 0.72,
        "body": (
            "Today's session reflected a market still grappling with conflicting "
            "signals. Technology stocks rallied on strong earnings guidance from "
            "semiconductor names, pushing the Nasdaq higher by 0.6%. However, "
            "the breadth was narrow, with only 55% of S&P constituents in positive "
            "territory.\n\n"
            "Fixed income markets sold off modestly after labor market data came "
            "in stronger than expected, pushing the 10-year yield to 4.35%. This "
            "reinforces the higher-for-longer narrative that has dominated recent "
            "Fed communications.\n\n"
            "Looking ahead, we expect range-bound trading until the next CPI print "
            "provides clarity on the inflation trajectory."
        ),
    },
    "portfolio analyst": {
        "summary": (
            "The portfolio is well-diversified across sectors but shows elevated "
            "concentration in technology. Risk-adjusted returns remain above benchmark."
        ),
        "key_points": [
            "Technology allocation at 35% exceeds policy limit of 30%",
            "Sharpe ratio of 1.42 outperforms benchmark by 0.3",
            "Cash position at 8% is within target range",
            "Emerging market exposure adds diversification benefit",
            "Consider rebalancing tech overweight into healthcare",
        ],
        "sentiment": "bullish",
        "confidence": 0.81,
        "body": (
            "The portfolio demonstrates strong risk-adjusted performance with a "
            "Sharpe ratio of 1.42, comfortably above the benchmark's 1.12. "
            "Position sizing has been disciplined, with no single name exceeding "
            "5% of NAV.\n\n"
            "The primary concern is sector concentration in technology at 35% of "
            "the book, which exceeds the 30% policy guideline. While this "
            "overweight has been additive to returns, it increases vulnerability "
            "to a sector rotation.\n\n"
            "We recommend a gradual rebalancing toward healthcare and industrials "
            "to reduce concentration risk while maintaining the quality factor tilt "
            "that has driven alpha generation."
        ),
    },
    "chief risk officer": {
        "summary": (
            "Portfolio risk metrics are within acceptable bounds, though tail risk "
            "has increased. VaR utilization is at 78% of limit."
        ),
        "key_points": [
            "1-day 95% VaR at $2.1M (78% of $2.7M limit)",
            "Expected shortfall suggests fat tails in return distribution",
            "Correlation regime has shifted higher across equity sectors",
            "Liquidity risk is low with 95% of book in liquid names",
        ],
        "sentiment": "bearish",
        "confidence": 0.76,
        "body": (
            "The current risk profile shows VaR utilization approaching but not "
            "breaching established limits. The 1-day 95% VaR stands at $2.1M "
            "against a limit of $2.7M, leaving a buffer of 22%.\n\n"
            "More concerning is the expected shortfall metric, which at $3.4M "
            "suggests heavier tails than a normal distribution would imply. Cross-"
            "sector correlations have increased from 0.45 to 0.62 over the past "
            "month, reducing diversification benefits.\n\n"
            "We recommend monitoring the correlation regime closely and consider "
            "hedging tail risk through options structures if VaR utilization "
            "exceeds 85%."
        ),
    },
    "senior trader": {
        "summary": (
            "The proposed long position is supported by improving fundamentals "
            "and favorable technicals. Risk/reward is attractive at current levels."
        ),
        "key_points": [
            "Revenue growth accelerating for three consecutive quarters",
            "Price breaking above 200-day moving average on high volume",
            "Short interest at 18-month low suggests reduced bearish positioning",
            "Implied volatility is below realized, making options cheap",
        ],
        "sentiment": "bullish",
        "confidence": 0.68,
        "body": (
            "The trade thesis rests on an improving fundamental picture combined "
            "with a supportive technical setup. Revenue growth has accelerated "
            "from 8% to 14% over the past three quarters, driven by market share "
            "gains in the core business.\n\n"
            "From a technical perspective, the stock has broken above its 200-day "
            "moving average on above-average volume, a pattern that has "
            "historically preceded sustained rallies in 72% of cases.\n\n"
            "We recommend sizing at 2% of NAV with a stop-loss at the recent "
            "swing low, providing a 3:1 reward-to-risk ratio."
        ),
    },
    "equity research": {
        "summary": (
            "The company reported earnings above consensus with strong guidance. "
            "Margins expanded on operating leverage."
        ),
        "key_points": [
            "EPS of $2.15 beat consensus of $1.98 by 8.6%",
            "Revenue of $4.2B topped estimates of $4.05B",
            "Operating margin expanded 150bps year-over-year",
            "Full-year guidance raised by 5% at midpoint",
            "Free cash flow conversion improved to 92%",
        ],
        "sentiment": "bullish",
        "confidence": 0.85,
        "body": (
            "The company delivered a strong quarter, beating on both the top and "
            "bottom lines. EPS of $2.15 exceeded the $1.98 consensus by 8.6%, "
            "driven by better-than-expected revenue and margin expansion.\n\n"
            "Operating margins widened to 24.5% from 23.0% a year ago, reflecting "
            "operating leverage as revenue growth outpaced cost inflation. Free "
            "cash flow conversion improved to 92%, supporting the ongoing "
            "buyback program.\n\n"
            "Management raised full-year guidance by 5% at the midpoint, citing "
            "strong demand trends and improved visibility into the back half."
        ),
    },
    "news analyst": {
        "summary": (
            "Key market-moving news centered on central bank policy signals and "
            "geopolitical developments. Sector rotation favored defensives."
        ),
        "key_points": [
            "Fed officials signaled patience on rate cuts",
            "Trade tensions escalated with new tariff proposals",
            "Major M&A deal announced in healthcare sector",
            "Commodity prices rose on supply disruption fears",
        ],
        "sentiment": "bearish",
        "confidence": 0.65,
        "body": (
            "The news cycle was dominated by hawkish commentary from Federal "
            "Reserve officials, who pushed back against market expectations for "
            "near-term rate cuts. This triggered a modest selloff in rate-"
            "sensitive sectors.\n\n"
            "Geopolitical headlines added to the cautious tone, with new tariff "
            "proposals raising concerns about global trade flows. Commodity "
            "markets responded with gains in oil and industrial metals on supply "
            "disruption fears.\n\n"
            "On the corporate front, a major healthcare M&A deal was announced, "
            "sparking renewed interest in the sector as a defensive positioning "
            "play."
        ),
    },
    "quantitative strategist": {
        "summary": (
            "Factor performance shows momentum and quality outperforming while "
            "value continues to lag. Factor crowding risk is moderate."
        ),
        "key_points": [
            "Momentum factor returned +2.1% MTD, strongest in 6 months",
            "Quality factor benefiting from flight to safety",
            "Value factor underperforming by 1.3% as rates stabilize",
            "Low volatility factor gaining as VIX rises",
            "Factor crowding metrics suggest moderate positioning risk",
        ],
        "sentiment": "neutral",
        "confidence": 0.74,
        "body": (
            "Factor returns this month show a clear preference for momentum and "
            "quality, consistent with a late-cycle environment where investors "
            "favor companies with proven earnings trajectories and strong "
            "balance sheets.\n\n"
            "The underperformance of the value factor is notable given the "
            "rate environment. Typically, value benefits from higher rates, "
            "but the current episode appears driven by earnings revisions "
            "rather than rate expectations.\n\n"
            "We recommend maintaining the portfolio's quality tilt while "
            "monitoring momentum factor crowding, which has reached the 72nd "
            "percentile of its historical range."
        ),
    },
}


def _detect_type(prompt: str) -> dict[str, object]:
    """Match a prompt to a mock response based on role keywords."""
    for keyword, response in _MOCK_RESPONSES.items():
        if keyword in prompt.lower():
            return response
    # Fallback
    return next(iter(_MOCK_RESPONSES.values()))


class MockLLMAdapter:
    """Deterministic mock for testing — generates template-based responses."""

    async def generate(
        self, prompt: str, *, max_tokens: int = 2048, temperature: float = 0.7
    ) -> LLMResponse:
        """Generate deterministic response based on analysis type detection in prompt."""
        from app.shared.adapters import LLMResponse

        response_data = _detect_type(prompt)
        return LLMResponse(
            text=json.dumps(response_data),
            model="mock-llm-v1",
            tokens_used=len(prompt.split()) + 350,
        )
