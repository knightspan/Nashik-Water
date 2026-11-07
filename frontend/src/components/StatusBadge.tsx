import { useTranslation } from 'react-i18next';
import { STATUS_HEX, STATUS_ON } from '../lib/format';
import type { Colour } from '../lib/types';

const SHAPE: Record<Colour, string> = {
  // A distinct glyph per state so the badge never relies on colour alone.
  GREEN: '●',
  AMBER: '▲',
  RED: '■',
  GREY: '○',
};

interface Props {
  colour: Colour;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

/** Colour verdict chip: filled status colour + glyph + text label. */
export function StatusBadge({ colour, size = 'md', className = '' }: Props) {
  const { t } = useTranslation();
  const pad =
    size === 'lg'
      ? 'px-4 py-2 text-base'
      : size === 'sm'
        ? 'px-2 py-0.5 text-[11px]'
        : 'px-3 py-1 text-xs';
  return (
    <span
      data-colour={colour}
      className={`inline-flex items-center gap-1.5 rounded-full font-bold uppercase tracking-wide ${pad} ${className}`}
      style={{ background: STATUS_HEX[colour], color: STATUS_ON[colour] }}
    >
      <span aria-hidden="true">{SHAPE[colour]}</span>
      {t(`status.${colour}`)}
    </span>
  );
}

/** Small swatch with glyph, for legends and lists. */
export function StatusDot({ colour }: { colour: Colour }) {
  return (
    <span
      aria-hidden="true"
      className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px]"
      style={{ background: STATUS_HEX[colour], color: STATUS_ON[colour] }}
    >
      {SHAPE[colour]}
    </span>
  );
}
