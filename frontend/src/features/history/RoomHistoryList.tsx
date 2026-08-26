import type { RoomPayload } from "../../lib/types";
import type { RoomHistoryEntry } from "./room-history";

export type LoadedHistoryRoom = { entry: RoomHistoryEntry; payload: RoomPayload | null };

type RoomHistoryListProps = {
  rooms: LoadedHistoryRoom[];
  onContinue: (roomId: string) => void;
  onDelete: (roomId: string) => void;
  onRemoveLocal: (roomId: string) => void;
};

export function RoomHistoryList({ rooms, onContinue, onDelete, onRemoveLocal }: RoomHistoryListProps) {
  if (rooms.length === 0) return <p className="empty-history">暂无本地对局记录</p>;
  return <section className="history-section" aria-label="本地对局历史"><h2>继续对局</h2>{rooms.map(({ entry, payload }) => payload ? <article className="history-card" key={entry.roomId}><div><strong>{payload.state.status === "finished" ? "已结束对局" : "进行中的对局"}</strong><p>{payload.state.phase_text}</p></div><div className="history-actions"><button onClick={() => onContinue(entry.roomId)}>继续对局</button><button className="danger-button" onClick={() => onDelete(entry.roomId)}>删除对局</button></div></article> : <article className="history-card unavailable" key={entry.roomId}><div><strong>无法访问的本地对局</strong><p>该房间已删除或当前浏览器不再拥有访问权限。</p></div><button onClick={() => onRemoveLocal(entry.roomId)}>移除记录</button></article>)}</section>;
}
