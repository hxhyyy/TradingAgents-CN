from tradingagents.utils.logging_init import get_logger
from tradingagents.utils.tool_logging import log_analyst_module
logger = get_logger("analysts.social_media")

from tradingagents.agents.utils.instrument_utils import build_instrument_context


def _get_company_name_for_social_media(ticker: str, market_info: dict) -> str:
    """
    为社交媒体分析师获取公司名称

    Args:
        ticker: 股票代码
        market_info: 市场信息字典

    Returns:
        str: 公司名称
    """
    try:
        if market_info['is_china']:
            # 中国A股：使用统一接口获取股票信息
            from tradingagents.dataflows.interface import get_china_stock_info_unified
            stock_info = get_china_stock_info_unified(ticker)

            logger.debug(f"📊 [社交媒体分析师] 获取股票信息返回: {stock_info[:200] if stock_info else 'None'}...")

            # 解析股票名称
            if stock_info and "股票名称:" in stock_info:
                company_name = stock_info.split("股票名称:")[1].split("\n")[0].strip()
                logger.info(f"✅ [社交媒体分析师] 成功获取中国股票名称: {ticker} -> {company_name}")
                return company_name
            else:
                # 降级方案：尝试直接从数据源管理器获取
                logger.warning(f"⚠️ [社交媒体分析师] 无法从统一接口解析股票名称: {ticker}，尝试降级方案")
                try:
                    from tradingagents.dataflows.data_source_manager import get_china_stock_info_unified as get_info_dict
                    info_dict = get_info_dict(ticker)
                    if info_dict and info_dict.get('name'):
                        company_name = info_dict['name']
                        logger.info(f"✅ [社交媒体分析师] 降级方案成功获取股票名称: {ticker} -> {company_name}")
                        return company_name
                except Exception as e:
                    logger.error(f"❌ [社交媒体分析师] 降级方案也失败: {e}")

                logger.error(f"❌ [社交媒体分析师] 所有方案都无法获取股票名称: {ticker}")
                return f"股票代码{ticker}"

        elif market_info['is_hk']:
            # 港股：使用改进的港股工具
            try:
                from tradingagents.dataflows.providers.hk.improved_hk import get_hk_company_name_improved
                company_name = get_hk_company_name_improved(ticker)
                logger.debug(f"📊 [社交媒体分析师] 使用改进港股工具获取名称: {ticker} -> {company_name}")
                return company_name
            except Exception as e:
                logger.debug(f"📊 [社交媒体分析师] 改进港股工具获取名称失败: {e}")
                # 降级方案：生成友好的默认名称
                clean_ticker = ticker.replace('.HK', '').replace('.hk', '')
                return f"港股{clean_ticker}"

        elif market_info['is_us']:
            # 美股：使用简单映射或返回代码
            us_stock_names = {
                'AAPL': '苹果公司',
                'TSLA': '特斯拉',
                'NVDA': '英伟达',
                'MSFT': '微软',
                'GOOGL': '谷歌',
                'AMZN': '亚马逊',
                'META': 'Meta',
                'NFLX': '奈飞'
            }

            company_name = us_stock_names.get(ticker.upper(), f"美股{ticker}")
            logger.debug(f"📊 [社交媒体分析师] 美股名称映射: {ticker} -> {company_name}")
            return company_name

        else:
            return f"股票{ticker}"

    except Exception as e:
        logger.error(f"❌ [社交媒体分析师] 获取公司名称失败: {e}")
        return f"股票{ticker}"


def create_social_media_analyst(llm, toolkit):
    @log_analyst_module("social_media")
    def social_media_analyst_node(state):
        # 🔧 工具调用计数器 - 防止无限循环
        tool_call_count = state.get("sentiment_tool_call_count", 0)
        max_tool_calls = 3  # 最大工具调用次数
        logger.info(f"🔧 [死循环修复] 当前工具调用次数: {tool_call_count}/{max_tool_calls}")

        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        # 获取股票市场信息
        from tradingagents.utils.stock_utils import StockUtils
        market_info = StockUtils.get_market_info(ticker)

        # 获取公司名称
        company_name = _get_company_name_for_social_media(ticker, market_info)
        instrument_context = build_instrument_context(ticker)
        logger.info(f"[社交媒体分析师] 公司名称: {company_name}")

        # 统一使用 get_stock_sentiment_unified 工具（预抓取，避免 tool_call 空转）
        logger.info(f"[社交媒体分析师] 使用统一情绪分析工具，自动识别股票类型")
        sentiment_tool = toolkit.get_stock_sentiment_unified

        if market_info["is_us"]:
            system_message = (
                """您是一位专业的美股投资者情绪分析师。
基于提供的真实数据（新闻情绪、Reddit 讨论等）进行分析。
**严禁编造**未在数据中出现的雪球、股吧、Reddit 帖子数量、情绪比例或股价预测。
若数据不足，请明确说明"情绪数据不足"，不要虚构替代分析。

分析要点：新闻情绪标签、讨论热度、短期价格影响预期。
请撰写中文报告，末尾附 Markdown 表格总结。"""
            )
        else:
            system_message = (
                """您是一位专业的中国市场社交媒体和投资情绪分析师。
基于提供的真实数据进行分析；**严禁编造**未出现的平台讨论数据。
若数据不足请明确说明，不要虚构雪球、股吧等讨论比例。
请撰写详细的中文分析报告，并在报告末尾附上Markdown表格总结关键发现。"""
            )

        def _generate_sentiment_report(sentiment_text: str) -> str:
            analysis_prompt = f"""请基于以下真实情绪/讨论数据，分析 {ticker}（{company_name}）的投资者情绪：

=== 情绪原始数据 ===
{sentiment_text}

=== 分析要求 ===
{system_message}"""
            llm_result = llm.invoke([
                {
                    "role": "system",
                    "content": "只能使用提供的数据，禁止编造任何社交媒体统计或股价预测。",
                },
                {"role": "user", "content": analysis_prompt},
            ])
            return llm_result.content if hasattr(llm_result, "content") else str(llm_result)

        report = ""
        try:
            logger.info(f"[社交媒体分析师] 预抓取情绪数据: {ticker}")
            sentiment_raw = sentiment_tool.invoke(
                {"ticker": ticker, "curr_date": current_date}
            )
            logger.info(
                f"[社交媒体分析师] 预抓取结果长度: {len(sentiment_raw) if sentiment_raw else 0}"
            )

            if sentiment_raw and len(str(sentiment_raw).strip()) > 80:
                report = _generate_sentiment_report(str(sentiment_raw))
            else:
                report = (
                    f"# {ticker} 情绪分析\n\n"
                    f"未能获取足够的情绪/社交媒体数据，无法给出可靠的情绪评分。"
                    f"建议参考新闻分析师报告，或稍后重试。"
                )
        except Exception as e:
            logger.error(f"[社交媒体分析师] 预抓取失败: {e}", exc_info=True)
            report = (
                f"# {ticker} 情绪分析\n\n"
                f"情绪数据获取失败: {e}"
            )

        from langchain_core.messages import AIMessage

        return {
            "messages": [AIMessage(content=report)],
            "sentiment_report": report,
            "sentiment_tool_call_count": tool_call_count + 1,
        }

    return social_media_analyst_node
