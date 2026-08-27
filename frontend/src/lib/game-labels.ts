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

const phaseLabels: Record<string, string> = {
  night_wolf: "狼人行动阶段",
  night_seer: "预言家查验阶段",
  night_witch: "女巫行动阶段",
  day_discussion: "白天讨论阶段",
  day_vote: "白天投票阶段",
  finished: "对局结束",
};

export function roleLabel(roleId: string): string {
  return roleLabels[roleId] ?? roleId;
}

export function factionLabel(factionId: string): string {
  return factionLabels[factionId] ?? factionId;
}

export function phaseLabel(phaseId: string): string {
  return phaseLabels[phaseId] ?? phaseId;
}
