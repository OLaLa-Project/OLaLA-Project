export type NavPage = "demo" | "team-a" | "team-b" | "langgraph-test" | "platform" | "truth-check";

export const NAV_PAGES: Array<{ id: NavPage; label: string; hint: string }> = [
  { id: "demo", label: "Example (RAG)", hint: "Wikipedia RAG dev" },
  { id: "truth-check", label: "Check Truth", hint: "Main Pipeline" },
  { id: "team-a", label: "Team A", hint: "Evidence Pipeline" },
  { id: "team-b", label: "Team B", hint: "Verification" },
  { id: "langgraph-test", label: "LangGraph", hint: "Pipeline test" },
  { id: "platform", label: "Platform", hint: "Common/Graph/Schema" },
];
