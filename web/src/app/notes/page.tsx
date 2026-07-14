"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { api, type Note } from "@/lib/api";
import { MobileNav } from "@/components/mobile-nav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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
} from "@/components/ui/dialog";

function formatDate(dateStr: string | null) {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function NotesPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [notes, setNotes] = useState<Note[]>([]);
  const [notesLoading, setNotesLoading] = useState(true);
  const [error, setError] = useState("");

  // Create dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [tags, setTags] = useState("");
  const [creating, setCreating] = useState(false);

  // View/Edit dialog
  const [viewNote, setViewNote] = useState<Note | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editContent, setEditContent] = useState("");
  const [editTags, setEditTags] = useState("");
  const [saving, setSaving] = useState(false);

  // Search
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<{ id: number; title: string; snippet: string; score: number; method: string }[] | null>(null);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (user) {
      loadNotes();
    }
  }, [user]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadNotes = async () => {
    setNotesLoading(true);
    setError("");
    try {
      const data = await api.listNotes();
      setNotes(data);
    } catch (err) {
      console.error("Failed to load notes", err);
      setError("Failed to load notes. Make sure you're signed in.");
    } finally {
      setNotesLoading(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      const tagList = tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      await api.createNote({
        title,
        content,
        tags: tagList.length > 0 ? tagList : undefined,
      });
      setTitle("");
      setContent("");
      setTags("");
      setCreateOpen(false);
      await loadNotes();
    } catch (err) {
      console.error("Create note failed", err);
    } finally {
      setCreating(false);
    }
  };

  const openEdit = (note: Note) => {
    setViewNote(note);
    setEditTitle(note.title);
    setEditContent(note.content);
    setEditTags((note.tags || []).join(", "));
    setEditOpen(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!viewNote) return;
    setSaving(true);
    try {
      const tagList = editTags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      await api.updateNote(viewNote.id, {
        title: editTitle,
        content: editContent,
        tags: tagList.length > 0 ? tagList : [],
      });
      setEditOpen(false);
      setViewNote(null);
      await loadNotes();
    } catch (err) {
      console.error("Save note failed", err);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this note?")) return;
    try {
      await api.deleteNote(id);
      setViewNote(null);
      setEditOpen(false);
      await loadNotes();
    } catch (err) {
      console.error("Delete note failed", err);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      setSearchResults(null);
      return;
    }
    setSearching(true);
    try {
      const results = await api.searchNotes(searchQuery);
      setSearchResults(results);
    } catch (err) {
      console.error("Search failed", err);
    } finally {
      setSearching(false);
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
        <h1 className="text-xl font-semibold">Notes</h1>
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground">{user.email}</span>
          <Button variant="outline" size="sm" onClick={() => router.push("/dashboard")}>
            Dashboard
          </Button>
        </div>
      </header>

      <main className="flex-1 p-6 pb-24 md:pb-6">
        {/* Search bar */}
        <div className="mb-6 flex gap-2">
          <Input
            placeholder="Search notes…"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              if (!e.target.value.trim()) setSearchResults(null);
            }}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            className="max-w-md"
          />
          <Button onClick={handleSearch} disabled={searching}>
            {searching ? "Searching…" : "Search"}
          </Button>
          <Button onClick={() => setCreateOpen(true)}>New Note</Button>
        </div>

        {/* Search results */}
        {searchResults && (
          <Card className="mb-6">
            <CardHeader>
              <CardTitle>Search Results</CardTitle>
              <CardDescription>
                {searchResults.length} result{searchResults.length !== 1 ? "s" : ""}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {searchResults.length === 0 ? (
                <p className="text-sm text-muted-foreground">No results found.</p>
              ) : (
                <div className="space-y-3">
                  {searchResults.map((r) => (
                    <div
                      key={r.id}
                      className="cursor-pointer rounded-lg border p-3 transition-colors hover:bg-accent"
                      onClick={() => {
                        const note = notes.find((n) => n.id === r.id);
                        if (note) openEdit(note);
                      }}
                    >
                      <p className="font-medium">{r.title}</p>
                      <p className="mt-1 text-sm text-muted-foreground line-clamp-2">{r.snippet}</p>
                      <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                        <span>Score: {r.score.toFixed(2)}</span>
                        <span>Method: {r.method}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Error */}
        {error && (
          <Card className="mb-6 border-red-200 bg-red-50">
            <CardContent className="p-4">
              <p className="text-sm text-red-700">{error}</p>
            </CardContent>
          </Card>
        )}

        {/* Notes list */}
        {notesLoading ? (
          <div className="flex items-center justify-center py-12">
            <p className="text-muted-foreground">Loading notes…</p>
          </div>
        ) : notes.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <p className="text-muted-foreground">No notes yet.</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Create one to start building your knowledge base.
              </p>
              <Button className="mt-4" onClick={() => setCreateOpen(true)}>
                Create Note
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {notes.map((note) => (
              <Card
                key={note.id}
                className="cursor-pointer transition-colors hover:bg-accent/50"
                onClick={() => openEdit(note)}
              >
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">{note.title}</CardTitle>
                  {note.tags && note.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {note.tags.map((tag) => (
                        <span
                          key={tag}
                          className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </CardHeader>
                <CardContent>
                  <p className="line-clamp-3 text-sm text-muted-foreground">
                    {note.content}
                  </p>
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
              <DialogTitle>Create Note</DialogTitle>
              <DialogDescription>Add a new note to your knowledge base.</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <label htmlFor="title" className="text-sm font-medium">Title</label>
                <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Note title" required />
              </div>
              <div className="space-y-2">
                <label htmlFor="content" className="text-sm font-medium">Content</label>
                <Textarea id="content" value={content} onChange={(e) => setContent(e.target.value)} placeholder="Write your note… (use [[WikiLinks]] to link notes)" rows={6} required />
              </div>
              <div className="space-y-2">
                <label htmlFor="tags" className="text-sm font-medium">Tags</label>
                <Input id="tags" value={tags} onChange={(e) => setTags(e.target.value)} placeholder="tag1, tag2, tag3" />
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

      {/* View/Edit dialog */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="max-w-2xl">
          <form onSubmit={handleSave}>
            <DialogHeader>
              <DialogTitle>Edit Note</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <label htmlFor="editTitle" className="text-sm font-medium">Title</label>
                <Input id="editTitle" value={editTitle} onChange={(e) => setEditTitle(e.target.value)} required />
              </div>
              <div className="space-y-2">
                <label htmlFor="editContent" className="text-sm font-medium">Content</label>
                <Textarea id="editContent" value={editContent} onChange={(e) => setEditContent(e.target.value)} rows={10} required />
              </div>
              <div className="space-y-2">
                <label htmlFor="editTags" className="text-sm font-medium">Tags</label>
                <Input id="editTags" value={editTags} onChange={(e) => setEditTags(e.target.value)} placeholder="tag1, tag2, tag3" />
              </div>
            </div>
            <DialogFooter className="flex items-center justify-between">
              <Button
                type="button"
                variant="destructive"
                onClick={() => viewNote && handleDelete(viewNote.id)}
              >
                Delete
              </Button>
              <div className="flex gap-2">
                <Button type="button" variant="outline" onClick={() => setEditOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" disabled={saving}>
                  {saving ? "Saving…" : "Save"}
                </Button>
              </div>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <MobileNav />
    </div>
  );
}
