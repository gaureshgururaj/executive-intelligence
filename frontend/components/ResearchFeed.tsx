"use client";

import { useMemo, useState } from "react";

import PaperCard from "@/components/PaperCard";
import type { Paper } from "@/lib/api";
import {
  ALL_CATEGORIES,
  type PaperSort,
  filterPapers,
  filtersAreDefault,
  sortPapers,
  uniqueCategories,
} from "@/lib/filter-papers";

export default function ResearchFeed({ papers }: { papers: Paper[] }) {
  const [category, setCategory] = useState(ALL_CATEGORIES);
  const [minPercent, setMinPercent] = useState(0);
  const [sort, setSort] = useState<PaperSort>("newest");

  const categories = useMemo(() => uniqueCategories(papers), [papers]);
  const visible = useMemo(
    () => sortPapers(filterPapers(papers, { category, minPercent }), sort),
    [papers, category, minPercent, sort],
  );
  const isDefault = filtersAreDefault({ category, minPercent });
  const relevanceLabel =
    minPercent === 0
      ? "Minimum relevance: All"
      : `Minimum relevance: ${minPercent}%`;
  const relevanceValueText =
    minPercent === 0
      ? "All relevance levels"
      : `${minPercent} percent minimum relevance`;

  if (papers.length === 0) {
    return (
      <section className="empty" aria-live="polite">
        <h2>No research papers available yet.</h2>
        <p>
          When the research pipeline publishes accepted papers, they will appear
          here.
        </p>
      </section>
    );
  }

  const countLabel = isDefault
    ? `${papers.length} accepted paper${papers.length === 1 ? "" : "s"}`
    : `Showing ${visible.length} of ${papers.length}`;

  return (
    <section className="feed" aria-label="Accepted research papers">
      <div className="feed-toolbar">
        <div className="feed-controls">
          <label className="feed-field">
            <span>Category</span>
            <select
              value={category}
              onChange={(event) => setCategory(event.target.value)}
            >
              <option value={ALL_CATEGORIES}>All categories</option>
              {categories.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <label className="feed-field feed-field-slider">
            <span>{relevanceLabel}</span>
            <input
              type="range"
              min={0}
              max={100}
              step={5}
              value={minPercent}
              onChange={(event) => setMinPercent(Number(event.target.value))}
              aria-valuetext={relevanceValueText}
            />
          </label>
          <label className="feed-field">
            <span>Sort by</span>
            <select
              value={sort}
              onChange={(event) => setSort(event.target.value as PaperSort)}
            >
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
              <option value="relevance-desc">Most relevant</option>
              <option value="relevance-asc">Least relevant</option>
            </select>
          </label>
        </div>
        <div className="feed-toolbar-meta">
          <p className="feed-count" aria-live="polite">
            {countLabel}
          </p>
          <button
            type="button"
            className="clear-filters"
            onClick={() => {
              setCategory(ALL_CATEGORIES);
              setMinPercent(0);
            }}
            disabled={isDefault}
          >
            Clear filters
          </button>
        </div>
      </div>

      {visible.length === 0 ? (
        <div className="empty filter-empty">
          <h2>No research papers match these filters.</h2>
          <p>Clear filters to see the full accepted research briefing again.</p>
          <button
            type="button"
            className="retry"
            onClick={() => {
              setCategory(ALL_CATEGORIES);
              setMinPercent(0);
            }}
          >
            Clear filters
          </button>
        </div>
      ) : (
        visible.map((paper) => <PaperCard key={paper.id} paper={paper} />)
      )}
    </section>
  );
}
