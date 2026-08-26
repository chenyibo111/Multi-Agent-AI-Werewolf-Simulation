import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import type { ApiClient } from "../../lib/api-client";
import { RoomHistoryList, type LoadedHistoryRoom } from "../history/RoomHistoryList";
import { loadRoomHistory, rememberRoom, removeRoom } from "../history/room-history";
import { CreateGameForm } from "./CreateGameForm";

export function HomePage({ apiClient }: { apiClient: ApiClient }) {
  const navigate = useNavigate();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rooms, setRooms] = useState<LoadedHistoryRoom[]>([]);
  useEffect(() => { let disposed = false; void Promise.all(loadRoomHistory().map(async (entry) => { try { return { entry, payload: await apiClient.getRoom(entry.roomId) }; } catch { return { entry, payload: null }; } })).then((loaded) => { if (!disposed) setRooms(loaded); }); return () => { disposed = true; }; }, [apiClient]);
  const create = async (roleId?: string) => { try { setPending(true); setError(null); const room = await apiClient.createRoom(roleId); rememberRoom({ roomId: room.roomId, openedAt: new Date().toISOString() }); navigate(`/rooms/${room.roomId}`); } catch (caught) { setError(caught instanceof Error ? caught.message : "创建失败，请重试。"); } finally { setPending(false); } };
  const removeLocal = (roomId: string) => { removeRoom(roomId); setRooms((current) => current.filter((room) => room.entry.roomId !== roomId)); };
  const deleteRoom = async (roomId: string) => { if (!window.confirm("确定删除这局对局吗？")) return; try { await apiClient.deleteRoom(roomId); removeLocal(roomId); } catch (caught) { setError(caught instanceof Error ? caught.message : "删除失败，请重试。"); } };
  return <main className="landing"><p className="eyebrow">☾ WEREWOLF ARENA</p><h1>月夜之下，识破每一句谎言。</h1><p>一名人类玩家，与五名 AI 开始标准六人局狼人杀。</p><CreateGameForm onCreate={create} pending={pending} error={error} /><RoomHistoryList rooms={rooms} onContinue={(roomId) => navigate(`/rooms/${roomId}`)} onDelete={(roomId) => void deleteRoom(roomId)} onRemoveLocal={removeLocal} /></main>;
}
