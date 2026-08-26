import { useState } from "react";

type Props = { onCreate: (roleId?: string) => Promise<void>; pending: boolean; error: string | null };

export function CreateGameForm({ onCreate, pending, error }: Props) {
  const [roleId, setRoleId] = useState("");
  return <form className="create-form" onSubmit={(event) => { event.preventDefault(); void onCreate(roleId || undefined); }}>
    <label htmlFor="role">选择身份</label>
    <select id="role" value={roleId} onChange={(event) => setRoleId(event.target.value)} disabled={pending}>
      <option value="">随机身份</option><option value="wolf">狼人</option><option value="seer">预言家</option><option value="witch">女巫</option><option value="villager">村民</option>
    </select>
    <button type="submit" disabled={pending}>{pending ? "正在创建…" : "开始对局"}</button>
    {error && <p role="alert">{error}</p>}
  </form>;
}
