import { useEffect, useRef } from 'react';

/** Browser cancellation stops obsolete reads; it never cancels a server write. */
export function useRequestScope(key: string) {
  const state = useRef({ key, epoch: 0, controllers: new Set<AbortController>() });
  if (state.current.key !== key) {
    state.current.key = key;
    state.current.epoch++;
  }
  useEffect(() => () => {
    state.current.epoch++;
    state.current.controllers.forEach(controller => controller.abort());
    state.current.controllers.clear();
  }, [key]);
  return {
    start() {
      const epoch = ++state.current.epoch;
      const controller = new AbortController();
      state.current.controllers.add(controller);
      return {
        signal: controller.signal,
        current: () => state.current.epoch === epoch,
        finish: () => state.current.controllers.delete(controller),
      };
    },
  };
}
