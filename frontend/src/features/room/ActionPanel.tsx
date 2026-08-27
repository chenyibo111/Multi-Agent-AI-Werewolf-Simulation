import { useState } from "react";

import type { HumanAction, HumanCommand, RoomSnapshot } from "../../lib/types";

const targetKinds = new Set<HumanAction>(["wolf_kill", "inspect", "witch_save", "witch_poison", "vote"]);
const labels: Partial<Record<HumanAction, string>> = {
  inspect: "确认查验", wolf_kill: "确认袭击", witch_save: "确认使用解药", witch_poison: "确认使用毒药", vote: "确认投票", abstain: "弃权", noop: "跳过行动", end_discussion: "结束讨论",
};

export function ActionPanel({ state, onSubmit, pending }: { state: RoomSnapshot; onSubmit: (command: HumanCommand) => Promise<void>; pending: boolean }) {
  const [selected, setSelected] = useState<string | null>(null);
  const [speech, setSpeech] = useState("");
  if (!state.waiting_for_human) return <section className="action-panel"><h2>行动面板</h2><p>AI 正在行动，请稍候。</p></section>;
  const submit = (command: HumanCommand) => { void onSubmit(command); };
  return <section className="action-panel"><h2>轮到你行动</h2>
    {state.human_actions.includes("speak") && <><textarea aria-label="公开发言" value={speech} maxLength={500} onChange={(event) => setSpeech(event.target.value)} /><button disabled={pending || !speech.trim()} onClick={() => submit({ kind: "speak", text: speech.trim() })}>发表发言</button></>}
    {state.human_actions.filter((kind) => targetKinds.has(kind)).map((kind) => {
      const fixedTargetId = state.fixed_target_ids?.[kind];
      if (fixedTargetId) return <div key={kind}><p>今晚被袭击：{state.participants[fixedTargetId]?.display_name ?? fixedTargetId}</p><button disabled={pending} onClick={() => submit({ kind, target_id: fixedTargetId })}>{labels[kind]}</button></div>;
      return <div key={kind}><p>请选择目标</p><div className="targets">{state.legal_target_ids.map((id) => <button className={selected === id ? "selected" : ""} key={id} disabled={pending} onClick={() => setSelected(id)}>{state.participants[id]?.display_name ?? id}</button>)}</div><button disabled={pending || !selected} onClick={() => selected && submit({ kind, target_id: selected })}>{labels[kind]}</button></div>;
    })}
    {state.human_actions.filter((kind) => kind !== "speak" && !targetKinds.has(kind)).map((kind) => <button key={kind} disabled={pending} onClick={() => submit({ kind })}>{labels[kind] ?? kind}</button>)}</section>;
}
