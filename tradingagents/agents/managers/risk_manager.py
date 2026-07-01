import time
import json

# 导入统一日志系统
from tradingagents.utils.logging_init import get_logger
from tradingagents.agents.utils.instrument_utils import build_instrument_context
from tradingagents.agents.utils.perspective_utils import (
    build_perspective_banner,
    build_perspective_guidance,
    build_perspective_output_schema,
    get_analysis_perspective,
    get_perspective_label,
)
from tradingagents.agents.utils.facts_card import build_facts_card_from_state, build_facts_card_text
logger = get_logger("default")


def create_risk_manager(llm, memory):
    def risk_manager_node(state) -> dict:

        company_name = state["company_of_interest"]
        instrument_context = build_instrument_context(company_name)

        history = state["risk_debate_state"]["history"]
        risk_debate_state = state["risk_debate_state"]
        market_research_report = state["market_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        sentiment_report = state["sentiment_report"]
        research_plan = state["investment_plan"]
        trader_plan = state.get("trader_investment_plan", "")

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"

        # 安全检查：确保memory不为None
        if memory is not None:
            past_memories = memory.get_memories(curr_situation, n_matches=2)
        else:
            logger.warning(f"⚠️ [DEBUG] memory为None，跳过历史记忆检索")
            past_memories = []

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        # ✅ 统一 facts 底稿（治本：跨节点口径一致）
        facts_card = build_facts_card_from_state(state)
        facts_text = build_facts_card_text(facts_card)

        prompt = f"""作为风险管理委员会主席，综合三位风险分析师（激进、中性、保守）的辩论，形成最终交易决策。

{build_perspective_banner()}

{instrument_context}

{facts_text}

---

**评级标准**（必须选择其一）：
- **买入**：强烈看多，建议建仓或显著加仓
- **增持**：偏多观点，建议逐步增加敞口
- **持有**：多空证据较为均衡，或暂无明确方向，建议维持现有仓位、暂不操作
- **减持**：偏谨慎，建议逐步降低敞口或部分获利了结
- **卖出**：强烈看空或风险过高，建议清仓或避免建仓

当辩论中最强论据支持某一方向时，应明确表态；仅当多空证据确实势均力敌时，才选择「持有」。

{build_perspective_guidance()}

---

**决策指导原则**：
1. **总结关键论点**：提取每位分析师的最强观点，重点关注与当前**{get_perspective_label()}**视角的相关性。
2. **综合上下文**：研究经理投资计划：**{research_plan}**；交易员交易提案：**{trader_plan}**。须在同一视角下协调二者，若交易员与视角宪法冲突，以视角宪法与研究经理计划为准并说明理由。
3. **从过去的错误中学习**：使用以下经验教训改进判断，避免重复失误：
{past_memory_str if past_memory_str.strip() else "（暂无历史记忆）"}
4. **依据证据裁决**：每个结论须有辩论中的具体证据支撑，避免无依据的极端判断。
5. **视角一致性**：最终结论、执行摘要、投资论点必须全部符合**{get_perspective_label()}**框架，不得混用另一套投资哲学的话术。

{build_perspective_output_schema()}

---

**分析师辩论历史：**
{history}

---

请基于分析师辩论中的具体证据做出果断判断。请用中文撰写所有分析内容和建议。"""

        # 📊 统计 prompt 大小
        prompt_length = len(prompt)
        # 粗略估算 token 数量（中文约 1.5-2 字符/token，英文约 4 字符/token）
        estimated_tokens = int(prompt_length / 1.8)  # 保守估计

        logger.info(f"📊 [Risk Manager] Prompt 统计:")
        logger.info(f"   - 辩论历史长度: {len(history)} 字符")
        logger.info(f"   - 交易员计划长度: {len(trader_plan)} 字符")
        logger.info(f"   - 历史记忆长度: {len(past_memory_str)} 字符")
        logger.info(f"   - 总 Prompt 长度: {prompt_length} 字符")
        logger.info(f"   - 估算输入 Token: ~{estimated_tokens} tokens")

        # 增强的LLM调用，包含错误处理和重试机制
        max_retries = 3
        retry_count = 0
        response_content = ""

        while retry_count < max_retries:
            try:
                logger.info(f"🔄 [Risk Manager] 调用LLM生成交易决策 (尝试 {retry_count + 1}/{max_retries})")

                # ⏱️ 记录开始时间
                start_time = time.time()

                response = llm.invoke(prompt)

                # ⏱️ 记录结束时间
                elapsed_time = time.time() - start_time
                
                if response and hasattr(response, 'content') and response.content:
                    response_content = response.content.strip()

                    # 📊 统计响应信息
                    response_length = len(response_content)
                    estimated_output_tokens = int(response_length / 1.8)

                    # 尝试获取实际的 token 使用情况（如果 LLM 返回了）
                    usage_info = ""
                    if hasattr(response, 'response_metadata') and response.response_metadata:
                        metadata = response.response_metadata
                        if 'token_usage' in metadata:
                            token_usage = metadata['token_usage']
                            usage_info = f", 实际Token: 输入={token_usage.get('prompt_tokens', 'N/A')} 输出={token_usage.get('completion_tokens', 'N/A')} 总计={token_usage.get('total_tokens', 'N/A')}"

                    logger.info(f"⏱️ [Risk Manager] LLM调用耗时: {elapsed_time:.2f}秒")
                    logger.info(f"📊 [Risk Manager] 响应统计: {response_length} 字符, 估算~{estimated_output_tokens} tokens{usage_info}")

                    if len(response_content) > 10:  # 确保响应有实质内容
                        logger.info(f"✅ [Risk Manager] LLM调用成功")
                        break
                    else:
                        logger.warning(f"⚠️ [Risk Manager] LLM响应内容过短: {len(response_content)} 字符")
                        response_content = ""
                else:
                    logger.warning(f"⚠️ [Risk Manager] LLM响应为空或无效")
                    response_content = ""

            except Exception as e:
                elapsed_time = time.time() - start_time
                logger.error(f"❌ [Risk Manager] LLM调用失败 (尝试 {retry_count + 1}): {str(e)}")
                logger.error(f"⏱️ [Risk Manager] 失败前耗时: {elapsed_time:.2f}秒")
                response_content = ""
            
            retry_count += 1
            if retry_count < max_retries and not response_content:
                logger.info(f"🔄 [Risk Manager] 等待2秒后重试...")
                time.sleep(2)
        
        # 如果所有重试都失败，生成默认决策
        if not response_content:
            logger.error(f"❌ [Risk Manager] 所有LLM调用尝试失败，使用默认决策")
            _perspective = get_analysis_perspective()
            _label = get_perspective_label(_perspective)
            if _perspective == "value":
                response_content = f"""**默认建议：持有**

由于技术原因无法生成详细分析，基于**{_label}**视角与风险控制原则，建议对{company_name}采取持有策略，等待更多基本面信息明朗。

**理由：**
1. 在价值分析框架下，信息不足时不应因短期波动盲目减持
2. 维持现有仓位，持续跟踪估值与基本面变化
3. 若出现基本面永久性恶化信号，再考虑减持

**建议：**
- 关注财报、行业景气与估值水平变化
- 设定基于基本面的减仓条件，而非纯技术止损

注意：此为系统默认建议，建议结合人工分析做出最终决策。"""
            else:
                response_content = f"""**默认建议：持有**

由于技术原因无法生成详细分析，基于**{_label}**视角与风险控制原则，建议对{company_name}采取观望/持有策略。

**理由：**
1. 趋势方向尚不明确，不宜盲目建仓或追涨
2. 等待价格与量能给出更清晰的方向信号
3. 控制回撤，避免在不确定性高时重仓

**建议：**
- 关注关键均线与支撑阻力位的突破/跌破
- 设定明确止损后再考虑建仓

注意：此为系统默认建议，建议结合人工分析做出最终决策。"""

        new_risk_debate_state = {
            "judge_decision": response_content,
            "history": risk_debate_state["history"],
            "risky_history": risk_debate_state["risky_history"],
            "safe_history": risk_debate_state["safe_history"],
            "neutral_history": risk_debate_state["neutral_history"],
            "latest_speaker": "Judge",
            "current_risky_response": risk_debate_state["current_risky_response"],
            "current_safe_response": risk_debate_state["current_safe_response"],
            "current_neutral_response": risk_debate_state["current_neutral_response"],
            "count": risk_debate_state["count"],
        }

        logger.info(f"📋 [Risk Manager] 最终决策生成完成，内容长度: {len(response_content)} 字符")
        
        return {
            "risk_debate_state": new_risk_debate_state,
            "final_trade_decision": response_content,
        }

    return risk_manager_node
