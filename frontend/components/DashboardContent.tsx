"use client";

import { useState } from "react";

import ArticleFeed from "@/components/ArticleFeed";
import ResearchFeed from "@/components/ResearchFeed";
import type { Article, Paper } from "@/lib/api";

type Mode = "trends" | "research";

export default function DashboardContent({
  articles,
  papers,
}: {
  articles: Article[];
  papers: Paper[];
}) {
  const [mode, setMode] = useState<Mode>("trends");

  return (
    <div className="dashboard-content">
      <div className="mode-switch" role="group" aria-label="Dashboard mode">
        <button
          type="button"
          aria-pressed={mode === "trends"}
          onClick={() => setMode("trends")}
        >
          Trends
        </button>
        <button
          type="button"
          aria-pressed={mode === "research"}
          onClick={() => setMode("research")}
        >
          Research
        </button>
      </div>
      {mode === "trends" ? (
        <ArticleFeed articles={articles} />
      ) : (
        <ResearchFeed papers={papers} />
      )}
    </div>
  );
}
