import { describe, expect, it } from 'vitest';
import { configMatches, defaults, fmt, riskLevel, timelineClock, serviceDayMinutes, timelineDayOffset } from './types';

describe('auditable presentation contracts', () => {
  it('does not present missing numbers as zero', () => {
    expect(fmt(null)).toBe('—'); expect(fmt(undefined)).toBe('—'); expect(fmt(0)).toBe('0');
  });
  it('marks a changed capacity, date, solver or source as stale', () => {
    expect(configMatches(defaults, {...defaults})).toBe(true);
    for (const change of [{contact_gates: 20}, {solver: 'greedy' as const}, {dataset_id: 'other'}, {service_date: '2026-07-02'}]) {
      expect(configMatches(defaults, {...defaults, ...change})).toBe(false);
    }
  });
  it('distinguishes a missing probability from low risk', () => {
    expect(riskLevel({predicted_delay_min: 35, probability_delay_15: null})).toBe('high');
    expect(riskLevel({predicted_delay_min: 2, probability_delay_15: .6})).toBe('high');
  });
  it('formats elapsed timeline minutes in the actual ATL timezone including rollover', () => {
    expect(timelineClock(0, '2026-07-01T04:00:00+00:00')).toBe('00:00');
    expect(timelineClock(1500, '2026-07-01T04:00:00+00:00')).toBe('01:00');
    expect(timelineClock(-30, '2026-07-01T04:00:00+00:00')).toBe('23:30');
  });
  it('uses local calendar dates and actual day duration across ATL DST changes', () => {
    expect(serviceDayMinutes('2026-03-08T05:00:00Z')).toBe(1380);
    expect(serviceDayMinutes('2026-11-01T04:00:00Z')).toBe(1500);
    expect(timelineDayOffset(1440, '2026-11-01T04:00:00Z')).toBe(0);
    expect(timelineDayOffset(1500, '2026-11-01T04:00:00Z')).toBe(1);
    expect(timelineDayOffset(-5, '2026-07-01T04:00:00Z')).toBe(-1);
  });
});
