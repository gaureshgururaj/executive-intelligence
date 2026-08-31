export default function Loading() {
  return (
    <main className="page">
      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Executive briefing</p>
          <h1>AI Executive Intelligence</h1>
          <p className="lede">Loading accepted developments…</p>
        </div>
      </header>
      <section className="feed" aria-busy="true" aria-label="Loading articles">
        <div className="card skeleton" />
        <div className="card skeleton" />
        <div className="card skeleton" />
      </section>
    </main>
  );
}
