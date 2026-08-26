import { useState } from "react";
import { useNavigate } from "react-router-dom";

import type { ApiClient } from "../../lib/api-client";
import { CreateGameForm } from "./CreateGameForm";

export function HomePage({ apiClient }: { apiClient: ApiClient }) {
  const navigate = useNavigate();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const resumeRoomId = localStorage.getItem("werewolf-arena-room-id");
  const create = async (roleId?: string) => { try { setPending(true); setError(null); const room = await apiClient.createRoom(roleId); localStorage.setItem("werewolf-arena-room-id", room.roomId); navigate(`/rooms/${room.roomId}`); } catch (caught) { setError(caught instanceof Error ? caught.message : "创建失败，请重试。"); } finally { setPending(false); } };
  return <main className="landing"><p className="eyebrow">☾ WEREWOLF ARENA</p><h1>月夜之下，识破每一句谎言。</h1><p>一名人类玩家，与五名 AI 开始标准六人局狼人杀。</p><CreateGameForm onCreate={create} pending={pending} error={error} />{resumeRoomId && <button className="subtle-button" onClick={() => navigate(`/rooms/${resumeRoomId}`)}>继续上次对局</button>}</main>;
}
