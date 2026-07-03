from __future__ import annotations

from app.core.config import settings
from app.providers.ais.marinetraffic_provider import MarineTrafficAISProvider
from app.providers.ais.mock_provider import MockAISProvider
from app.providers.llm.gemini_provider import GeminiLLMProvider
from app.providers.llm.groq_provider import GroqLLMProvider
from app.providers.llm.mock_provider import MockLLMProvider
from app.providers.news.gdelt_provider import GDELTNewsProvider
from app.providers.news.mock_provider import MockNewsProvider
from app.providers.prices.alphavantage_provider import AlphaVantagePriceProvider
from app.providers.prices.mock_provider import MockPriceProvider
from app.providers.sanctions.mock_provider import MockSanctionsProvider
from app.providers.sanctions.ofac_provider import OFACSanctionsProvider


def _demo_requested(demo_mode: bool | None = None) -> bool:
    return settings.demo_mode if demo_mode is None else demo_mode


def get_news_provider(demo_mode: bool | None = None):
    if _demo_requested(demo_mode) or not settings.gdelt_enabled:
        return MockNewsProvider(demo_mode=True)
    return GDELTNewsProvider(demo_mode=False)


def get_sanctions_provider(demo_mode: bool | None = None):
    if _demo_requested(demo_mode) or not settings.ofac_enabled:
        return MockSanctionsProvider(demo_mode=True)
    return OFACSanctionsProvider(demo_mode=False)


def get_ais_provider(demo_mode: bool | None = None):
    if _demo_requested(demo_mode) or settings.ais_provider.lower() == "mock":
        return MockAISProvider(demo_mode=True)
    provider_name = settings.ais_provider.lower()
    if provider_name == "marinetraffic":
        return MarineTrafficAISProvider(demo_mode=False)
    return MockAISProvider(demo_mode=True)


def get_price_provider(demo_mode: bool | None = None):
    if _demo_requested(demo_mode) or settings.price_provider.lower() == "mock":
        return MockPriceProvider(demo_mode=True)
    if settings.price_provider.lower() == "alphavantage":
        return AlphaVantagePriceProvider(demo_mode=False)
    return MockPriceProvider(demo_mode=True)


def get_llm_provider(demo_mode: bool | None = None):
    if _demo_requested(demo_mode):
        return MockLLMProvider(demo_mode=True)
    provider_name = settings.llm_provider.lower()
    if provider_name == "gemini" and settings.gemini_api_key:
        return GeminiLLMProvider(demo_mode=False)
    if provider_name == "groq" and settings.groq_api_key:
        return GroqLLMProvider(demo_mode=False)
    if settings.gemini_api_key:
        return GeminiLLMProvider(demo_mode=False)
    if settings.groq_api_key:
        return GroqLLMProvider(demo_mode=False)
    return MockLLMProvider(demo_mode=True)
