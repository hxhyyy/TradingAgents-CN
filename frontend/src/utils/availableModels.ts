/** 按创建/更新时间倒序排列模型配置 */
export function sortModelsByNewest(configs: any[]): any[] {
  const getTimestamp = (config: any) => {
    const timeValue = config.created_at || config.updated_at
    const timestamp = timeValue ? new Date(timeValue).getTime() : 0
    return Number.isNaN(timestamp) ? 0 : timestamp
  }
  return [...configs].sort((a, b) => getTimestamp(b) - getTimestamp(a))
}

/** 若默认模型不在可用列表中，回退到第一个可用模型 */
export function resolveModelSelection(
  availableModels: any[],
  quickModel: string,
  deepModel: string
): { quickAnalysisModel: string; deepAnalysisModel: string } {
  const availableNames = new Set(availableModels.map(m => m.model_name))

  let quickAnalysisModel = quickModel
  let deepAnalysisModel = deepModel

  if (availableModels.length === 0) {
    return { quickAnalysisModel, deepAnalysisModel }
  }

  if (!availableNames.has(quickAnalysisModel)) {
    quickAnalysisModel = availableModels[0].model_name
  }

  if (!availableNames.has(deepAnalysisModel)) {
    deepAnalysisModel =
      availableModels.find(m => m.model_name === quickAnalysisModel)?.model_name
      || availableModels[0].model_name
  }

  return { quickAnalysisModel, deepAnalysisModel }
}
