import type { CreatedRoom, HumanCommand, RoomPayload } from "./types";

type CreateRoomResponse = RoomPayload & { room_id: string; session_token?: string };

export class ApiRequestError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export class ApiClient {
  private readonly baseUrl: string;

  constructor(baseUrl = import.meta.env.VITE_API_BASE_URL ?? "") {
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  async createRoom(requestedRoleId?: string): Promise<CreatedRoom> {
    const response = await this.request<CreateRoomResponse>("/api/rooms", {
      method: "POST",
      body: JSON.stringify(requestedRoleId ? { requested_role_id: requestedRoleId } : {}),
    });
    const { room_id: roomId, session_token: _token, ...payload } = response;
    return { ...payload, roomId };
  }

  getRoom(roomId: string): Promise<RoomPayload> {
    return this.request<RoomPayload>(`/api/rooms/${encodeURIComponent(roomId)}`);
  }

  submitCommand(roomId: string, command: HumanCommand): Promise<RoomPayload> {
    return this.request<RoomPayload>(`/api/rooms/${encodeURIComponent(roomId)}/commands`, {
      method: "POST",
      body: JSON.stringify(command),
    });
  }

  continueRoom(roomId: string): Promise<RoomPayload> {
    return this.request<RoomPayload>(`/api/rooms/${encodeURIComponent(roomId)}/continue`, {
      method: "POST",
    });
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      credentials: "include",
      headers: { "Content-Type": "application/json", ...init.headers },
    });
    if (!response.ok) {
      throw new ApiRequestError(await errorMessage(response));
    }
    return (await response.json()) as T;
  }
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    return typeof payload.detail === "string" ? payload.detail : "请求未完成，请重试。";
  } catch {
    return "请求未完成，请重试。";
  }
}
