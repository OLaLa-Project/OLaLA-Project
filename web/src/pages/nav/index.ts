export type NavPage = "demo" | "team-a" | "team-b" | "platform";

export const NAV_PAGES: Array<{ id: NavPage; label: string; hint: string }> = [
  { id: "demo", label: "LLM Demo", hint: "Wikipedia RAG dev" },
  { id: "team-a", label: "Team A", hint: "Evidence Pipeline" },
  { id: "team-b", label: "Team B", hint: "Verification" },
  { id: "platform", label: "Platform", hint: "Common/Graph/Schema" },
];
