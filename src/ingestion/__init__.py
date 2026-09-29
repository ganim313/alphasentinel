def __getattr__(name: str):
    if name == "ingest_bhavcopy_dataframe":
        from src.ingestion.bhavcopy import ingest_bhavcopy_dataframe
        return ingest_bhavcopy_dataframe
    elif name == "fetch_screener_fundamentals":
        from src.ingestion.screener_scraper import fetch_screener_fundamentals
        return fetch_screener_fundamentals
    elif name == "record_corporate_action":
        from src.ingestion.corporate_actions import record_corporate_action
        return record_corporate_action
    elif name == "apply_pending_corporate_actions":
        from src.ingestion.corporate_actions import apply_pending_corporate_actions
        return apply_pending_corporate_actions
    elif name == "fetch_macro_weather_data":
        from src.ingestion.macro_feeds import fetch_macro_weather_data
        return fetch_macro_weather_data
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    "ingest_bhavcopy_dataframe",
    "fetch_screener_fundamentals",
    "record_corporate_action",
    "apply_pending_corporate_actions",
    "fetch_macro_weather_data",
]

