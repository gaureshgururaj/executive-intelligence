import ArticleCard from "@/components/ArticleCard";
import PaperCard from "@/components/PaperCard";
import type { RecommendationItem } from "@/lib/api";
import { relevancePercent } from "@/lib/filter-articles";

export default function RecommendationCard({
  recommendation,
}: {
  recommendation: RecommendationItem;
}) {
  const percent = relevancePercent(recommendation.recommendation_score);

  return (
    <div className="recommendation">
      <div className="recommendation-meta">
        <p className="recommendation-score">Recommended {percent}%</p>
        <p className="recommendation-reason">{recommendation.reason}</p>
      </div>
      {recommendation.content_type === "article" ? (
        <ArticleCard article={recommendation.item} />
      ) : (
        <PaperCard paper={recommendation.item} />
      )}
    </div>
  );
}
