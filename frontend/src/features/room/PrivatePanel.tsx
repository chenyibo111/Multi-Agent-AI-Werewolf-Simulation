import type { RoomSnapshot } from "../../lib/types";

export function PrivatePanel({ state }: { state: RoomSnapshot }) { const human = state.participants.human; return <section className="private-panel"><p className="eyebrow">你的身份</p><h2>{human?.role_id ?? "身份加载中"}</h2><p>{state.phase_text}</p><p className="muted">第 {state.round_number} 回合</p></section>; }
