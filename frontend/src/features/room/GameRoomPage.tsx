import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import type { ApiClient } from "../../lib/api-client";
import type { RoomReport } from "../../lib/types";
import { ActionPanel } from "./ActionPanel";
import { ConnectionStatus } from "./ConnectionStatus";
import { PlayerRail } from "./PlayerRail";
import { PrivatePanel } from "./PrivatePanel";
import { RoomTimeline } from "./RoomTimeline";
import { FinishedReport } from "./FinishedReport";
import { SpectatorPanel } from "./SpectatorPanel";
import { useRoomSession } from "./use-room-session";

export function GameRoomPage({ roomId, apiClient }: { roomId: string; apiClient: ApiClient }) {
  const session = useRoomSession(roomId, apiClient);
  const [pending, setPending] = useState(false);
  const [report, setReport] = useState<RoomReport | null>(null);
  const submit = async (command: Parameters<typeof session.submitCommand>[0]) => { try { setPending(true); await session.submitCommand(command); } finally { setPending(false); } };
  useEffect(() => { if (session.snapshot?.status !== "finished") return; void apiClient.getReport(roomId).then(setReport).catch(() => setReport(null)); }, [apiClient, roomId, session.snapshot?.status]);
  if (!session.snapshot) return <main className="app-shell">正在载入对局…</main>;
  return <main className="game-layout"><header><Link to="/">☾ Werewolf Arena</Link><ConnectionStatus status={session.connection} onRefresh={() => void session.refresh()} onContinue={() => void session.continueRoom()} /></header><div className="game-columns"><RoomTimeline events={session.events} participants={session.snapshot.participants} /><aside>{session.snapshot.view_mode === "active" && <PrivatePanel state={session.snapshot} />}{session.snapshot.view_mode === "spectating" && <SpectatorPanel />}{session.snapshot.view_mode === "finished" && (report ? <FinishedReport report={report} /> : <p>正在生成完整复盘…</p>)}<PlayerRail state={session.snapshot} />{session.snapshot.view_mode === "active" && <ActionPanel state={session.snapshot} onSubmit={submit} pending={pending} />}{session.error && <p role="alert">{session.error}</p>}{session.snapshot.status === "finished" && <Link className="restart" to="/">返回历史</Link>}</aside></div></main>;
}
