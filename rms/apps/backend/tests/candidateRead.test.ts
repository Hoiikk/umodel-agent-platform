import { AddressInfo } from 'net';
import { Server } from 'http';
import { isCandidateStatus } from '@rms/shared';
import { app } from '../src/app';
import * as store from '../src/data/store';
import seed from '../src/data/candidates.json';

/**
 * GET /api/candidates 读取契约测试（先于存储层性能优化落地）。
 *
 * 锁定三项契约，优化前后都必须保持：
 * 1. 字段：每条记录恰好含 AGENTS.md §3.2 冻结的 8 个字段，类型与取值不变；
 * 2. 条数：与种子文件 candidates.json 一致；
 * 3. 顺序：返回顺序与种子文件声明顺序一致。
 *
 * HTTP 层走真实 express app（随机端口，无新依赖）；
 * store 层额外锁定「写入后读可见」与「重复读取结果一致」两项行为，
 * 为快照复用优化的失效逻辑兜底。
 */

/** AGENTS.md §3.2 冻结字段（字典序，供精确比对）。 */
const FROZEN_FIELDS = ['createdAt', 'email', 'id', 'name', 'phone', 'position', 'source', 'status'];

describe('GET /api/candidates - HTTP 读取契约', () => {
  let server: Server;
  let baseUrl: string;

  beforeAll((done) => {
    server = app.listen(0, () => {
      const { port } = server.address() as AddressInfo;
      baseUrl = `http://127.0.0.1:${port}`;
      done();
    });
  });

  afterAll((done) => {
    server.close(done);
  });

  it('健康检查返回稳定的存活响应', async () => {
    const res = await fetch(`${baseUrl}/healthz`);
    expect(res.status).toBe(200);
    await expect(res.json()).resolves.toEqual({ status: 'ok' });
  });

  it('返回 200 且为 JSON 数组，条数与种子一致', async () => {
    const res = await fetch(`${baseUrl}/api/candidates`);
    expect(res.status).toBe(200);
    const body = (await res.json()) as unknown[];
    expect(Array.isArray(body)).toBe(true);
    expect(body).toHaveLength(seed.length);
  });

  it('每条记录恰好包含 8 个冻结字段，类型正确、状态合法', async () => {
    const res = await fetch(`${baseUrl}/api/candidates`);
    const body = (await res.json()) as Record<string, unknown>[];
    for (const item of body) {
      expect(Object.keys(item).sort()).toEqual(FROZEN_FIELDS);
      for (const field of FROZEN_FIELDS) {
        expect(typeof item[field]).toBe('string');
      }
      expect(isCandidateStatus(item.status)).toBe(true);
    }
  });

  it('返回顺序与种子文件声明顺序一致', async () => {
    const res = await fetch(`${baseUrl}/api/candidates`);
    const body = (await res.json()) as Array<{ id: string }>;
    expect(body.map((c) => c.id)).toEqual(seed.map((s) => s.id));
  });

  it('整体内容与种子文件深度一致（取值逐字段锁定）', async () => {
    const res = await fetch(`${baseUrl}/api/candidates`);
    const body = await res.json();
    expect(body).toEqual(seed);
  });
});

describe('candidateStore - 读取行为契约', () => {
  beforeEach(() => {
    store.loadSeed();
  });

  it('重复调用 listCandidates 返回内容一致', () => {
    expect(store.listCandidates()).toEqual(store.listCandidates());
  });

  it('listCandidates 与种子深度一致（字段 / 条数 / 顺序）', () => {
    expect(store.listCandidates()).toEqual(seed);
  });

  it('getCandidate 命中返回同一条记录，未命中返回 undefined', () => {
    expect(store.getCandidate('cand-001')).toEqual(seed[0]);
    expect(store.getCandidate('no-such-id')).toBeUndefined();
  });

  it('saveCandidate 写入后，再次 list 必须可见最新数据（快照失效兜底）', () => {
    const before = store.listCandidates();
    const target = store.getCandidate('cand-001');
    expect(target).toBeDefined();
    store.saveCandidate({ ...target!, status: 'SCREENING' });

    const after = store.listCandidates();
    expect(after).toHaveLength(before.length);
    expect(after.find((c) => c.id === 'cand-001')?.status).toBe('SCREENING');
    // 未改动的记录保持原样
    expect(after.find((c) => c.id === 'cand-002')).toEqual(before.find((c) => c.id === 'cand-002'));
  });
});
