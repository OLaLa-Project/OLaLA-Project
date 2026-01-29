import { useEffect, useState } from "react";
import DemoPage from "./pages/demo/DemoPage";
import { NAV_PAGES, type NavPage } from "./pages/nav";
import PlatformPage from "./pages/platform";
import TeamAPage from "./pages/team-a";
import TeamBPage from "./pages/team-b";
import LangGraphTestPage from "./pages/langgraph-test";

function getHashPage(): NavPage {
  const hash = window.location.hash.replace("#", "").trim();
  if (hash === "team-a" || hash === "team-b" || hash === "langgraph-test" || hash === "platform") return hash;
  return "demo";
}

function App() {
  const [page, setPage] = useState<NavPage>(getHashPage());

  useEffect(() => {
    const onHashChange = () => setPage(getHashPage());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  function handleNav(next: NavPage) {
    window.location.hash = next;
    setPage(next);
  }

  return (
    <div>
      <div className="bg-sheen"></div>
      <div className="bg-blobs"></div>
      <div className="page">
        <header className="topbar">
          <div className="brand">
            <div className="brand-mark">A</div>
            <div>
              <div className="brand-title">LLM RAG Demo</div>
              <div className="brand-sub">SLM sandbox for local Ollama</div>
            </div>
          </div>
          <nav className="nav">
            <div className="nav-tabs">
              {NAV_PAGES.map((nav) => (
                <button
                  key={nav.id}
                  className="pill tab"
                  data-active={page === nav.id}
                  onClick={() => handleNav(nav.id)}
                >
                  {nav.label}
                </button>
              ))}
            </div>
            <div className="nav-status">
              <div className="pill status" data-state={page === "demo" ? "ok" : "down"}>
                {page === "demo" ? "API" : "Docs"}
              </div>
            </div>
          </nav>
        </header>

        {page === "demo" ? (
          <DemoPage />
        ) : (
          <main className="team-wrap">
            {page === "team-a" ? <TeamAPage /> : null}
            {page === "team-b" ? <TeamBPage /> : null}
            {page === "langgraph-test" ? <LangGraphTestPage /> : null}
            {page === "platform" ? <PlatformPage /> : null}
          </main>
        )}
      </div>
    </div>
  );
}

export default App;
