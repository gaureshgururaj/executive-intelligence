import type { Article } from "@/lib/api";

function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "Date unavailable";
  }
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

function articleDate(article: Article): { iso: string; label: string } | null {
  const iso = article.published_at ?? article.created_at;
  if (!iso) {
    return null;
  }
  return { iso, label: formatDate(iso) };
}

function relevancePercent(score: number): number {
  return Math.round(score * 100);
}

export default function ArticleCard({ article }: { article: Article }) {
  const date = articleDate(article);
  const percent = relevancePercent(article.relevance_score);

  return (
    <article className="card">
      <div className="card-meta">
        <span className="badge">{article.category}</span>
        {date ? (
          <time className="card-date" dateTime={date.iso}>
            {date.label}
          </time>
        ) : (
          <span className="card-date">Date unavailable</span>
        )}
      </div>
      <h2 className="card-title">{article.title}</h2>
      <p className="card-summary">{article.summary}</p>
      <div className="relevance">
        <div className="meta-label">
          <span>Relevance</span>
          <span>{percent}%</span>
        </div>
        <div
          className="relevance-track"
          role="meter"
          aria-label="Relevance score"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent}
        >
          <span className="relevance-fill" style={{ width: `${percent}%` }} />
        </div>
      </div>
      {article.key_points.length > 0 ? (
        <div className="key-points-block">
          <p className="meta-label">Key points</p>
          <ul className="key-points">
            {article.key_points.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>
        </div>
      ) : null}
      <a
        className="source-link"
        href={article.canonical_url}
        target="_blank"
        rel="noopener noreferrer"
      >
        Read original →
      </a>
    </article>
  );
}
