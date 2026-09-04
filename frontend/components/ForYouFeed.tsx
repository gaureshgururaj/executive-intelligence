"use client";

import { useEffect, useState } from "react";

import RecommendationCard from "@/components/RecommendationCard";
import {
  fetchRecommendations,
  type RecommendationItem,
  type RecommendationProfile,
} from "@/lib/api";

export default function ForYouFeed({
  profiles,
}: {
  profiles: RecommendationProfile[];
}) {
  const [selectedProfileId, setSelectedProfileId] = useState(
    profiles[0]?.id ?? "",
  );
  const [items, setItems] = useState<RecommendationItem[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">(
    profiles.length === 0 ? "ready" : "loading",
  );
  const [reloadToken, setReloadToken] = useState(0);

  const selectedProfile =
    profiles.find((profile) => profile.id === selectedProfileId) ?? null;

  useEffect(() => {
    if (!selectedProfileId) {
      return;
    }

    let cancelled = false;
    setStatus("loading");

    fetchRecommendations(selectedProfileId)
      .then((recommendations) => {
        if (!cancelled) {
          setItems(recommendations);
          setStatus("ready");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setStatus("error");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedProfileId, reloadToken]);

  if (profiles.length === 0) {
    return (
      <section className="empty" aria-live="polite">
        <h2>No recommendation profiles available yet.</h2>
      </section>
    );
  }

  return (
    <section
      className="feed"
      aria-label="Personalized recommendations"
      aria-busy={status === "loading"}
    >
      <div className="feed-toolbar for-you-toolbar">
        <div className="feed-controls">
          <label className="feed-field">
            <span>Profile</span>
            <select
              value={selectedProfileId}
              onChange={(event) => setSelectedProfileId(event.target.value)}
            >
              {profiles.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        {selectedProfile && selectedProfile.interests.length > 0 ? (
          <p className="profile-interests">
            <span className="profile-interests-label">Interests</span>
            {selectedProfile.interests.join(" · ")}
          </p>
        ) : null}
        {status === "ready" ? (
          <p className="feed-count" aria-live="polite">
            {items.length === 0
              ? "No matching recommendations"
              : `${items.length} recommendation${items.length === 1 ? "" : "s"}`}
          </p>
        ) : null}
      </div>

      {status === "loading" ? (
        <>
          <div className="card skeleton" />
          <div className="card skeleton" />
          <div className="card skeleton" />
        </>
      ) : status === "error" ? (
        <div className="empty error-state" role="alert">
          <h2>Unable to load recommendations.</h2>
          <p>Confirm the API is running, then try again.</p>
          <button
            type="button"
            className="retry"
            onClick={() => setReloadToken((token) => token + 1)}
          >
            Retry
          </button>
        </div>
      ) : items.length === 0 ? (
        <div className="empty" aria-live="polite">
          <h2>No recommendations match this profile yet.</h2>
        </div>
      ) : (
        items.map((recommendation) => (
          <RecommendationCard
            key={`${recommendation.content_type}-${recommendation.item.id}`}
            recommendation={recommendation}
          />
        ))
      )}
    </section>
  );
}
