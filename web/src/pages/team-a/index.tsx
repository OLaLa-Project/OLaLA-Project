function TeamAPage() {
  return (
    <div className="team">
      <div className="team-header">
        <h2>Team A (Evidence Pipeline)</h2>
        <p>Stage 1~5</p>
      </div>
      <div className="team-grid">
        <section className="team-card">
          <h3>Focus</h3>
          <ul>
            <li>stage01_normalize</li>
            <li>stage02_querygen</li>
            <li>stage03_retrieve</li>
            <li>stage04_rerank</li>
            <li>stage05_topk</li>
          </ul>
        </section>
        <section className="team-card">
          <h3>Working Paths</h3>
          <div className="team-paths">
            <div>backend/app/stages/stage01_normalize</div>
            <div>backend/app/stages/stage02_querygen</div>
            <div>backend/app/stages/stage03_retrieve</div>
            <div>backend/app/stages/stage04_rerank</div>
            <div>backend/app/stages/stage05_topk</div>
          </div>
        </section>
      </div>
    </div>
  );
}

export default TeamAPage;
