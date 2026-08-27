import type { RoomReport } from "../../lib/types";
import { factionLabel, roleLabel } from "../../lib/game-labels";

export function FinishedReport({ report }: { report: RoomReport }) {
  return <section className="finished-report"><h2>完整复盘</h2><p>{report.winner_faction ? `${factionLabel(report.winner_faction)}获胜` : "胜者未知"}</p><div>{Object.values(report.participants).map((player) => <p key={player.participant_id}>{player.display_name} · {player.role_id ? roleLabel(player.role_id) : "未知身份"}</p>)}</div></section>;
}
