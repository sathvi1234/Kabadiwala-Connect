import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";
import { Badge, Card, MapPanel, States } from "../components/Bits";

export function VerifyPage() {
  const { lotId = "" } = useParams();
  const { t } = useTranslation();
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  useEffect(() => { void api<Record<string, unknown>>(`/api/public/verify/${lotId}`).then(setData); }, [lotId]);
  if (!data) return <main className="p-6"><States loading /></main>;
  if (!data.found) return <main className="p-6"><Card title={t("public.verify")}>{t("public.notFound")}</Card></main>;
  const verification = data.verification as Record<string, boolean>;
  const timeline = (data.timeline as { event: string; at: string }[]) || [];
  return (
    <main className="mx-auto max-w-xl p-4">
      <Card title={t("public.verify")}>
        <p className="text-xs text-muted">{t("public.noPii")}</p>
        <p className="mt-3 text-xl font-extrabold">{String(data.lot_id)}</p>
        <p>{String(data.material)} · {String(data.weight_kg)} kg · {String(data.city)}</p>
        <Badge>{String(data.status)}</Badge>
        <p className="mt-3 text-sm">GPS {verification.gps ? "✓" : "✗"} · Photo {verification.photo ? "✓" : "✗"} · Time {verification.time ? "✓" : "✗"} · Distance {verification.distance_flag ? "!" : "✓"}</p>
        <div className="mt-4">{timeline.map((event) => <p key={event.at + event.event} className="border-l-2 border-brand py-2 pl-3 text-sm"><b>{event.event}</b> · {event.at}</p>)}</div>
      </Card>
    </main>
  );
}

export function CommunityPage() {
  const { t } = useTranslation();
  const [data, setData] = useState<{ recyclers: { business_name: string; lat: number; lng: number; verified: boolean; city: string }[]; events: { title: string; city: string; starts_at: string; description: string; lat: number; lng: number }[]; areas: { city: string; weight_kg: number; lots: number }[] } | null>(null);
  useEffect(() => { void api<NonNullable<typeof data>>("/api/public/map").then(setData); }, []);
  if (!data) return <main className="p-6"><States loading /></main>;
  return (
    <main className="mx-auto max-w-4xl space-y-4 p-4">
      <Card title={t("public.map")}>
        <p className="mb-3 text-xs text-muted">{t("public.noPii")}</p>
        <MapPanel points={[...data.recyclers.map((row) => ({ lat: row.lat, lng: row.lng, label: row.business_name })), ...data.events.map((row) => ({ lat: row.lat, lng: row.lng, label: row.title }))]} />
      </Card>
      <Card title={t("public.drives")}>{data.events.map((event) => <p key={event.title} className="text-sm">{event.title} · {event.city} · {event.starts_at}<span className="block text-muted">{event.description}</span></p>)}</Card>
      <Card title={t("public.areas")}>{data.areas.map((area) => <p key={area.city}>{area.city}: {area.weight_kg} kg · {area.lots}</p>)}</Card>
    </main>
  );
}
