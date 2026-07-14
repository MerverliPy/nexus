"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import { MobileNav } from "@/components/mobile-nav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface ParsedIntent {
  intent: string;
  entities: Record<string, unknown>;
}

interface TranscribeResponse {
  text: string | null;
  intent: ParsedIntent;
  source: string;
}

const INTENT_LABELS: Record<string, string> = {
  finance_log: "💰 Log Expense",
  finance_balance: "💰 Check Balance",
  finance_recent: "💰 Recent Transactions",
  task_add: "📋 Add Task",
  unknown: "❓ Unknown",
};

const INTENT_COLORS: Record<string, string> = {
  finance_log: "border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-950",
  finance_balance: "border-purple-200 bg-purple-50 dark:border-purple-800 dark:bg-purple-950",
  finance_recent: "border-purple-200 bg-purple-50 dark:border-purple-800 dark:bg-purple-950",
  task_add: "border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950",
  unknown: "border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-900",
};

export default function VoicePage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [text, setText] = useState("");
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState<TranscribeResponse | null>(null);
  const [error, setError] = useState("");

  // TTS
  const [ttsText, setTtsText] = useState("");
  const [ttsVoice, setTtsVoice] = useState("alloy");
  const [ttsProcessing, setTtsProcessing] = useState(false);
  const audioRef = useRef<HTMLAudioElement>(null);

  // Recording
  const [recording, setRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  // Voice commands history
  const [history, setHistory] = useState<{ text: string; intent: ParsedIntent }[]>([]);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [user, loading, router]);

  const handleParse = async () => {
    if (!text.trim()) return;
    setProcessing(true);
    setError("");
    setResult(null);
    try {
      const res = await fetch(
        `${api.getAPIBase()}/api/v1/voice/transcribe?text=${encodeURIComponent(text.trim())}`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${api.getTokens().access}` },
        }
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: "Request failed" }));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const data: TranscribeResponse = await res.json();
      setResult(data);
      setHistory((prev) => [{ text: text.trim(), intent: data.intent }, ...prev].slice(0, 20));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to parse command");
    } finally {
      setProcessing(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleParse();
    }
  };

  const handleTts = async () => {
    if (!ttsText.trim()) return;
    setTtsProcessing(true);
    setError("");
    try {
      const res = await fetch(`${api.getAPIBase()}/api/v1/voice/speak`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${api.getTokens().access}`,
        },
        body: JSON.stringify({ text: ttsText.trim(), voice: ttsVoice }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: "TTS failed" }));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      if (audioRef.current) {
        audioRef.current.src = url;
        audioRef.current.play();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "TTS failed");
    } finally {
      setTtsProcessing(false);
    }
  };

  const handleQuickAction = (action: string) => {
    const commands: Record<string, string> = {
      "log-coffee": "log 5 dollars for coffee",
      "log-lunch": "spent 15 at subway",
      "add-task": "remind me to review the budget",
      "check-balance": "whats my balance",
      "recent": "last transaction",
    };
    setText(commands[action] || "");
  };

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-muted-foreground">Loading…</p>
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="flex flex-1 flex-col">
      {/* Header */}
      <header className="flex items-center justify-between border-b px-6 py-3">
        <h1 className="text-xl font-semibold">Voice</h1>
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground">{user.email}</span>
          <Button variant="outline" size="sm" onClick={() => router.push("/dashboard")}>
            Dashboard
          </Button>
        </div>
      </header>

      <main className="flex-1 space-y-6 p-6 pb-24 md:pb-6">
        {/* Error */}
        {error && (
          <Card className="border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950">
            <CardContent className="p-4">
              <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
            </CardContent>
          </Card>
        )}

        {/* Command Input */}
        <Card>
          <CardHeader>
            <CardTitle>Voice Command</CardTitle>
            <CardDescription>Type a command or use the quick actions below</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Input
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder='e.g. "log 5 dollars for coffee" or "remind me to buy groceries"'
                className="flex-1"
              />
              <Button onClick={handleParse} disabled={processing || !text.trim()}>
                {processing ? "Parsing…" : "Parse"}
              </Button>
            </div>

            {/* Quick actions */}
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={() => handleQuickAction("log-coffee")}>
                ☕ Log Coffee
              </Button>
              <Button variant="outline" size="sm" onClick={() => handleQuickAction("log-lunch")}>
                🥪 Log Lunch
              </Button>
              <Button variant="outline" size="sm" onClick={() => handleQuickAction("add-task")}>
                📋 Add Task
              </Button>
              <Button variant="outline" size="sm" onClick={() => handleQuickAction("check-balance")}>
                💰 Balance
              </Button>
              <Button variant="outline" size="sm" onClick={() => handleQuickAction("recent")}>
                🧾 Recent
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Parse Result */}
        {result && (
          <Card className={INTENT_COLORS[result.intent.intent] || ""}>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-lg">
                {INTENT_LABELS[result.intent.intent] || "❓ Unknown"}
              </CardTitle>
              {result.text && (
                <CardDescription>
                  "{result.text}" — via {result.source}
                </CardDescription>
              )}
            </CardHeader>
            <CardContent>
              <pre className="overflow-x-auto rounded bg-black/5 p-3 text-sm dark:bg-white/5">
                {JSON.stringify(result.intent, null, 2)}
              </pre>
            </CardContent>
          </Card>
        )}

        {/* Text-to-Speech */}
        <Card>
          <CardHeader>
            <CardTitle>Text to Speech</CardTitle>
            <CardDescription>Convert text to spoken audio</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Textarea
                value={ttsText}
                onChange={(e) => setTtsText(e.target.value)}
                placeholder="Type something to speak…"
                rows={2}
                className="flex-1"
              />
            </div>
            <div className="flex items-center gap-2">
              <select
                value={ttsVoice}
                onChange={(e) => setTtsVoice(e.target.value)}
                className="rounded-md border bg-background px-3 py-2 text-sm"
              >
                <option value="alloy">Alloy</option>
                <option value="echo">Echo</option>
                <option value="fable">Fable</option>
                <option value="onyx">Onyx</option>
                <option value="nova">Nova</option>
                <option value="shimmer">Shimmer</option>
              </select>
              <Button onClick={handleTts} disabled={ttsProcessing || !ttsText.trim()}>
                {ttsProcessing ? "Generating…" : "🔊 Speak"}
              </Button>
            </div>
            <audio ref={audioRef} controls className="w-full" />
          </CardContent>
        </Card>

        {/* Command History */}
        {history.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Recent Commands</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {history.map((item, i) => (
                  <div
                    key={i}
                    className="flex cursor-pointer items-center justify-between rounded-lg border p-3 transition-colors hover:bg-accent"
                    onClick={() => setText(item.text)}
                  >
                    <span className="text-sm font-medium">{item.text}</span>
                    <span className="text-xs text-muted-foreground">
                      {INTENT_LABELS[item.intent.intent] || item.intent.intent}
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </main>

      <MobileNav />
    </div>
  );
}
