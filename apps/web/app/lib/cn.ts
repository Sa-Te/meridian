/** Joins conditional class names, dropping falsy values. A single-purpose
 * stand-in for `clsx` -- not worth a dependency for one filter+join. */
export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}
