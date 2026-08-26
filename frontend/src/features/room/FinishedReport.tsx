import type { RoomReport } from "../../lib/types";

export function FinishedReport({ report }: { report: RoomReport }) {
  return <section className="finished-report"><h2>完整复盘</h2><p>{report.winner_faction ?? "未知"} 阵营获胜</p><div>{Object.values(report.participants).map((player) => <p key={player.participant_id}>{player.display_name} · {player.role_id ?? "未知身份"}</p>)}</div></section>;
}
