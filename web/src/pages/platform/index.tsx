function PlatformPage() {
  return (
    <div className="team">
      <div className="team-header">
        <h2>Platform (Common)</h2>
        <p>Stage 9~10 + Graph/Schema</p>
      </div>
      <div className="team-grid">
        <section className="team-card">
          <h3>Focus</h3>
          <ul>
            <li>stage09_judge</li>
            <li>stage10_policy</li>
            <li>graph</li>
            <li>shared</li>
          </ul>
        </section>
        <section className="team-card">
          <h3>Working Paths</h3>
          <div className="team-paths">
            <div>backend/app/stages/stage09_judge</div>
            <div>backend/app/stages/stage10_policy</div>
            <div>backend/app/graph</div>
            <div>shared</div>
          </div>
        </section>
      </div>
    </div>
  );
}

export default PlatformPage;
