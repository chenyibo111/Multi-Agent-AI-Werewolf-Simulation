import type { RoomEvent } from "../../lib/types";

export function RoomTimeline({ events }: { events: RoomEvent[] }) {
  return <section className="timeline" aria-label="公开对局时间线"><h2>对局叙事</h2>{events.length === 0 ? <p>等待第一条公开事件。</p> : events.map((event) => <article className="timeline-event" key={event.sequence}><span>#{event.sequence}</span><p>{eventText(event)}</p></article>)}</section>;
}

function eventText(event: RoomEvent): string {
  const payload = event.payload;
  if (event.event_type === "phase_changed" && typeof payload.phase === "string") return `阶段切换：${payload.phase}`;
  if (event.event_type === "inspection_result" && typeof payload.target_id === "string" && typeof payload.is_wolf === "boolean") return `查验结果：${payload.target_id} ${payload.is_wolf ? "是狼人" : "不是狼人"}。`;
  if (event.event_type === "public_speech" && typeof payload.actor_id === "string" && typeof payload.text === "string") return `${payload.actor_id}：${payload.text}`;
  if (event.event_type === "night_announcement" && Array.isArray(payload.death_ids) && payload.death_ids.every((id) => typeof id === "string")) return payload.death_ids.length ? `天亮了，昨夜 ${payload.death_ids.join("、")} 出局。` : "平安夜，昨夜无人出局。";
  if (event.event_type === "execution" && typeof payload.target_id === "string") return `${payload.target_id} 被放逐出局。`;
  if (event.event_type === "vote_no_execution") return "本轮无人被放逐。";
  if (event.event_type === "vote_tied") return "投票平局，本轮无人被放逐。";
  if (event.event_type === "game_finished" && typeof payload.winner_faction === "string") return `对局结束，${payload.winner_faction} 阵营获胜。`;
  return "对局状态已更新。";
}
