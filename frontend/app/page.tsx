"use client";

import { useEffect, useState } from "react";

import { fetchHealth } from "@/lib/api";

type Indicator = "checking" | "ok" | "down";

const LABELS: Record<Indicator, string> = {
  checking: "Checking API…",
  ok: "API healthy",
  down: "API unavailable",
};

export default function HomePage() {
  const [status, setStatus] = useState<Indicator>("checking");

  useEffect(() => {
    let cancelled = false;

    fetchHealth()
      .then((payload) => {
        if (!cancelled) {
          setStatus(payload.status === "ok" ? "ok" : "down");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setStatus("down");
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="page">
      <h1>AI Executive Intelligence Platform</h1>
      <p className="status">
        <span className={`dot ${status}`} aria-hidden="true" />
        <span>{LABELS[status]}</span>
      </p>
    </main>
  );
}
