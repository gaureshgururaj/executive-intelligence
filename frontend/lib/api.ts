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
