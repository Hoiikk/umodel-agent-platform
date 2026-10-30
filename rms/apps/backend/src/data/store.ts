import { Candidate, isCandidateStatus } from '@rms/shared';
import seed from './candidates.json';

/**
 * 内存存储层（AGENTS.md §3.3）：只存内存，启动时从种子文件加载。
 * 本层只做数据存取，不含任何业务规则。
 *
 * 读取性能优化（函数签名与返回契约保持不变）：
 * - candidateById：id → Candidate 哈希索引，getCandidate O(1) 命中；
 * - listSnapshot：有序列表快照——首次 listCandidates 时按 Map 迭代序
 *   （= 种子声明序）构建一次并冻结，之后重复查询直接复用同一实例，
 *   不再每次 O(n) 重建数组；冻结可防止调用方误改共享快照；
 * - 任何写入（loadSeed / saveCandidate）都会失效快照，保证写后读一致。
 */
const candidateById = new Map<string, Candidate>();

/** 有序列表快照；null 表示已失效，下次读取时重建。 */
let listSnapshot: Candidate[] | null = null;

function invalidateSnapshot(): void {
  listSnapshot = null;
}

export function loadSeed(): void {
  candidateById.clear();
  for (const raw of seed) {
    if (!isCandidateStatus(raw.status)) {
      throw new Error(`种子数据含非法状态: ${raw.id} -> ${raw.status}`);
    }
    candidateById.set(raw.id, { ...raw, status: raw.status });
  }
  invalidateSnapshot();
}

export function listCandidates(): Candidate[] {
  if (listSnapshot === null) {
    listSnapshot = Object.freeze([...candidateById.values()]) as Candidate[];
  }
  return listSnapshot;
}

export function getCandidate(id: string): Candidate | undefined {
  return candidateById.get(id);
}

export function saveCandidate(candidate: Candidate): void {
  candidateById.set(candidate.id, candidate);
  invalidateSnapshot();
}
