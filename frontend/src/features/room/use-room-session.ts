import { useCallback, useEffect, useRef, useState } from "react";

import type { ApiClient } from "../../lib/api-client";
import type { HumanCommand, RoomEvent, RoomPayload, RoomSnapshot } from "../../lib/types";
import { mergeRoomEvents } from "./event-store";

export type ConnectionStatus = "loading" | "connected" | "reconnecting" | "offline" | "error";

type RoomSession = {
  snapshot: RoomSnapshot | null;
  events: RoomEvent[];
  connection: ConnectionStatus;
  error: string | null;
  refresh: () => Promise<void>;
  continueRoom: () => Promise<void>;
  submitCommand: (command: HumanCommand) => Promise<void>;
};

const reconnectDelays = [500, 1_000, 2_000, 4_000];

export function useRoomSession(roomId: string, apiClient: ApiClient): RoomSession {
  const [snapshot, setSnapshot] = useState<RoomSnapshot | null>(null);
  const [events, setEvents] = useState<RoomEvent[]>([]);
  const [connection, setConnection] = useState<ConnectionStatus>("loading");
  const [error, setError] = useState<string | null>(null);
  const latestSequence = useRef(0);

  const mergeEvents = useCallback((incoming: RoomEvent[]) => {
    setEvents((current) => {
      const merged = mergeRoomEvents(current, incoming);
      latestSequence.current = merged.at(-1)?.sequence ?? 0;
      return merged;
    });
  }, []);

  const applyPayload = useCallback(
    (payload: RoomPayload) => {
      setSnapshot(payload.state);
      latestSequence.current = Math.max(
        latestSequence.current,
        ...payload.events.map((event) => event.sequence),
      );
      mergeEvents(payload.events);
    },
    [mergeEvents],
  );

  const refresh = useCallback(async () => {
    try {
      setError(null);
      applyPayload(await apiClient.getRoom(roomId));
    } catch (caught) {
      setError(messageFor(caught));
      setConnection("error");
    }
  }, [apiClient, applyPayload, roomId]);

  const continueRoom = useCallback(async () => {
    try {
      setError(null);
      applyPayload(await apiClient.continueRoom(roomId));
    } catch (caught) {
      setError(messageFor(caught));
    }
  }, [apiClient, applyPayload, roomId]);

  const submitCommand = useCallback(
    async (command: HumanCommand) => {
      try {
        setError(null);
        applyPayload(await apiClient.submitCommand(roomId, command));
      } catch (caught) {
        setError(messageFor(caught));
        throw caught;
      }
    },
    [apiClient, applyPayload, roomId],
  );

  useEffect(() => {
    let disposed = false;
    let socket: WebSocket | undefined;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let retries = 0;

    const connect = () => {
      if (disposed) return;
      socket = new WebSocket(socketUrl(roomId, latestSequence.current));
      socket.onmessage = (message) => {
        try {
          const envelope = JSON.parse(message.data) as { type?: string; events?: RoomEvent[] };
          if (envelope.type === "events" && Array.isArray(envelope.events)) mergeEvents(envelope.events);
        } catch {
          setError("收到无法识别的对局事件。");
        }
      };
      socket.onerror = () => setConnection("reconnecting");
      socket.onclose = () => {
        if (disposed) return;
        const delay = reconnectDelays[retries++];
        if (delay === undefined) {
          setConnection("offline");
          return;
        }
        setConnection("reconnecting");
        retryTimer = setTimeout(connect, delay);
      };
      setConnection("connected");
    };

    void (async () => {
      try {
        applyPayload(await apiClient.getRoom(roomId));
        connect();
      } catch (caught) {
        setError(messageFor(caught));
        setConnection("error");
      }
    })();

    return () => {
      disposed = true;
      if (retryTimer !== undefined) clearTimeout(retryTimer);
      socket?.close();
    };
  }, [apiClient, applyPayload, mergeEvents, roomId]);

  return { snapshot, events, connection, error, refresh, continueRoom, submitCommand };
}

function socketUrl(roomId: string, sequence: number): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/api/rooms/${encodeURIComponent(roomId)}/events?after_sequence=${sequence}`;
}

function messageFor(caught: unknown): string {
  return caught instanceof Error ? caught.message : "请求未完成，请重试。";
}
