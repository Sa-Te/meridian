"use client";

import { useState } from "react";

export interface AsyncState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

interface AsyncStateActions<T> {
  start: () => void;
  succeed: (data: T) => void;
  fail: (error: string) => void;
}

/** The loading/data/error state shape every read-only view in this app
 * needs, without prescribing how or when to fetch -- each caller writes
 * its own useEffect with an explicit, literal dependency array (e.g.
 * [meetingId]) and calls these actions from it. A shared hook that
 * forwarded a caller-supplied dependency array into an internal
 * useEffect/useCallback was tried first and rejected: this project's
 * eslint-plugin-react-hooks version requires dependency arrays to be
 * literal at the call site, which a forwarded array can never be. See
 * docs/adr/0014. */
export function useAsyncState<T>(): [AsyncState<T>, AsyncStateActions<T>] {
  const [state, setState] = useState<AsyncState<T>>({
    data: null,
    error: null,
    loading: true,
  });

  return [
    state,
    {
      start: () => setState((previous) => ({ ...previous, loading: true, error: null })),
      succeed: (data: T) => setState({ data, error: null, loading: false }),
      fail: (error: string) => setState({ data: null, error, loading: false }),
    },
  ];
}
