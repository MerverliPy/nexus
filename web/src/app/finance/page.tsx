"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

interface Account {
  id: number;
  name: string;
  account_type: string;
  institution: string | null;
  balance: number;
}

interface Transaction {
  id: number;
  account_id: number | null;
  amount: number;
  vendor: string | null;
  category: string | null;
  description: string | null;
  transaction_date: string;
  is_verified: boolean;
}

interface SpendingItem {
  category: string;
  total: number;
  count: number;
}

export default function FinancePage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"transactions" | "accounts" | "analytics">("transactions");
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [spending, setSpending] = useState<SpendingItem[]>([]);
  const [monthlyTotal, setMonthlyTotal] = useState(0);
  const [filterCategory, setFilterCategory] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [txVendor, setTxVendor] = useState("");
  const [txAmount, setTxAmount] = useState("");
  const [txCategory, setTxCategory] = useState("");
  const [txDate, setTxDate] = useState("");

  useEffect(() => {
    if (!loading && !user) router.push("/login");
  }, [user, loading, router]);

  const loadAccounts = async () => {
    try {
      const res = await fetch(`http://localhost:8000/api/v1/finance/accounts`, {
        headers: { Authorization: `Bearer ${api.getTokens().access}` },
      });
      if (res.ok) setAccounts(await res.json());
    } catch {}
  };

  const loadTransactions = async (category?: string) => {
    try {
      const params = new URLSearchParams();
      if (category) params.set("category", category);
      params.set("limit", "50");
      const res = await fetch(
        `http://localhost:8000/api/v1/finance/transactions?${params}`,
        { headers: { Authorization: `Bearer ${api.getTokens().access}` } }
      );
      if (res.ok) setTransactions(await res.json());
    } catch {}
  };

  const loadAnalytics = async () => {
    try {
      const token = api.getTokens().access;
      const catRes = await fetch(
        "http://localhost:8000/api/v1/finance/analytics/spending-by-category",
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (catRes.ok) setSpending(await catRes.json());

      const monRes = await fetch(
        "http://localhost:8000/api/v1/finance/analytics/monthly-totals",
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (monRes.ok) {
        const data = await monRes.json();
        if (data.length > 0) setMonthlyTotal(data[0].total);
      }
    } catch {}
  };

  useEffect(() => {
    if (user) {
      loadAccounts();
      loadTransactions();
      loadAnalytics();
    }
  }, [user]);

  const handleCreateTransaction = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createTransaction({
        amount: parseFloat(txAmount),
        vendor: txVendor || undefined,
        category: txCategory || undefined,
        transaction_date: txDate || new Date().toISOString().split("T")[0],
      });
      setTxVendor("");
      setTxAmount("");
      setTxCategory("");
      setTxDate("");
      setCreateOpen(false);
      loadTransactions(filterCategory);
      loadAnalytics();
    } catch (err) {
      console.error("Create failed", err);
    }
  };

  const handleDelete = async (id: number) => {
    await api.deleteTransaction(id);
    loadTransactions(filterCategory);
    loadAnalytics();
  };

  if (loading) return <div className="flex flex-1 items-center justify-center"><p className="text-muted-foreground">Loading…</p></div>;
  if (!user) return null;

  const totalBalance = accounts.reduce((sum, a) => sum + a.balance, 0);

  return (
    <div className="flex flex-1 flex-col">
      <header className="flex items-center justify-between border-b px-6 py-3">
        <h1 className="text-xl font-semibold">Nexus Finance</h1>
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground">{user.email}</span>
          <Button variant="outline" size="sm" onClick={() => router.push("/dashboard")}>
            Tasks
          </Button>
        </div>
      </header>

      <main className="flex-1 p-6">
        {/* Summary cards */}
        <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Total Balance</CardTitle></CardHeader>
            <CardContent>
              <p className={`text-2xl font-bold ${totalBalance >= 0 ? "text-green-600" : "text-red-600"}`}>
                ${totalBalance.toFixed(2)}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">This Month Spending</CardTitle></CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-red-600">${monthlyTotal.toFixed(2)}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Accounts</CardTitle></CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{accounts.length}</p>
            </CardContent>
          </Card>
        </div>

        {/* Tabs */}
        <div className="mb-4 flex gap-2">
          {(["transactions", "accounts", "analytics"] as const).map((tab) => (
            <Button key={tab} variant={activeTab === tab ? "default" : "outline"} size="sm" onClick={() => setActiveTab(tab)}>
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </Button>
          ))}
        </div>

        {/* Transactions tab */}
        {activeTab === "transactions" && (
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Transactions</CardTitle>
                <CardDescription>Filter by category</CardDescription>
              </div>
              <Dialog open={createOpen} onOpenChange={setCreateOpen}>
                <DialogTrigger render={<Button>New Transaction</Button>} />
                <DialogContent>
                  <form onSubmit={handleCreateTransaction}>
                    <DialogHeader>
                      <DialogTitle>Log Transaction</DialogTitle>
                      <DialogDescription>Add a manual transaction.</DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                      <div className="space-y-2">
                        <label className="text-sm font-medium">Vendor</label>
                        <Input value={txVendor} onChange={(e) => setTxVendor(e.target.value)} placeholder="e.g. Starbucks" />
                      </div>
                      <div className="space-y-2">
                        <label className="text-sm font-medium">Amount ($)</label>
                        <Input type="number" step="0.01" value={txAmount} onChange={(e) => setTxAmount(e.target.value)} placeholder="4.50" required />
                      </div>
                      <div className="space-y-2">
                        <label className="text-sm font-medium">Category</label>
                        <Input value={txCategory} onChange={(e) => setTxCategory(e.target.value)} placeholder="Dining, Groceries, etc." />
                      </div>
                      <div className="space-y-2">
                        <label className="text-sm font-medium">Date</label>
                        <Input type="date" value={txDate} onChange={(e) => setTxDate(e.target.value)} />
                      </div>
                    </div>
                    <DialogFooter>
                      <Button type="submit">Log Transaction</Button>
                    </DialogFooter>
                  </form>
                </DialogContent>
              </Dialog>
            </CardHeader>
            <CardContent>
              <div className="mb-4 flex gap-2 flex-wrap">
                <Button variant={!filterCategory ? "default" : "outline"} size="sm" onClick={() => { setFilterCategory(""); loadTransactions(); }}>
                  All
                </Button>
                {["Dining", "Groceries", "Entertainment", "Transportation", "Shopping", "Bills"].map((cat) => (
                  <Button
                    key={cat}
                    variant={filterCategory === cat ? "default" : "outline"}
                    size="sm"
                    onClick={() => { setFilterCategory(cat); loadTransactions(cat); }}
                  >
                    {cat}
                  </Button>
                ))}
              </div>
              {transactions.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">No transactions yet.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Vendor</TableHead>
                      <TableHead className="text-right">Amount</TableHead>
                      <TableHead>Category</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {transactions.map((tx) => (
                      <TableRow key={tx.id}>
                        <TableCell>{tx.transaction_date}</TableCell>
                        <TableCell className="font-medium">{tx.vendor || "—"}</TableCell>
                        <TableCell className={`text-right font-mono ${tx.amount > 0 ? "text-red-600" : "text-green-600"}`}>
                          {tx.amount > 0 ? "-" : "+"}${Math.abs(tx.amount).toFixed(2)}
                        </TableCell>
                        <TableCell>{tx.category ? <Badge variant="outline">{tx.category}</Badge> : "—"}</TableCell>
                        <TableCell>{tx.is_verified ? <Badge className="bg-green-100 text-green-800">Verified</Badge> : <Badge variant="outline">Unverified</Badge>}</TableCell>
                        <TableCell className="text-right">
                          <Button variant="ghost" size="sm" className="text-red-600" onClick={() => handleDelete(tx.id)}>
                            Delete
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        )}

        {/* Accounts tab */}
        {activeTab === "accounts" && (
          <Card>
            <CardHeader>
              <CardTitle>Accounts</CardTitle>
            </CardHeader>
            <CardContent>
              {accounts.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">No accounts. Use CLI: <code>nexus finance add-account</code></p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Institution</TableHead>
                      <TableHead className="text-right">Balance</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {accounts.map((a) => (
                      <TableRow key={a.id}>
                        <TableCell className="font-medium">{a.name}</TableCell>
                        <TableCell>{a.account_type}</TableCell>
                        <TableCell>{a.institution || "—"}</TableCell>
                        <TableCell className={`text-right font-mono ${a.balance >= 0 ? "text-green-600" : "text-red-600"}`}>
                          ${a.balance.toFixed(2)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        )}

        {/* Analytics tab */}
        {activeTab === "analytics" && (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader><CardTitle>Spending by Category</CardTitle></CardHeader>
              <CardContent>
                {spending.length === 0 ? (
                  <p className="py-8 text-center text-sm text-muted-foreground">No spending data yet.</p>
                ) : (
                  <div className="space-y-3">
                    {spending.map((item) => {
                      const maxTotal = Math.max(...spending.map((s) => s.total));
                      const pct = (item.total / maxTotal) * 100;
                      return (
                        <div key={item.category}>
                          <div className="flex justify-between text-sm mb-1">
                            <span>{item.category}</span>
                            <span className="font-mono">${item.total.toFixed(2)} ({item.count}x)</span>
                          </div>
                          <div className="h-2 w-full rounded-full bg-muted">
                            <div
                              className="h-2 rounded-full bg-primary"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Top Vendors</CardTitle></CardHeader>
              <CardContent>
                {transactions.length === 0 ? (
                  <p className="py-8 text-center text-sm text-muted-foreground">No data yet.</p>
                ) : (
                  <div className="space-y-2">
                    {Object.entries(
                      transactions.reduce<Record<string, number>>((acc, tx) => {
                        const v = tx.vendor || "Unknown";
                        acc[v] = (acc[v] || 0) + tx.amount;
                        return acc;
                      }, {})
                    ).sort(([, a], [, b]) => b - a).slice(0, 10).map(([vendor, total]) => (
                      <div key={vendor} className="flex justify-between text-sm">
                        <span>{vendor}</span>
                        <span className="font-mono">${total.toFixed(2)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}
      </main>
    </div>
  );
}
