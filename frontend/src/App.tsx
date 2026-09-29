import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { Shell } from "./components/Shell";
import { CommunityPage, LoginPage, RegisterCollector, RegisterHub, RegisterRecycler, ScanPage, VerifyPage } from "./pages/AuthPages";
import { AdminAnalytics, AdminPrices, AuditPage, DisputesPage, SyncPage, UsersPage, VerificationPage } from "./pages/AdminPages";
import { AiPage, LotDetail, LotsPage, PickupsPage, PricesPage, RecyclersPage, RewardsPage, SafetyPage, SettingsPage, TransactionsPage, TutorialsPage } from "./pages/CollectorPages";
import { OffersPage, PaymentsPage, RatingsPage, RecyclerAnalytics, RecyclerLot, RecyclerPickups, RecyclerProfilePage } from "./pages/RecyclerPages";

const LandingPage = lazy(() => import("./pages/LandingPage").then((module) => ({ default: module.LandingPage })));
const CollectorDashboard = lazy(() => import("./pages/HomeDash").then((module) => ({ default: module.CollectorDashboard })));
const RecyclerDashboard = lazy(() => import("./pages/HomeDash").then((module) => ({ default: module.RecyclerDashboard })));
const AdminDashboard = lazy(() => import("./pages/HomeDash").then((module) => ({ default: module.AdminDashboard })));

function Guard({ role, children }: { role: "collector" | "recycler" | "admin"; children: React.ReactNode }) {
  const { user, ready } = useAuth();
  if (!ready) return <p className="p-6 text-sm">…</p>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== role) return <Navigate to={`/app/${user.role}`} replace />;
  return children;
}

function Pending({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<div className="grid gap-3 p-4 sm:grid-cols-3">{[1, 2, 3].map((item) => <div key={item} className="h-24 animate-pulse rounded-2xl bg-white" />)}</div>}>{children}</Suspense>;
}

export function App() {
  const { user, ready } = useAuth();
  return (
    <Routes>
      <Route path="/" element={<Pending><LandingPage /></Pending>} />
      <Route path="/login" element={ready && user ? <Navigate to={`/app/${user.role}`} replace /> : <LoginPage />} />
      <Route path="/register" element={<RegisterHub />} />
      <Route path="/register/collector" element={<RegisterCollector />} />
      <Route path="/register/recycler" element={<RegisterRecycler />} />
      <Route path="/verify/:lotId" element={<VerifyPage />} />
      <Route path="/community" element={<CommunityPage />} />
      {["/collector", "/app/collector"].map((path) => (
      <Route key={path} path={path} element={<Guard role="collector"><Shell /></Guard>}>
        <Route index element={<Pending><CollectorDashboard /></Pending>} />
        <Route path="lots" element={<LotsPage />} />
        <Route path="lots/:id" element={<LotDetail />} />
        <Route path="recyclers" element={<RecyclersPage />} />
        <Route path="prices" element={<PricesPage />} />
        <Route path="pickups" element={<PickupsPage />} />
        <Route path="transactions" element={<TransactionsPage />} />
        <Route path="ai" element={<AiPage />} />
        <Route path="safety" element={<SafetyPage />} />
        <Route path="rewards" element={<RewardsPage />} />
        <Route path="tutorials" element={<TutorialsPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
      ))}
      {["/recycler", "/app/recycler"].map((path) => (
      <Route key={path} path={path} element={<Guard role="recycler"><Shell /></Guard>}>
        <Route index element={<Pending><RecyclerDashboard /></Pending>} />
        <Route path="pickups" element={<RecyclerPickups />} />
        <Route path="offers" element={<OffersPage />} />
        <Route path="scan" element={<ScanPage />} />
        <Route path="lots/:id" element={<RecyclerLot />} />
        <Route path="payments" element={<PaymentsPage />} />
        <Route path="ratings" element={<RatingsPage />} />
        <Route path="analytics" element={<RecyclerAnalytics />} />
        <Route path="profile" element={<RecyclerProfilePage />} />
      </Route>
      ))}
      {["/admin", "/app/admin"].map((path) => (
      <Route key={path} path={path} element={<Guard role="admin"><Shell /></Guard>}>
        <Route index element={<Pending><AdminDashboard /></Pending>} />
        <Route path="verification" element={<VerificationPage />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="prices" element={<AdminPrices />} />
        <Route path="disputes" element={<DisputesPage />} />
        <Route path="audit" element={<AuditPage />} />
        <Route path="sync" element={<SyncPage />} />
        <Route path="analytics" element={<AdminAnalytics />} />
      </Route>
      ))}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
