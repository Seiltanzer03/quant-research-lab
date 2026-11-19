import { describe, expect, it } from 'vitest';
import { inspectCSV, riskReward } from './utils';

describe('Scenario geometry', () => {
  it('checks long and short level order and zero risk', () => {
    expect(riskReward('long', 100, 120, 90)).toBe(2);
    expect(riskReward('short', 100, 80, 110)).toBe(2);
    expect(riskReward('long', 100, 90, 110)).toBeNull();
    expect(riskReward('long', 100, 120, 100)).toBeNull();
  });
});
describe('CSV preview', () => {
  it('understands quoted TradingView CSV and detects invalid ranges', () => {
    const valid = inspectCSV('time,open,high,low,close\n"2026-01-01T00:00:00Z",100,110,90,105\n');
    expect(valid.rows).toBe(1); expect(valid.invalid).toBe(0); expect(valid.missing).toEqual([]);
    const invalid = inspectCSV('time,open,high,low,close\n1735689600,100,95,90,105\n');
    expect(invalid.invalid).toBe(1);
  });
  it('reports missing columns and duplicates without claiming a full import', () => {
    expect(inspectCSV('time,close\n1,10').missing).toContain('high');
    expect(inspectCSV('time,open,high,low,close\n1,10,11,9,10\n1,10,11,9,10').duplicates).toBe(1);
  });
});
