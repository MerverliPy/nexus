"use client";

import { useEffect, useRef } from "react";
import { api } from "./api";

const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL ||
  process.env.NEXT_PUBLIC_API_URL?.replace(/^http/, "ws") + "/ws/tasks" ||
  "ws://localhost:8000/ws/tasks";

export function useWebSocket(onEvent: () => void) {
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let ws: WebSocket | null = null;

    const connect = () => {
      const token = api.getTokens().access;
      if (!token) return;

      ws = new WebSocket(WS_URL);

      ws.onopen = () => {
        ws!.send(JSON.stringify({ token }));
      };

      ws.onmessage = (msg) => {
        try {
          const data = JSON.parse(msg.data);
          if (
            data.event === "task_created" ||
            data.event === "task_updated" ||
            data.event === "task_deleted"
          ) {
            onEvent();
          }
        } catch {
          // ignore parse errors
        }
      };

      ws.onclose = () => {
        ws = null;
        reconnectRef.current = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws?.close();
      };
    };

    connect();

    return () => {
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      ws?.close();
    };
  }, [onEvent]);
}
