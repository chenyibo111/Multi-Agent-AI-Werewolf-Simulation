import type { ProjectedParticipant, RoomEvent } from "../../lib/types";
import { eventText } from "./RoomTimeline";

type ReplayRound = {
  number: number;
  nightEvents: RoomEvent[];
  dayEvents: RoomEvent[];
};

export function ReplayRecap({
  events,
  participants,
}: {
  events: RoomEvent[];
  participants: Record<string, ProjectedParticipant>;
}) {
  const rounds = buildReplayRounds(events);
  if (rounds.length === 0) return null;

  return <section className="replay-recap" aria-label="按回合复盘">
    <h2>按回合复盘</h2>
    {rounds.map((round) => <article className="replay-round" key={round.number}>
      {round.nightEvents.length > 0 && <RecapBlock title={`第 ${round.number} 夜`} events={round.nightEvents} participants={participants} />}
      {round.dayEvents.length > 0 && <RecapBlock title={`第 ${round.number} 天`} events={round.dayEvents} participants={participants} />}
    </article>)}
  </section>;
}

function RecapBlock({
  title,
  events,
  participants,
}: {
  title: string;
  events: RoomEvent[];
  participants: Record<string, ProjectedParticipant>;
}) {
  return <section className="replay-block">
    <h3>{title}</h3>
    <ul>{events.map((event) => <li key={event.sequence}>{eventText(event, participants)}</li>)}</ul>
  </section>;
}

function buildReplayRounds(events: RoomEvent[]): ReplayRound[] {
  const rounds: ReplayRound[] = [];
  let currentRound: ReplayRound | undefined;
  let period: "night" | "day" = "night";

  for (const event of events) {
    const phase = event.event_type === "phase_changed" && typeof event.payload.phase === "string"
      ? event.payload.phase
      : undefined;
    if (phase === "night_wolf") {
      currentRound = { number: rounds.length + 1, nightEvents: [], dayEvents: [] };
      rounds.push(currentRound);
      period = "night";
      continue;
    }
    if (!currentRound || event.event_type === "game_finished" || phase) {
      if (phase === "day_discussion" || phase === "day_vote") period = "day";
      if (phase === "night_seer" || phase === "night_witch") period = "night";
      continue;
    }
    (period === "night" ? currentRound.nightEvents : currentRound.dayEvents).push(event);
  }

  return rounds.filter((round) => round.nightEvents.length > 0 || round.dayEvents.length > 0);
}
