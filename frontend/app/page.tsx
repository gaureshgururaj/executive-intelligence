import ArticleCard from "@/components/ArticleCard";
import HealthIndicator from "@/components/HealthIndicator";
import { fetchArticles } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const articles = await fetchArticles();

  return (
    <main className="page">
      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Executive briefing</p>
          <h1>AI Executive Intelligence</h1>
          <p className="lede">
            Accepted developments scored for technology leaders. Only
            quality-gated analysis appears here.
          </p>
        </div>
        <HealthIndicator />
      </header>

      {articles.length === 0 ? (
        <section className="empty" aria-live="polite">
          <h2>No accepted intelligence yet</h2>
          <p>
            When the pipeline publishes accepted articles, they will appear
            here.
          </p>
        </section>
      ) : (
        <section className="feed" aria-label="Accepted articles">
          {articles.map((article) => (
            <ArticleCard key={article.id} article={article} />
          ))}
        </section>
      )}
    </main>
  );
}
