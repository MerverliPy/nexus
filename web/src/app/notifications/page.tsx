"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { api, type Notification, type NotificationPreferences } from "@/lib/api";
import { MobileNav } from "@/components/mobile-nav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

function formatDate(dateStr: string | null) {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function statusBadge(status: string) {
  const variants: Record<string, string> = {
    pending: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300",
    sent: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
    failed: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
  };
  return (
    <Badge className={variants[status] || ""} variant="outline">
      {status === "pending" ? "Unread" : status === "sent" ? "Read" : status}
    </Badge>
  );
}

function priorityBadge(priority: string) {
  const variants: Record<string, string> = {
    urgent: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
    normal: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
    digest: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300",
  };
  return (
    <Badge className={variants[priority] || ""} variant="outline">
      {priority}
    </Badge>
  );
}

function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <label className="flex items-center gap-3 cursor-pointer">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
          checked ? "bg-primary" : "bg-input"
        }`}
      >
        <span
          className={`inline-block h-3.5 w-3.5 transform rounded-full bg-background transition-transform ${
            checked ? "translate-x-[18px]" : "translate-x-[3px]"
          }`}
        />
      </button>
      <span className="text-sm">{label}</span>
    </label>
  );
}

export default function NotificationsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [notifLoading, setNotifLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);

  // Create dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [createTitle, setCreateTitle] = useState("");
  const [createBody, setCreateBody] = useState("");
  const [createPriority, setCreatePriority] = useState("normal");
  const [creating, setCreating] = useState(false);

  // Digest
  const [digesting, setDigesting] = useState(false);
  const [digestResult, setDigestResult] = useState<{ bundled: number; sent: boolean } | null>(null);

  // Preferences
  const [prefsOpen, setPrefsOpen] = useState(false);
  const [prefs, setPrefs] = useState<NotificationPreferences | null>(null);
  const [prefsLoading, setPrefsLoading] = useState(false);
  const [savingPrefs, setSavingPrefs] = useState(false);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (user) {
      loadNotifications();
    }
  }, [user]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadNotifications = async () => {
    setNotifLoading(true);
    setError("");
    try {
      const data = await api.listNotifications(statusFilter);
      setNotifications(data);
    } catch (err) {
      console.error("Failed to load notifications", err);
      setError("Failed to load notifications.");
    } finally {
      setNotifLoading(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      await api.createNotification({
        title: createTitle,
        body: createBody || undefined,
        priority: createPriority,
      });
      setCreateTitle("");
      setCreateBody("");
      setCreatePriority("normal");
      setCreateOpen(false);
      await loadNotifications();
    } catch (err) {
      console.error("Create notification failed", err);
    } finally {
      setCreating(false);
    }
  };

  const handleDigest = async () => {
    setDigesting(true);
    setDigestResult(null);
    try {
      const result = await api.triggerDigest();
      setDigestResult(result);
      await loadNotifications();
    } catch (err) {
      console.error("Digest failed", err);
    } finally {
      setDigesting(false);
    }
  };

  const openPreferences = async () => {
    setPrefsOpen(true);
    setPrefsLoading(true);
    try {
      const data = await api.getPreferences();
      setPrefs(data);
    } catch (err) {
      console.error("Failed to load preferences", err);
    } finally {
      setPrefsLoading(false);
    }
  };

  const handleSavePrefs = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prefs) return;
    setSavingPrefs(true);
    try {
      const updated = await api.updatePreferences({
        digest_hour: prefs.digest_hour,
        urgent_immediate: prefs.urgent_immediate,
        bundle_normal: prefs.bundle_normal,
        telegram_chat_id: prefs.telegram_chat_id,
      });
      setPrefs(updated);
      setPrefsOpen(false);
    } catch (err) {
      console.error("Save preferences failed", err);
    } finally {
      setSavingPrefs(false);
    }
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
        <h1 className="text-xl font-semibold">Notifications</h1>
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => router.push("/dashboard")}>
            Dashboard
          </Button>
          <span className="text-sm text-muted-foreground">{user.email}</span>
          <Button variant="outline" size="sm" onClick={() => router.push("/login")}>
            Sign Out
          </Button>
        </div>
      </header>

      <main className="flex-1 p-6 pb-24 md:pb-6">
        {/* Actions row */}
        <div className="mb-6 flex flex-wrap gap-2">
          <Button onClick={() => setCreateOpen(true)}>New Notification</Button>
          <Button variant="secondary" onClick={handleDigest} disabled={digesting}>
            {digesting ? "Sending…" : "Send Digest"}
          </Button>
          <Button variant="outline" onClick={openPreferences}>
            Preferences
          </Button>
          <Button variant="ghost" onClick={() => { setStatusFilter(undefined); loadNotifications(); }}>
            All
          </Button>
          <Button variant="ghost" onClick={() => { setStatusFilter("pending"); loadNotifications(); }}>
            Unread
          </Button>
          <Button variant="ghost" onClick={() => { setStatusFilter("sent"); loadNotifications(); }}>
            Sent
          </Button>
        </div>

        {/* Digest result */}
        {digestResult && (
          <Card className="mb-6 border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950">
            <CardContent className="p-4">
              <p className="text-sm text-green-700 dark:text-green-300">
                Digest sent — {digestResult.bundled} notification{digestResult.bundled !== 1 ? "s" : ""} bundled
                {digestResult.sent ? " and delivered." : "."}
              </p>
            </CardContent>
          </Card>
        )}

        {/* Error */}
        {error && (
          <Card className="mb-6 border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950">
            <CardContent className="p-4">
              <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
            </CardContent>
          </Card>
        )}

        {/* Notification list */}
        {notifLoading ? (
          <div className="flex items-center justify-center py-12">
            <p className="text-muted-foreground">Loading notifications…</p>
          </div>
        ) : notifications.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <p className="text-muted-foreground">No notifications.</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Create one to test the notification system.
              </p>
              <Button className="mt-4" onClick={() => setCreateOpen(true)}>
                Create Notification
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {notifications.map((notif) => (
              <Card key={notif.id} className={notif.status === "pending" ? "border-l-4 border-l-yellow-500" : ""}>
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <CardTitle className="text-base">{notif.title}</CardTitle>
                      <CardDescription>
                        {formatDate(notif.created_at)}
                      </CardDescription>
                    </div>
                    <div className="flex items-center gap-2">
                      {priorityBadge(notif.priority)}
                      {statusBadge(notif.status)}
                    </div>
                  </div>
                </CardHeader>
                {notif.body && (
                  <CardContent>
                    <p className="text-sm text-muted-foreground whitespace-pre-wrap">{notif.body}</p>
                  </CardContent>
                )}
                <CardContent className="pt-0">
                  <div className="flex gap-2 text-xs text-muted-foreground">
                    <span>Channel: {notif.channel}</span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </main>

      {/* Create dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <form onSubmit={handleCreate}>
            <DialogHeader>
              <DialogTitle>Create Notification</DialogTitle>
              <DialogDescription>
                Send a notification to yourself.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <label htmlFor="notifTitle" className="text-sm font-medium">Title</label>
                <Input
                  id="notifTitle"
                  value={createTitle}
                  onChange={(e) => setCreateTitle(e.target.value)}
                  placeholder="Notification title"
                  required
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="notifBody" className="text-sm font-medium">Body</label>
                <Textarea
                  id="notifBody"
                  value={createBody}
                  onChange={(e) => setCreateBody(e.target.value)}
                  placeholder="Optional message body…"
                  rows={3}
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="notifPriority" className="text-sm font-medium">Priority</label>
                <Select value={createPriority} onValueChange={(v) => v && setCreatePriority(v)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="urgent">Urgent — sent immediately</SelectItem>
                    <SelectItem value="normal">Normal — bundled into next digest</SelectItem>
                    <SelectItem value="digest">Digest — bundled into daily summary</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button type="submit" disabled={creating}>
                {creating ? "Creating…" : "Create"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Preferences dialog */}
      <Dialog open={prefsOpen} onOpenChange={setPrefsOpen}>
        <DialogContent>
          <form onSubmit={handleSavePrefs}>
            <DialogHeader>
              <DialogTitle>Notification Preferences</DialogTitle>
              <DialogDescription>
                Configure how notifications are delivered.
              </DialogDescription>
            </DialogHeader>
            {prefsLoading ? (
              <div className="py-8 text-center text-sm text-muted-foreground">Loading preferences…</div>
            ) : prefs ? (
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <label htmlFor="digestHour" className="text-sm font-medium">
                    Daily Digest Hour (UTC)
                  </label>
                  <Input
                    id="digestHour"
                    type="number"
                    min={0}
                    max={23}
                    value={prefs.digest_hour}
                    onChange={(e) => setPrefs({ ...prefs, digest_hour: parseInt(e.target.value) || 9 })}
                  />
                </div>
                <Toggle
                  checked={prefs.urgent_immediate}
                  onChange={(v) => setPrefs({ ...prefs, urgent_immediate: v })}
                  label="Send urgent notifications immediately"
                />
                <Toggle
                  checked={prefs.bundle_normal}
                  onChange={(v) => setPrefs({ ...prefs, bundle_normal: v })}
                  label="Bundle normal-priority notifications into digest"
                />
                <div className="space-y-2">
                  <label htmlFor="telegramChatId" className="text-sm font-medium">
                    Telegram Chat ID (optional)
                  </label>
                  <Input
                    id="telegramChatId"
                    value={prefs.telegram_chat_id || ""}
                    onChange={(e) => setPrefs({ ...prefs, telegram_chat_id: e.target.value || null })}
                    placeholder="e.g. 123456789"
                  />
                </div>
              </div>
            ) : (
              <div className="py-8 text-center text-sm text-red-500">Failed to load preferences.</div>
            )}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setPrefsOpen(false)}>Cancel</Button>
              <Button type="submit" disabled={savingPrefs || !prefs}>
                {savingPrefs ? "Saving…" : "Save"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <MobileNav />
    </div>
  );
}
