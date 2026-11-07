import { render, screen } from '@testing-library/react';
import { EchoText } from './EchoText';

describe('EchoText', () => {
  it('renders one visible heading and four hidden echo layers', () => {
    render(<EchoText text="GODAVARI" />);
    expect(screen.getByRole('heading', { level: 1 })).toHaveAccessibleName('GODAVARI');
    const layers = screen.getAllByTestId('echo-layer');
    expect(layers).toHaveLength(4);
    layers.forEach((l) => expect(l).toHaveAttribute('aria-hidden', 'true'));
  });
});
