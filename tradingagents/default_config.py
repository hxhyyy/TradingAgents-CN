import os

DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", "./results"),
    "data_dir": os.path.join(os.path.expanduser("~"), "Documents", "TradingAgents", "data"),
    "data_cache_dir": os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
        "dataflows/data_cache",
    ),
    # LLM settings
    "llm_provider": "openai",
    "deep_think_llm": "o4-mini",
    "quick_think_llm": "gpt-4o-mini",
    "backend_url": "https://api.openai.com/v1",
    # Debate and discussion settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    # 分析视角：value=价值分析, trend=趋势分析（与 selected_analysts 正交）
    "analysis_perspective": "value",
    # Tool settings - 从环境变量读取，提供默认值
    "online_tools": os.getenv("ONLINE_TOOLS_ENABLED", "false").lower() == "true",
    "online_news": os.getenv("ONLINE_NEWS_ENABLED", "true").lower() == "true", 
    "realtime_data": os.getenv("REALTIME_DATA_ENABLED", "false").lower() == "true",

    # Note: Database and cache configuration is now managed by .env file and config.database_manager
    # No database/cache settings in default config to avoid configuration conflicts
}
