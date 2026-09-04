export type HealthResponse = {
  status: string;
};

export type Article = {
  id: string;
  canonical_url: string;
  title: string;
  excerpt: string | null;
  published_at: string | null;
  summary: string;
  category: string;
  relevance_score: number;
  key_points: string[];
  created_at: string;
};

export type Paper = {
  id: string;
  arxiv_id: string;
  title: string;
  abstract: string;
  authors: string[];
  published_at: string | null;
  arxiv_updated_at: string | null;
  paper_url: string;
  pdf_url: string | null;
  categories: string[];
  summary: string;
  category: string;
  relevance_score: number;
  key_findings: string[];
  practical_implications: string[];
  created_at: string;
};

export type RecommendationProfile = {
  id: string;
  name: string;
  interests: string[];
};

export type ArticleRecommendation = {
  content_type: "article";
  recommendation_score: number;
  matched_interests: string[];
  reason: string;
  item: Article;
};

export type PaperRecommendation = {
  content_type: "paper";
  recommendation_score: number;
  matched_interests: string[];
  reason: string;
  item: Paper;
};

export type RecommendationItem = ArticleRecommendation | PaperRecommendation;

export function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${getApiBaseUrl()}/health`);
  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`);
  }
  return (await response.json()) as HealthResponse;
}

export async function fetchArticles(): Promise<Article[]> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/articles`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Articles request failed with status ${response.status}`);
  }
  return (await response.json()) as Article[];
}

export async function fetchPapers(): Promise<Paper[]> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/papers`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Papers request failed with status ${response.status}`);
  }
  return (await response.json()) as Paper[];
}

export async function fetchRecommendationProfiles(): Promise<
  RecommendationProfile[]
> {
  const response = await fetch(
    `${getApiBaseUrl()}/api/v1/recommendation-profiles`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(
      `Recommendation profiles request failed with status ${response.status}`,
    );
  }
  return (await response.json()) as RecommendationProfile[];
}

export async function fetchRecommendations(
  profileId: string,
): Promise<RecommendationItem[]> {
  const url = new URL(`${getApiBaseUrl()}/api/v1/recommendations`);
  url.searchParams.set("profile_id", profileId);
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(
      `Recommendations request failed with status ${response.status}`,
    );
  }
  return (await response.json()) as RecommendationItem[];
}
