"use client";

import { useState } from "react";

import ArticleFeed from "@/components/ArticleFeed";
import ForYouFeed from "@/components/ForYouFeed";
import ResearchFeed from "@/components/ResearchFeed";
import type { Article, Paper, RecommendationProfile } from "@/lib/api";

type Mode = "for-you" | "trends" | "research";

export default function DashboardContent({
  articles,
  papers,
  profiles,
}: {
  articles: Article[];
  papers: Paper[];
  profiles: RecommendationProfile[];
}) {
  const [mode, setMode] = useState<Mode>("for-you");

  return (
    <div className="dashboard-content">
      <div className="mode-switch" role="group" aria-label="Dashboard mode">
        <button
          type="button"
          aria-pressed={mode === "for-you"}
          onClick={() => setMode("for-you")}
        >
          For You
        </button>
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
      {mode === "for-you" ? (
        <ForYouFeed profiles={profiles} />
      ) : mode === "trends" ? (
        <ArticleFeed articles={articles} />
      ) : (
        <ResearchFeed papers={papers} />
      )}
    </div>
  );
}
