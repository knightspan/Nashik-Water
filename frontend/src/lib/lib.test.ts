import en from '../i18n/en';
import mr from '../i18n/mr';
import { source } from '../test/utils';
import { bandOf, redRuns, sortBySeverity, sourceBadge, timeAgo } from './format';

function keys(o: object, prefix = ''): string[] {
  return Object.entries(o).flatMap(([k, v]) =>
    typeof v === 'object' && v !== null ? keys(v as object, `${prefix}${k}.`) : [`${prefix}${k}`],
  );
}

describe('translations', () => {
  it('Marathi has exactly the English keys, none empty', () => {
    expect(keys(mr).sort()).toEqual(keys(en).sort());
    const empty = keys(mr).filter((k) => {
      const v = k.split('.').reduce<unknown>((o, p) => (o as Record<string, unknown>)[p], mr);
      return typeof v === 'string' && v.trim() === '' && k !== 'project.quoteB';
    });
    expect(empty).toEqual([]);
  });

  it('includes the required limitation notices', () => {
    expect(en.about.limits.one).toContain('is not a certificate that water is safe to drink');
    expect(en.about.limits.two).toBe('River water is not meant for direct drinking.');
    expect(en.about.limits.three).toBe(
      'Simulated sites show computer-generated demonstration data.',
    );
  });
});

describe('format helpers', () => {
  it('sorts RED first, then AMBER, GREY, GREEN', () => {
    const list = [
      source({ id: 'a', name_en: 'A', status_colour: 'GREEN' }),
      source({ id: 'b', name_en: 'B', status_colour: 'GREY' }),
      source({ id: 'c', name_en: 'C', status_colour: 'RED' }),
      source({ id: 'd', name_en: 'D', status_colour: 'AMBER' }),
    ];
    expect(sortBySeverity(list, 'en').map((s) => s.id)).toEqual(['c', 'd', 'b', 'a']);
  });

  it.each([
    [null, null],
    [10, 'excellent'],
    [25, 'excellent'],
    [26, 'good'],
    [50, 'good'],
    [75, 'poor'],
    [100, 'very_poor'],
    [101, 'unfit'],
  ])('bandOf(%s) = %s', (w, band) => {
    expect(bandOf(w)).toBe(band);
  });

  it('chooses the right source badge', () => {
    expect(sourceBadge(source())).toBe('live');
    expect(sourceBadge(source({ stale: true }))).toBe('delayed');
    expect(sourceBadge(source({ simulated: true }))).toBe('simulated');
  });

  it('formats relative time', () => {
    const now = Date.parse('2026-11-02T12:00:00Z');
    expect(timeAgo('2026-11-02T11:55:00Z', 'en', now)).toBe('5 minutes ago');
    expect(timeAgo('2026-11-02T11:59:50Z', 'en', now)).toBe('now');
  });
});

describe('redRuns', () => {
  it('groups consecutive RED points into shaded spans', () => {
    const pts = [
      { t: 1, colour: 'GREEN' },
      { t: 2, colour: 'RED' },
      { t: 3, colour: 'RED' },
      { t: 4, colour: 'GREEN' },
      { t: 5, colour: 'RED' },
    ];
    expect(redRuns(pts)).toEqual([
      [2, 4],
      [5, 5],
    ]);
  });
});
