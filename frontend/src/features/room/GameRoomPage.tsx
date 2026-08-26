import { useState } from "react";
import { Link } from "react-router-dom";

import type { ApiClient } from "../../lib/api-client";
import { ActionPanel } from "./ActionPanel";
import { ConnectionStatus } from "./ConnectionStatus";
import { PlayerRail } from "./PlayerRail";
import { PrivatePanel } from "./PrivatePanel";
import { RoomTimeline } from "./RoomTimeline";
import { useRoomSession } from "./use-room-session";

export function GameRoomPage({ roomId, apiClient }: { roomId: string; apiClient: ApiClient }) {
  const session = useRoomSession(roomId, apiClient);
  const [pending, setPending] = useState(false);
  const submit = async (command: Parameters<typeof session.submitCommand>[0]) => { try { setPending(true); await session.submitCommand(command); } finally { setPending(false); } };
  if (!session.snapshot) return <main className="app-shell">正在载入对局…</main>;
  return <main className="game-layout"><header><Link to="/">☾ Werewolf Arena</Link><ConnectionStatus status={session.connection} onRefresh={() => void session.refresh()} onContinue={() => void session.continueRoom()} /></header><div className="game-columns"><RoomTimeline events={session.events} /><aside><PrivatePanel state={session.snapshot} /><PlayerRail state={session.snapshot} /><ActionPanel state={session.snapshot} onSubmit={submit} pending={pending} />{session.error && <p role="alert">{session.error}</p>}{session.snapshot.status === "finished" && <Link className="restart" to="/">再开一局</Link>}</aside></div></main>;
}
