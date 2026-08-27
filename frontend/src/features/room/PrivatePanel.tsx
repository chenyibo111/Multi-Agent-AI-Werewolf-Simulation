import type { RoomSnapshot } from "../../lib/types";
import { roleLabel } from "../../lib/game-labels";

export function PrivatePanel({ state }: { state: RoomSnapshot }) {
  const human = state.participants.human;
  const isWitch = human?.role_id === "witch";
  const antidoteAvailable = human?.private_state?.antidote_available === true;
  const poisonAvailable = human?.private_state?.poison_available === true;

  return <section className="private-panel"><p className="eyebrow">你的身份</p><h2>{human?.role_id ? roleLabel(human.role_id) : "身份加载中"}</h2>{state.wolf_teammates?.map((teammate) => <p key={teammate.participant_id}>你的狼人同伴：{teammate.seat_number ?? "?"}号 {teammate.display_name}</p>)}{isWitch && <p>解药：{antidoteAvailable ? "可用" : "已用"}；毒药：{poisonAvailable ? "可用" : "已用"}</p>}<p>当前阶段：{state.phase_text}</p><p className="muted">第 {state.round_number} 回合</p></section>;
}
