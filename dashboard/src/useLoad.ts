import { useCallback, useEffect, useState } from "react";

export interface Loaded<T> {
  data: T | undefined;
  error: string | undefined;
  reload: () => void;
}

export function useLoad<T>(load: () => Promise<T>, key: string): Loaded<T> {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<string>();
  const [attempt, setAttempt] = useState(0);
  const reload = useCallback(() => {
    setAttempt((count) => count + 1);
  }, []);

  useEffect(() => {
    let current = true;
    load()
      .then((loaded) => {
        if (current) {
          setData(loaded);
          setError(undefined);
        }
      })
      .catch((cause: unknown) => {
        if (current)
          setError(cause instanceof Error ? cause.message : "Failed");
      });
    return () => {
      current = false;
    };
  }, [key, attempt]);

  return { data, error, reload };
}
