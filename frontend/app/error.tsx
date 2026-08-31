"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="page">
      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Executive briefing</p>
          <h1>AI Executive Intelligence</h1>
        </div>
      </header>
      <section className="empty error-state" role="alert">
        <h2>Unable to load intelligence</h2>
        <p>
          The briefing could not be retrieved. Confirm the API is running, then
          try again.
        </p>
        <p className="error-detail">{error.message}</p>
        <button type="button" className="retry" onClick={() => reset()}>
          Retry
        </button>
      </section>
    </main>
  );
}
