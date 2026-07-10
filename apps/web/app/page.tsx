"use client";

import { useEffect, useState } from "react";

type HealthState =
  | { status: "loading" }
  | { status: "ok" }
  | { status: "error"; message: string };

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Home() {
  const [health, setHealth] = useState<HealthState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;

    async function checkHealth() {
      try {
        const response = await fetch(`${API_URL}/health`);
        if (!response.ok) {
          throw new Error(`API responded with ${response.status}`);
        }
        const data = await response.json();
        if (cancelled) {
          return;
        }
        setHealth(
          data.status === "ok"
            ? { status: "ok" }
            : { status: "error", message: "Unexpected response from API" },
        );
      } catch (error) {
        if (!cancelled) {
          setHealth({
            status: "error",
            message: error instanceof Error ? error.message : "Unknown error",
          });
        }
      }
    }

    void checkHealth();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50">
      <div className="rounded-2xl border border-slate-200 bg-white/70 p-8 shadow-sm backdrop-blur">
        <h1 className="text-xl font-medium text-slate-800">Meridian</h1>
        <p className="mt-2 text-sm text-slate-500">API status</p>
        <p data-testid="health-status" className="mt-4 text-lg font-semibold text-slate-900">
          {health.status === "loading" && "Checking..."}
          {health.status === "ok" && "ok"}
          {health.status === "error" && `error: ${health.message}`}
        </p>
      </div>
    </main>
  );
}
