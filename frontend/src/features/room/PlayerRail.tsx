import type { RoomSnapshot } from "../../lib/types";
import { roleLabel } from "../../lib/game-labels";

export function PlayerRail({ state }: { state: RoomSnapshot }) { return <section className="player-rail"><h2>场上玩家</h2>{Object.values(state.participants).sort((left, right) => (left.seat_number ?? 0) - (right.seat_number ?? 0)).map((player) => <div className="player" key={player.participant_id}><span className={`player-status ${player.alive ? "alive" : "dead"}`}>{player.alive ? "存活" : "已出局"}</span><span>{player.seat_number !== undefined ? `${player.seat_number}号 ${player.display_name}` : player.display_name}</span>{player.role_id && <em>{roleLabel(player.role_id)}</em>}</div>)}</section>; }
