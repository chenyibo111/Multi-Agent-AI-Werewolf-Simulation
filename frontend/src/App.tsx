import { Navigate, Route, Routes } from "react-router-dom";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<main className="app-shell">Werewolf Arena</main>} />
      <Route path="/rooms/:roomId" element={<main className="app-shell">正在载入对局…</main>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
