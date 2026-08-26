import type { RoomSnapshot } from "../../lib/types";

export function PlayerRail({ state }: { state: RoomSnapshot }) { return <section className="player-rail"><h2>场上玩家</h2>{Object.values(state.participants).map((player) => <div className="player" key={player.participant_id}><span>{player.alive ? "●" : "○"}</span><span>{player.display_name}</span>{player.role_id && <em>{player.role_id}</em>}</div>)}</section>; }
