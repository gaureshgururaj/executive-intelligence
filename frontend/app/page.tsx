import DashboardContent from "@/components/DashboardContent";
import HealthIndicator from "@/components/HealthIndicator";
import { fetchArticles, fetchPapers } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const [articles, papers] = await Promise.all([
    fetchArticles(),
    fetchPapers(),
  ]);

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

      <DashboardContent articles={articles} papers={papers} />
    </main>
  );
}
