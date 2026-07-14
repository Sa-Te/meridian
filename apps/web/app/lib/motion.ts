import type { CSSProperties } from "react";

/** A single mounting element fades and rises into place using the
 * `@starting-style` CSS transition -- no mount-tracking React state is
 * needed, since `@starting-style` fires automatically the instant an
 * element is inserted into the DOM. Reduced motion keeps the opacity
 * fade and drops the rise. */
export const ENTER_TRANSITION_CLASSES =
  "transition-[opacity,transform] duration-[var(--duration-base)] ease-[var(--ease-out)] starting:opacity-0 starting:translate-y-1 motion-reduce:starting:translate-y-0";

/** Same entrance recipe, plus a per-item transition-delay driven by the
 * `--stagger-delay` custom property set via staggerDelayStyle(). */
export const LIST_ENTER_CLASSES = `${ENTER_TRANSITION_CLASSES} delay-[var(--stagger-delay)] motion-reduce:delay-0`;

/** Press feedback: pair with PRESS_ACTIVE_CLASSES on the same element (or
 * on a conditionally-applied variant of it) to get a smooth, reduced-
 * motion-aware scale-down on :active. Split in two because Card only
 * applies the :active classes when it is the `interactive` variant, but
 * still needs the base transition unconditionally (it already carries the
 * pre-existing color-hover transition). */
export const PRESS_TRANSITION_CLASSES =
  "transition duration-[var(--duration-press)] ease-[var(--ease-out)]";
export const PRESS_ACTIVE_CLASSES = "active:scale-97 motion-reduce:active:scale-100";

const MAX_STAGGERED_ITEMS = 7;
const STAGGER_STEP_MS = 30;

/** Caps the stagger at the first 8 items (index 0-7) so a long list's
 * cumulative delay never makes the tail feel like it's blocking on the
 * animation before it can be interacted with. */
export function staggerDelayStyle(index: number): CSSProperties {
  const delayMs = Math.min(index, MAX_STAGGERED_ITEMS) * STAGGER_STEP_MS;
  return { "--stagger-delay": `${delayMs}ms` } as CSSProperties;
}
