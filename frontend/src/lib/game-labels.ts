const roleLabels: Record<string, string> = {
  wolf: "狼人",
  seer: "预言家",
  witch: "女巫",
  villager: "平民",
};

const factionLabels: Record<string, string> = {
  wolf: "狼人阵营",
  good: "好人阵营",
  villager: "好人阵营",
};

export function roleLabel(roleId: string): string {
  return roleLabels[roleId] ?? roleId;
}

export function factionLabel(factionId: string): string {
  return factionLabels[factionId] ?? factionId;
}
