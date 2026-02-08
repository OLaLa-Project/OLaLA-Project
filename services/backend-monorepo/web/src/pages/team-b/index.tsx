function TeamBPage() {
  return (
    <div className="team">
      <div className="team-header">
        <h2>Team B (Verification)</h2>
        <p>Stage 6~8</p>
      </div>
      <div className="team-grid">
        <section className="team-card">
          <h3>Focus</h3>
          <ul>
            <li>stage06_verify_support</li>
            <li>stage07_verify_refute</li>
            <li>stage08_aggregate</li>
          </ul>
        </section>
        <section className="team-card">
          <h3>Working Paths</h3>
          <div className="team-paths">
            <div>backend/app/stages/stage06_verify_support</div>
            <div>backend/app/stages/stage07_verify_refute</div>
            <div>backend/app/stages/stage08_aggregate</div>
          </div>
        </section>
      </div>
    </div>
  );
}

export default TeamBPage;
