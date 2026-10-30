import seed from './resumes.json';

/**
 * 简历原文 sidecar 存储（独立于候选人主表，AGENTS.md §3.3 同样适用）：
 * - 简历原文只存本模块的独立 Map，不进 candidates 主表；
 * - 启动时从 sidecar 种子文件 resumes.json 加载，重启丢数据是预期行为。
 * 本层只做数据存取，不含任何业务规则。
 */
const resumeTexts = new Map<string, string>();

export function loadResumeSeed(): void {
  resumeTexts.clear();
  for (const raw of seed) {
    resumeTexts.set(raw.candidateId, raw.resumeText);
  }
}

/** 按候选人 id 取简历原文；无简历（未录入 sidecar）返回 undefined。 */
export function getResumeText(candidateId: string): string | undefined {
  return resumeTexts.get(candidateId);
}
