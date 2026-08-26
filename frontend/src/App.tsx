import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { HomePage } from "./features/home/HomePage";
import { GameRoomPage } from "./features/room/GameRoomPage";
import { ApiClient } from "./lib/api-client";

const apiClient = new ApiClient();
function RoomRoute() { const { roomId } = useParams(); return roomId ? <GameRoomPage roomId={roomId} apiClient={apiClient} /> : <Navigate to="/" replace />; }

export function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage apiClient={apiClient} />} />
      <Route path="/rooms/:roomId" element={<RoomRoute />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
