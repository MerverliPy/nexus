"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { api, type Portfolio, type PortfolioAnalytics, type NetWorth, type RebalanceRecommendation } from "@/lib/api";
import { MobileNav } from "@/components/mobile-nav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(value);
}

function formatPercent(value: number) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function gainColor(value: number) {
  if (value > 0) return "text-green-600 dark:text-green-400";
  if (value < 0) return "text-red-600 dark:text-red-400";
  return "text-muted-foreground";
}

export default function PortfolioPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [analyticsMap, setAnalyticsMap] = useState<Record<number, PortfolioAnalytics>>({});
  const [rebalanceMap, setRebalanceMap] = useState<Record<number, RebalanceRecommendation>>({});
  const [pageLoading, setPageLoading] = useState(true);
  const [error, setError] = useState("");

  // Net worth
  const [netWorth, setNetWorth] = useState<NetWorth | null>(null);
  const [netWorthLoading, setNetWorthLoading] = useState(false);
  const [snapshotting, setSnapshotting] = useState(false);

  // Add holding dialog
  const [addHoldingOpen, setAddHoldingOpen] = useState(false);
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<number | null>(null);
  const [holdingTicker, setHoldingTicker] = useState("");
  const [holdingQuantity, setHoldingQuantity] = useState("");
  const [holdingCostBasis, setHoldingCostBasis] = useState("");
  const [holdingAssetClass, setHoldingAssetClass] = useState("stocks");
  const [addingHolding, setAddingHolding] = useState(false);
  const [addHoldingError, setAddHoldingError] = useState("");

  // Rebalance dialog
  const [rebalanceOpen, setRebalanceOpen] = useState(false);
  const [rebalanceData, setRebalanceData] = useState<RebalanceRecommendation | null>(null);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (user) {
      loadAll();
    }
  }, [user]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadAll = async () => {
    setPageLoading(true);
    setError("");
    try {
      const pfList = await api.listPortfolios();
      setPortfolios(pfList);

      // Fetch analytics for each portfolio
      const analyticsPromises = pfList.map((pf) =>
        api.getPortfolioAnalytics(pf.id).catch((err) => {
          console.error(`Failed to load analytics for portfolio ${pf.id}`, err);
          return null;
        })
      );
      const analyticsResults = await Promise.all(analyticsPromises);
      const aMap: Record<number, PortfolioAnalytics> = {};
      analyticsResults.forEach((a) => {
        if (a) aMap[a.portfolio_id] = a;
      });
      setAnalyticsMap(aMap);

      // Fetch net worth
      try {
        const nw = await api.getNetWorth();
        setNetWorth(nw);
      } catch (err) {
        console.error("Failed to load net worth", err);
      }
    } catch (err) {
      console.error("Failed to load portfolios", err);
      setError("Failed to load portfolio data.");
    } finally {
      setPageLoading(false);
    }
  };

  const loadRebalance = async (portfolioId: number) => {
    try {
      const data = await api.getPortfolioRebalance(portfolioId);
      setRebalanceData(data);
      setRebalanceOpen(true);
    } catch (err) {
      console.error("Failed to load rebalance", err);
    }
  };

  const handleAddHolding = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPortfolioId) return;
    setAddingHolding(true);
    setAddHoldingError("");
    try {
      await api.addHolding({
        portfolio_id: selectedPortfolioId,
        ticker: holdingTicker,
        quantity: parseFloat(holdingQuantity),
        cost_basis: parseFloat(holdingCostBasis),
        asset_class: holdingAssetClass,
      });
      setHoldingTicker("");
      setHoldingQuantity("");
      setHoldingCostBasis("");
      setHoldingAssetClass("stocks");
      setAddHoldingOpen(false);
      // Reload analytics for this portfolio
      const analytics = await api.getPortfolioAnalytics(selectedPortfolioId);
      setAnalyticsMap((prev) => ({ ...prev, [selectedPortfolioId]: analytics }));
    } catch (err) {
      setAddHoldingError(err instanceof Error ? err.message : String(err));
    } finally {
      setAddingHolding(false);
    }
  };

  const handleDeleteHolding = async (holdingId: number, portfolioId: number) => {
    if (!confirm("Delete this holding?")) return;
    try {
      await api.deleteHolding(holdingId);
      // Reload analytics for this portfolio
      const analytics = await api.getPortfolioAnalytics(portfolioId);
      setAnalyticsMap((prev) => ({ ...prev, [portfolioId]: analytics }));
    } catch (err) {
      console.error("Delete holding failed", err);
    }
  };

  const handleSnapshot = async () => {
    setSnapshotting(true);
    try {
      const nw = await api.createNetWorthSnapshot();
      setNetWorth(nw);
    } catch (err) {
      console.error("Snapshot failed", err);
    } finally {
      setSnapshotting(false);
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
        <h1 className="text-xl font-semibold">Portfolio</h1>
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
        {/* Error */}
        {error && (
          <Card className="mb-6 border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950">
            <CardContent className="p-4">
              <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
            </CardContent>
          </Card>
        )}

        {/* Net Worth */}
        {netWorth && (
          <Card className="mb-6">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle>Net Worth</CardTitle>
                <Button variant="outline" size="sm" onClick={handleSnapshot} disabled={snapshotting}>
                  {snapshotting ? "Saving…" : "Save Snapshot"}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-4">
                <div>
                  <p className="text-sm text-muted-foreground">Total Assets</p>
                  <p className="text-xl font-semibold text-green-600 dark:text-green-400">
                    {formatCurrency(netWorth.total_assets)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Liabilities</p>
                  <p className="text-xl font-semibold text-red-600 dark:text-red-400">
                    {formatCurrency(netWorth.total_liabilities)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Net Worth</p>
                  <p className="text-xl font-semibold">
                    {formatCurrency(netWorth.net_worth)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Portfolio</p>
                  <p className="text-xl font-semibold">
                    {formatCurrency(netWorth.breakdown.portfolio)}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Loading state */}
        {pageLoading ? (
          <div className="flex items-center justify-center py-12">
            <p className="text-muted-foreground">Loading portfolios…</p>
          </div>
        ) : portfolios.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <p className="text-muted-foreground">No portfolios yet.</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Create a portfolio through the API to get started.
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-2">
            {portfolios.map((pf) => {
              const analytics = analyticsMap[pf.id];
              return (
                <Card key={pf.id}>
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle>{pf.name}</CardTitle>
                        <CardDescription>
                          {analytics
                            ? `${formatCurrency(analytics.total_value)} — ${analytics.holdings.length} holding${analytics.holdings.length !== 1 ? "s" : ""}`
                            : "Loading…"}
                        </CardDescription>
                      </div>
                      <div className="flex gap-1">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setSelectedPortfolioId(pf.id);
                            setAddHoldingOpen(true);
                          }}
                        >
                          + Holding
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => loadRebalance(pf.id)}
                        >
                          Rebalance
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  {analytics && (
                    <>
                      {/* Summary row */}
                      <CardContent className="pb-3">
                        <div className="grid grid-cols-3 gap-3 text-sm">
                          <div>
                            <span className="text-muted-foreground">Gain/Loss: </span>
                            <span className={gainColor(analytics.total_gain_loss)}>
                              {formatCurrency(analytics.total_gain_loss)} ({formatPercent(analytics.total_gain_loss_pct)})
                            </span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Cost: </span>
                            <span>{formatCurrency(analytics.total_cost)}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Value: </span>
                            <span>{formatCurrency(analytics.total_value)}</span>
                          </div>
                        </div>
                      </CardContent>

                      {/* Holdings table */}
                      {analytics.holdings.length > 0 && (
                        <CardContent className="pt-0">
                          <Table>
                            <TableHeader>
                              <TableRow>
                                <TableHead>Ticker</TableHead>
                                <TableHead>Shares</TableHead>
                                <TableHead>Cost Basis</TableHead>
                                <TableHead>Price</TableHead>
                                <TableHead>Value</TableHead>
                                <TableHead>Gain/Loss</TableHead>
                                <TableHead className="text-right">Action</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {analytics.holdings.map((h) => (
                                <TableRow key={h.id}>
                                  <TableCell className="font-medium">{h.ticker}</TableCell>
                                  <TableCell>{h.quantity}</TableCell>
                                  <TableCell>{formatCurrency(h.cost_basis)}</TableCell>
                                  <TableCell>{formatCurrency(h.current_price)}</TableCell>
                                  <TableCell>{formatCurrency(h.market_value)}</TableCell>
                                  <TableCell className={gainColor(h.gain_loss)}>
                                    {formatCurrency(h.gain_loss)} ({formatPercent(h.gain_loss_pct)})
                                  </TableCell>
                                  <TableCell className="text-right">
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      className="text-red-600 hover:text-red-700 hover:bg-red-50"
                                      onClick={() => handleDeleteHolding(h.id, pf.id)}
                                    >
                                      Delete
                                    </Button>
                                  </TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        </CardContent>
                      )}
                    </>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </main>

      {/* Add Holding dialog */}
      <Dialog open={addHoldingOpen} onOpenChange={(open) => { setAddHoldingOpen(open); if (!open) setAddHoldingError(""); }}>
        <DialogContent>
          <form onSubmit={handleAddHolding}>
            <DialogHeader>
              <DialogTitle>Add Holding</DialogTitle>
              <DialogDescription>
                Add a new holding to{" "}
                {portfolios.find((p) => p.id === selectedPortfolioId)?.name || "portfolio"}.
              </DialogDescription>
            </DialogHeader>
            {addHoldingError && (
              <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300">
                {addHoldingError}
              </div>
            )}
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <label htmlFor="ticker" className="text-sm font-medium">Ticker</label>
                <Input
                  id="ticker"
                  value={holdingTicker}
                  onChange={(e) => setHoldingTicker(e.target.value.toUpperCase())}
                  placeholder="e.g. AAPL"
                  required
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="quantity" className="text-sm font-medium">Shares</label>
                <Input
                  id="quantity"
                  type="number"
                  step="any"
                  value={holdingQuantity}
                  onChange={(e) => setHoldingQuantity(e.target.value)}
                  placeholder="10"
                  required
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="costBasis" className="text-sm font-medium">Cost Basis (per share)</label>
                <Input
                  id="costBasis"
                  type="number"
                  step="any"
                  value={holdingCostBasis}
                  onChange={(e) => setHoldingCostBasis(e.target.value)}
                  placeholder="150.00"
                  required
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="assetClass" className="text-sm font-medium">Asset Class</label>
                <Select value={holdingAssetClass} onValueChange={(v) => v && setHoldingAssetClass(v)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="stocks">Stocks</SelectItem>
                    <SelectItem value="bonds">Bonds</SelectItem>
                    <SelectItem value="etf">ETF</SelectItem>
                    <SelectItem value="crypto">Crypto</SelectItem>
                    <SelectItem value="real_estate">Real Estate</SelectItem>
                    <SelectItem value="cash">Cash</SelectItem>
                    <SelectItem value="other">Other</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button type="submit" disabled={addingHolding}>
                {addingHolding ? "Adding…" : "Add Holding"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Rebalance dialog */}
      <Dialog open={rebalanceOpen} onOpenChange={setRebalanceOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rebalance Recommendations</DialogTitle>
            <DialogDescription>
              {rebalanceData
                ? `Based on a total value of ${formatCurrency(rebalanceData.total_value)}.`
                : "Loading…"}
            </DialogDescription>
          </DialogHeader>
          {rebalanceData ? (
            rebalanceData.recommendations.length === 0 ? (
              <div className="py-8 text-center text-sm text-muted-foreground">
                No rebalancing needed — no target allocation set.
              </div>
            ) : (
              <div className="space-y-3 py-4">
                {rebalanceData.recommendations.map((rec) => (
                  <div
                    key={rec.asset_class}
                    className="flex items-center justify-between rounded-lg border p-3"
                  >
                    <div>
                      <p className="font-medium capitalize">{rec.asset_class.replace("_", " ")}</p>
                      <p className="text-sm text-muted-foreground">
                        Current: {rec.current_pct.toFixed(1)}% → Target: {rec.target_pct.toFixed(1)}%
                      </p>
                    </div>
                    <div className="text-right">
                      <Badge
                        variant="outline"
                        className={
                          rec.action === "buy"
                            ? "border-green-300 text-green-700 dark:border-green-700 dark:text-green-300"
                            : rec.action === "sell"
                              ? "border-red-300 text-red-700 dark:border-red-700 dark:text-red-300"
                              : ""
                        }
                      >
                        {rec.action === "buy" ? "Buy" : rec.action === "sell" ? "Sell" : "Hold"}
                      </Badge>
                      {rec.action !== "hold" && (
                        <p className="mt-1 text-sm font-medium">
                          {formatCurrency(rec.amount)}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )
          ) : (
            <div className="py-8 text-center text-sm text-muted-foreground">Loading rebalance data…</div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setRebalanceOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <MobileNav />
    </div>
  );
}
