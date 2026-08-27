import type { RoomSnapshot } from "../../lib/types";

export function PlayerRail({ state }: { state: RoomSnapshot }) { return <section className="player-rail"><h2>场上玩家</h2>{Object.values(state.participants).sort((left, right) => (left.seat_number ?? 0) - (right.seat_number ?? 0)).map((player) => <div className="player" key={player.participant_id}><span>{player.alive ? "●" : "○"}</span><span>{player.seat_number !== undefined ? `${player.seat_number}号 ${player.display_name}` : player.display_name}</span>{player.role_id && <em>{player.role_id}</em>}</div>)}</section>; }
