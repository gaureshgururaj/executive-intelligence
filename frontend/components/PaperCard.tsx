import type { Paper } from "@/lib/api";
import { relevancePercent } from "@/lib/filter-articles";

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

function paperDate(paper: Paper): { iso: string; label: string } | null {
  const iso = paper.published_at ?? paper.created_at;
  if (!iso) {
    return null;
  }
  return { iso, label: formatDate(iso) };
}

function formatAuthors(authors: string[]): string | null {
  if (authors.length === 0) {
    return null;
  }
  if (authors.length <= 3) {
    return authors.join(", ");
  }
  return `${authors.slice(0, 3).join(", ")} +${authors.length - 3} more`;
}

export default function PaperCard({ paper }: { paper: Paper }) {
  const date = paperDate(paper);
  const percent = relevancePercent(paper.relevance_score);
  const authors = formatAuthors(paper.authors);

  return (
    <article className="card">
      <div className="card-meta">
        <span className="badge">{paper.category}</span>
        {date ? (
          <time className="card-date" dateTime={date.iso}>
            {date.label}
          </time>
        ) : (
          <span className="card-date">Date unavailable</span>
        )}
      </div>
      <h2 className="card-title">{paper.title}</h2>
      {authors ? <p className="card-authors">{authors}</p> : null}
      <p className="card-summary">{paper.summary}</p>
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
      {paper.key_findings.length > 0 ? (
        <div className="key-points-block">
          <p className="meta-label">Key findings</p>
          <ul className="key-points">
            {paper.key_findings.map((finding) => (
              <li key={finding}>{finding}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {paper.practical_implications.length > 0 ? (
        <div className="key-points-block">
          <p className="meta-label">Practical implications</p>
          <ul className="key-points">
            {paper.practical_implications.map((implication) => (
              <li key={implication}>{implication}</li>
            ))}
          </ul>
        </div>
      ) : null}
      <div className="source-links">
        <a
          className="source-link"
          href={paper.paper_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          View on arXiv
        </a>
        {paper.pdf_url ? (
          <a
            className="source-link"
            href={paper.pdf_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            PDF
          </a>
        ) : null}
      </div>
    </article>
  );
}
