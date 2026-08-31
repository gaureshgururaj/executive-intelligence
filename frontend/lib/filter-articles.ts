import type { Article } from "@/lib/api";

export const ALL_CATEGORIES = "all";

export type ArticleFilters = {
  category: string;
  minPercent: number;
};

export type ArticleSort =
  | "newest"
  | "oldest"
  | "relevance-desc"
  | "relevance-asc";

export function relevancePercent(score: number): number {
  return Math.round(score * 100);
}

export function uniqueCategories(articles: Article[]): string[] {
  return [...new Set(articles.map((article) => article.category))].sort((a, b) =>
    a.localeCompare(b, "en"),
  );
}

export function filtersAreDefault(filters: ArticleFilters): boolean {
  return filters.category === ALL_CATEGORIES && filters.minPercent === 0;
}

export function filterArticles(
  articles: Article[],
  filters: ArticleFilters,
): Article[] {
  return articles.filter((article) => {
    const categoryMatch =
      filters.category === ALL_CATEGORIES ||
      article.category === filters.category;
    const relevanceMatch =
      relevancePercent(article.relevance_score) >= filters.minPercent;
    return categoryMatch && relevanceMatch;
  });
}

function articleTimestampMs(article: Article): number {
  const iso = article.published_at ?? article.created_at;
  if (!iso) {
    return 0;
  }
  const ms = Date.parse(iso);
  return Number.isNaN(ms) ? 0 : ms;
}

export function sortArticles(
  articles: Article[],
  sort: ArticleSort,
): Article[] {
  return [...articles].sort((left, right) => {
    const newerFirst = (): number => {
      const byTime = articleTimestampMs(right) - articleTimestampMs(left);
      return byTime !== 0 ? byTime : right.id.localeCompare(left.id);
    };
    const olderFirst = (): number => {
      const byTime = articleTimestampMs(left) - articleTimestampMs(right);
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
