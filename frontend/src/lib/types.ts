export type HumanAction =
  | "speak"
  | "end_discussion"
  | "wolf_kill"
  | "inspect"
  | "witch_save"
  | "witch_poison"
  | "vote"
  | "abstain"
  | "noop";

export type HumanCommand = {
  kind: HumanAction;
  target_id?: string;
  text?: string;
};

export type ProjectedParticipant = {
  participant_id: string;
  display_name: string;
  alive: boolean;
  role_id?: string;
  private_state?: Record<string, unknown>;
};

export type RoomSnapshot = {
  game_id: string;
  phase: string;
  status: "running" | "finished";
  round_number: number;
  participants: Record<string, ProjectedParticipant>;
  waiting_for_human: boolean;
  human_actions: HumanAction[];
  legal_target_ids: string[];
  phase_text: string;
  view_mode: "active" | "spectating" | "finished";
};

export type RoomEvent = {
  sequence: number;
  event_type: string;
  payload: Record<string, unknown>;
  visibility: "public" | "private";
};

export type RoomPayload = {
  state: RoomSnapshot;
  events: RoomEvent[];
};

export type RoomReport = {
  winner_faction: string | null;
  participants: Record<string, ProjectedParticipant>;
  events: RoomEvent[];
};

export type CreatedRoom = RoomPayload & {
  roomId: string;
};
