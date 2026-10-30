import { loadSeed } from '../data/store';
import { CandidateRepository } from './candidateRepository';
import { MemoryCandidateRepository } from './memoryCandidateRepository';
import { MySqlCandidateRepository } from './mysqlCandidateRepository';

export function createCandidateRepository(): CandidateRepository {
  if (process.env.RMS_STORAGE === 'memory') { loadSeed(); return new MemoryCandidateRepository(); }
  return new MySqlCandidateRepository();
}
