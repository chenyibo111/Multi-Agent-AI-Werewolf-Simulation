import type { ProjectedParticipant, RoomEvent } from "../../lib/types";
import { phaseLabel } from "../../lib/game-labels";

export function RoomTimeline({ events, participants = {} }: { events: RoomEvent[]; participants?: Record<string, ProjectedParticipant> }) {
  return <section className="timeline" aria-label="公开对局时间线"><h2>对局叙事</h2>{events.length === 0 ? <p>等待第一条公开事件。</p> : events.map((event) => <article className="timeline-event" key={event.sequence}><span>#{event.sequence}</span><p>{eventText(event, participants)}</p></article>)}</section>;
}

function eventText(event: RoomEvent, participants: Record<string, ProjectedParticipant>): string {
  const payload = event.payload;
  if (event.event_type === "phase_changed" && typeof payload.phase === "string") return `阶段切换：${phaseLabel(payload.phase)}`;
  if (event.event_type === "inspection_result" && typeof payload.target_id === "string" && typeof payload.is_wolf === "boolean") return `查验结果：${displayName(payload.target_id, participants)} ${payload.is_wolf ? "是狼人" : "不是狼人"}。`;
  if (event.event_type === "witch_night_target" && typeof payload.target_id === "string") return `女巫得知：今晚被袭击的是${displayName(payload.target_id, participants)}。`;
  if (event.event_type === "witch_action_result" && isWitchActionResult(payload)) {
    const actions = [
      payload.saved_target_id ? `救下${displayName(payload.saved_target_id, participants)}` : "",
      payload.poisoned_target_id ? `毒杀${displayName(payload.poisoned_target_id, participants)}` : "",
    ].filter(Boolean).join("；") || "未使用药剂";
    return `女巫行动：${actions}；解药${payload.antidote_available ? "可用" : "已用"}，毒药${payload.poison_available ? "可用" : "已用"}。`;
  }
  if (event.event_type === "agent_public_reason" && isPublicReason(payload)) return `${displayName(payload.actor_id, participants)}的${publicReasonLabel(payload.action_kind)}理由：${payload.reason}`;
  if (event.event_type === "agent_private_reason" && isPrivateReason(payload)) return `${displayName(payload.actor_id, participants)}的夜间${nightActionLabel(payload.action_kind)}理由：${payload.reason}`;
  if (event.event_type === "public_speech" && typeof payload.actor_id === "string" && typeof payload.text === "string") return `${displayName(payload.actor_id, participants)}：${payload.text}`;
  if (event.event_type === "night_announcement" && Array.isArray(payload.death_ids) && payload.death_ids.every((id) => typeof id === "string")) return payload.death_ids.length ? `天亮了，昨夜 ${payload.death_ids.map((id) => displayName(id, participants)).join("、")} 出局。` : "平安夜，昨夜无人出局。";
  if (event.event_type === "vote_result" && Array.isArray(payload.votes)) {
    const votes = payload.votes.flatMap((vote) => {
      if (!isVote(vote)) return [];
      const target = vote.target_id === null ? "弃权" : displayName(vote.target_id, participants);
      return `${displayName(vote.actor_id, participants)} → ${target}`;
    });
    if (votes.length) return `投票结果：${votes.join("；")}。`;
  }
  if (event.event_type === "wolf_team_suggestion" && typeof payload.actor_id === "string" && typeof payload.target_id === "string" && typeof payload.message === "string") return `狼人同伴 ${displayName(payload.actor_id, participants)} 建议击杀 ${displayName(payload.target_id, participants)}：${payload.message}`;
  if (event.event_type === "execution" && typeof payload.target_id === "string") return `${displayName(payload.target_id, participants)} 被放逐出局。`;
  if (event.event_type === "vote_no_execution") return "本轮无人被放逐。";
  if (event.event_type === "vote_tied") return "投票平局，本轮无人被放逐。";
  if (event.event_type === "game_finished" && typeof payload.winner_faction === "string") return `对局结束，${payload.winner_faction} 阵营获胜。`;
  return "对局状态已更新。";
}

function displayName(participantId: string, participants: Record<string, ProjectedParticipant>): string {
  return participants[participantId]?.display_name ?? participantId;
}

function isVote(value: unknown): value is { actor_id: string; target_id: string | null } {
  return typeof value === "object" && value !== null
    && typeof (value as Record<string, unknown>).actor_id === "string"
    && (typeof (value as Record<string, unknown>).target_id === "string" || (value as Record<string, unknown>).target_id === null);
}

function isWitchActionResult(value: Record<string, unknown>): value is {
  saved_target_id: string | null;
  poisoned_target_id: string | null;
  antidote_available: boolean;
  poison_available: boolean;
} {
  return (typeof value.saved_target_id === "string" || value.saved_target_id === null)
    && (typeof value.poisoned_target_id === "string" || value.poisoned_target_id === null)
    && typeof value.antidote_available === "boolean"
    && typeof value.poison_available === "boolean";
}

function isPublicReason(value: Record<string, unknown>): value is {
  actor_id: string;
  action_kind: "speak" | "vote" | "abstain";
  reason: string;
} {
  return typeof value.actor_id === "string"
    && typeof value.reason === "string"
    && (value.action_kind === "speak" || value.action_kind === "vote" || value.action_kind === "abstain");
}

function isPrivateReason(value: Record<string, unknown>): value is {
  actor_id: string;
  action_kind: "wolf_kill" | "inspect" | "witch_save" | "witch_poison";
  target_id: string;
  reason: string;
} {
  return typeof value.actor_id === "string"
    && typeof value.target_id === "string"
    && typeof value.reason === "string"
    && (value.action_kind === "wolf_kill"
      || value.action_kind === "inspect"
      || value.action_kind === "witch_save"
      || value.action_kind === "witch_poison");
}

function publicReasonLabel(actionKind: "speak" | "vote" | "abstain"): string {
  return { speak: "发言", vote: "投票", abstain: "弃权" }[actionKind];
}

function nightActionLabel(actionKind: "wolf_kill" | "inspect" | "witch_save" | "witch_poison"): string {
  return {
    wolf_kill: "狼人击杀",
    inspect: "预言家查验",
    witch_save: "女巫救人",
    witch_poison: "女巫用毒",
  }[actionKind];
}
