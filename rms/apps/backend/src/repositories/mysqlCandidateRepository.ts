import { Candidate, isCandidateStatus } from '@rms/shared';
import mysql, { Pool, RowDataPacket } from 'mysql2/promise';
import { CandidateRepository } from './candidateRepository';

type CandidateRow = RowDataPacket & Omit<Candidate, 'createdAt'> & { createdAt: Date };

export class MySqlCandidateRepository implements CandidateRepository {
  private readonly pool: Pool;
  constructor() {
    this.pool = mysql.createPool({ host: process.env.RMS_DB_HOST ?? '127.0.0.1', port: Number(process.env.RMS_DB_PORT ?? 3307), database: process.env.MYSQL_DATABASE ?? 'rms', user: process.env.RMS_DB_USER, password: process.env.RMS_DB_PASSWORD, connectionLimit: 5, timezone: 'Z' });
  }
  async list(): Promise<Candidate[]> { const [rows] = await this.pool.query<CandidateRow[]>('SELECT id,name,phone,email,position,status,source,reject_reason AS rejectReason,created_at AS createdAt FROM candidates ORDER BY created_at ASC, id ASC'); return rows.map(mapRow); }
  async getById(id: string): Promise<Candidate | undefined> { const [rows] = await this.pool.execute<CandidateRow[]>('SELECT id,name,phone,email,position,status,source,reject_reason AS rejectReason,created_at AS createdAt FROM candidates WHERE id = ?', [id]); return rows[0] ? mapRow(rows[0]) : undefined; }
  async save(candidate: Candidate): Promise<void> { await this.pool.execute('UPDATE candidates SET status = ? WHERE id = ?', [candidate.status, candidate.id]); }
}
function mapRow(row: CandidateRow): Candidate { if (!isCandidateStatus(row.status)) throw new Error(`数据库含非法状态: ${row.id}`); return { ...row, status: row.status, createdAt: row.createdAt.toISOString() }; }
