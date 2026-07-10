"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { api, type Task } from "@/lib/api";
import { useWebSocket } from "@/lib/use-websocket";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function formatDate(dateStr: string | null) {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function getDueDateClass(dateStr: string | null, status: string) {
  if (status === "completed" || !dateStr) return "";
  const d = new Date(dateStr);
  const now = new Date();
  return d < now ? "text-red-600 font-medium" : "";
}

function statusBadge(status: string) {
  const variants: Record<string, string> = {
    pending: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300",
    completed: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  };
  return (
    <Badge className={variants[status] || ""} variant="outline">
      {status}
    </Badge>
  );
}

function priorityLabel(p: number) {
  if (p >= 5) return "High";
  if (p >= 2) return "Medium";
  return "Normal";
}

export default function DashboardPage() {
  const { user, loading, logout, tasks, refreshTasks } = useAuth();
  const router = useRouter();
  const [filter, setFilter] = useState<string>("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("0");
  const [dueDate, setDueDate] = useState("");
  const [recurrence, setRecurrence] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (user) {
      refreshTasks();
    }
  }, [user]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleRefresh = useCallback(() => {
    refreshTasks(filter === "all" ? undefined : filter);
  }, [refreshTasks, filter]);

  useWebSocket(handleRefresh);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      await api.createTask({
        title,
        description: description || undefined,
        priority: parseInt(priority),
        due_date: dueDate || null,
        recurrence_rule: recurrence || null,
      });
      setTitle("");
      setDescription("");
      setPriority("0");
      setDueDate("");
      setRecurrence("");
      setCreateOpen(false);
      await refreshTasks(filter === "all" ? undefined : filter);
    } catch (err) {
      console.error("Create failed", err);
    } finally {
      setCreating(false);
    }
  };

  const handleComplete = async (id: number) => {
    await api.completeTask(id);
    await refreshTasks(filter === "all" ? undefined : filter);
  };

  const handleDelete = async (id: number) => {
    await api.deleteTask(id);
    await refreshTasks(filter === "all" ? undefined : filter);
  };

  const handleFilterChange = (newFilter: string) => {
    setFilter(newFilter);
    refreshTasks(newFilter === "all" ? undefined : newFilter);
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
        <h1 className="text-xl font-semibold">Nexus</h1>
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => router.push("/finance")}>
            Finance
          </Button>
          <span className="text-sm text-muted-foreground">{user.email}</span>
          <Button variant="outline" size="sm" onClick={logout}>
            Sign Out
          </Button>
        </div>
      </header>

      <main className="flex-1 p-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
            <div>
              <CardTitle>Tasks</CardTitle>
              <CardDescription>
                {tasks.filter((t) => t.status === "pending").length} pending
              </CardDescription>
            </div>
            <Dialog open={createOpen} onOpenChange={setCreateOpen}>
              <DialogTrigger render={<Button>New Task</Button>} />
              <DialogContent>
                <form onSubmit={handleCreate}>
                  <DialogHeader>
                    <DialogTitle>Create Task</DialogTitle>
                    <DialogDescription>
                      Add a new task to your list.
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4 py-4">
                    <div className="space-y-2">
                      <label htmlFor="title" className="text-sm font-medium">
                        Title
                      </label>
                      <Input
                        id="title"
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        placeholder="What needs to be done?"
                        required
                      />
                    </div>
                    <div className="space-y-2">
                      <label htmlFor="desc" className="text-sm font-medium">
                        Description
                      </label>
                      <Textarea
                        id="desc"
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        placeholder="Optional details…"
                        rows={3}
                      />
                    </div>
                    <div className="space-y-2">
                      <label htmlFor="priority" className="text-sm font-medium">
                        Priority
                      </label>
                      <Select value={priority} onValueChange={(v) => v && setPriority(v)}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="0">Normal</SelectItem>
                          <SelectItem value="3">Medium</SelectItem>
                          <SelectItem value="5">High</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <label htmlFor="dueDate" className="text-sm font-medium">
                        Due Date
                      </label>
                      <Input
                        id="dueDate"
                        value={dueDate}
                        onChange={(e) => setDueDate(e.target.value)}
                        placeholder="tomorrow, next monday, jul 15…"
                      />
                    </div>
                    <div className="space-y-2">
                      <label htmlFor="recur" className="text-sm font-medium">
                        Repeat
                      </label>
                      <Select value={recurrence} onValueChange={(v) => v && setRecurrence(v)}>
                        <SelectTrigger>
                          <SelectValue placeholder="No repeat" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="">No repeat</SelectItem>
                          <SelectItem value="FREQ=DAILY">Daily</SelectItem>
                          <SelectItem value="FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR">Weekdays</SelectItem>
                          <SelectItem value="FREQ=WEEKLY">Weekly</SelectItem>
                          <SelectItem value="FREQ=WEEKLY;BYDAY=MO">Weekly (Mon)</SelectItem>
                          <SelectItem value="FREQ=MONTHLY">Monthly</SelectItem>
                          <SelectItem value="FREQ=YEARLY">Yearly</SelectItem>
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
          </CardHeader>
          <CardContent>
            {/* Filter tabs */}
            <div className="mb-4 flex gap-2">
              {["all", "pending", "completed"].map((f) => (
                <Button
                  key={f}
                  variant={filter === f ? "default" : "outline"}
                  size="sm"
                  onClick={() => handleFilterChange(f)}
                >
                  {f.charAt(0).toUpperCase() + f.slice(1)}
                </Button>
              ))}
            </div>

            {/* Task table */}
            {tasks.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                No tasks yet. Create one to get started.
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[40%]">Title</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Priority</TableHead>
                    <TableHead>Due</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {tasks.map((task) => (
                    <TableRow key={task.id}>
                      <TableCell className="font-medium">
                        {task.title}
                        {task.description && (
                          <p className="text-xs text-muted-foreground truncate max-w-[250px]">
                            {task.description}
                          </p>
                        )}
                      </TableCell>
                      <TableCell>{statusBadge(task.status)}</TableCell>
                      <TableCell>{priorityLabel(task.priority)}</TableCell>
                      <TableCell className={getDueDateClass(task.due_date, task.status)}>
                        {formatDate(task.due_date)}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          {task.status === "pending" && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleComplete(task.id)}
                            >
                              Complete
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-red-600 hover:text-red-700 hover:bg-red-50"
                            onClick={() => handleDelete(task.id)}
                          >
                            Delete
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
