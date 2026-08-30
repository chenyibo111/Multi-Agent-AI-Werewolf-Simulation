import type { RoomReport } from "../../lib/types";
import { factionLabel, roleLabel } from "../../lib/game-labels";
import { RoomTimeline } from "./RoomTimeline";
import { ReplayRecap } from "./ReplayRecap";

export function FinishedReport({ report }: { report: RoomReport }) {
  return <section className="finished-report">
    <h2>完整复盘</h2>
    <p className="replay-winner">{report.winner_faction ? `${factionLabel(report.winner_faction)}获胜` : "胜者未知"}</p>
    <section className="role-reveal" aria-label="身份揭晓">
      <h3>身份揭晓</h3>
      <ul>{Object.values(report.participants).sort((left, right) => (left.seat_number ?? 0) - (right.seat_number ?? 0)).map((player) => <li key={player.participant_id}>{player.seat_number ? `${player.seat_number}号 ` : ""}{player.display_name} · {player.role_id ? roleLabel(player.role_id) : "未知身份"} · {player.alive ? "存活" : "已出局"}</li>)}</ul>
    </section>
    <ReplayRecap events={report.events} participants={report.participants} />
    <details className="replay-audit">
      <summary>查看完整事件时间线</summary>
      <RoomTimeline title="完整事件时间线" ariaLabel="完整事件时间线" events={report.events} participants={report.participants} />
    </details>
  </section>;
}
