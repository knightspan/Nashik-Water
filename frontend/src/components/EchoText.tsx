import type { ElementType } from 'react';

const ECHO_LAYERS = [
  { offset: 0.04, className: 'text-echo-1' },
  { offset: 0.08, className: 'text-echo-2' },
  { offset: 0.12, className: 'text-echo-3' },
  { offset: 0.16, className: 'text-echo-4' },
] as const;

interface EchoTextProps {
  text: string;
  as?: ElementType;
  className?: string;
}

/**
 * Typographic echo stack: the word in ink on top, with four lighter copies behind it,
 * each shifted up-left by a further 0.04em. Echo layers are hidden from screen readers.
 */
export function EchoText({ text, as: Tag = 'h1', className = '' }: EchoTextProps) {
  return (
    <Tag className={`relative isolate inline-block leading-crush ${className}`}>
      {[...ECHO_LAYERS].reverse().map(({ offset, className: tone }) => (
        <span
          key={offset}
          aria-hidden="true"
          data-testid="echo-layer"
          className={`pointer-events-none absolute inset-0 select-none ${tone}`}
          style={{ transform: `translate(-${offset}em, -${offset}em)`, zIndex: -1 }}
        >
          {text}
        </span>
      ))}
      <span className="relative text-ink">{text}</span>
    </Tag>
  );
}
