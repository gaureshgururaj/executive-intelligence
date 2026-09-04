import type { Paper } from "@/lib/api";
import { relevancePercent } from "@/lib/filter-articles";

export const ALL_CATEGORIES = "all";

export type PaperFilters = {
  category: string;
  minPercent: number;
};

export type PaperSort =
  | "newest"
  | "oldest"
  | "relevance-desc"
  | "relevance-asc";

export function uniqueCategories(papers: Paper[]): string[] {
  return [...new Set(papers.map((paper) => paper.category))].sort((a, b) =>
    a.localeCompare(b, "en"),
  );
}

export function filtersAreDefault(filters: PaperFilters): boolean {
  return filters.category === ALL_CATEGORIES && filters.minPercent === 0;
}

export function filterPapers(
  papers: Paper[],
  filters: PaperFilters,
): Paper[] {
  return papers.filter((paper) => {
    const categoryMatch =
      filters.category === ALL_CATEGORIES || paper.category === filters.category;
    const relevanceMatch =
      relevancePercent(paper.relevance_score) >= filters.minPercent;
    return categoryMatch && relevanceMatch;
  });
}

function paperTimestampMs(paper: Paper): number {
  const iso = paper.published_at ?? paper.created_at;
  if (!iso) {
    return 0;
  }
  const ms = Date.parse(iso);
  return Number.isNaN(ms) ? 0 : ms;
}

export function sortPapers(papers: Paper[], sort: PaperSort): Paper[] {
  return [...papers].sort((left, right) => {
    const newerFirst = (): number => {
      const byTime = paperTimestampMs(right) - paperTimestampMs(left);
      return byTime !== 0 ? byTime : right.id.localeCompare(left.id);
    };
    const olderFirst = (): number => {
      const byTime = paperTimestampMs(left) - paperTimestampMs(right);
      return byTime !== 0 ? byTime : left.id.localeCompare(right.id);
    };

    switch (sort) {
      case "newest":
        return newerFirst();
      case "oldest":
        return olderFirst();
      case "relevance-desc": {
        const byScore =
          relevancePercent(right.relevance_score) -
          relevancePercent(left.relevance_score);
        return byScore !== 0 ? byScore : newerFirst();
      }
      case "relevance-asc": {
        const byScore =
          relevancePercent(left.relevance_score) -
          relevancePercent(right.relevance_score);
        return byScore !== 0 ? byScore : newerFirst();
      }
    }
  });
}
