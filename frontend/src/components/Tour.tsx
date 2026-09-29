import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { driver } from "driver.js";
import "driver.js/dist/driver.css";

const STEPS: Record<string, string[]> = {
  collector: ["tour-earnings", "tour-actions", "tour-prices", "tour-lots", "tour-sync", "tour-emergency"],
  recycler: ["tour-kpi", "tour-kanban", "tour-offers", "tour-availability", "tour-scan"],
  admin: ["tour-kpi", "tour-activity", "tour-verify", "tour-charts", "tour-reset"],
};

export function ProductTour({ role }: { role: string }) {
  const { t, i18n } = useTranslation();
  const location = useLocation();

  useEffect(() => {
    if (location.pathname !== `/app/${role}`) return;
    const key = `tour-${role}`;
    if (localStorage.getItem(key)) return;
    const ids = STEPS[role] || [];
    const timer = window.setTimeout(() => {
      const steps = ids
        .filter((id) => document.getElementById(id))
        .map((id) => ({
          element: `#${id}`,
          popover: { title: t(`tour.${id}`), description: t(`tour.${id}Body`), side: "bottom" as const },
        }));
      if (steps.length < 3) return;
      const tour = driver({
        showProgress: true,
        allowClose: true,
        nextBtnText: t("tour.next"),
        prevBtnText: t("tour.back"),
        doneBtnText: t("tour.done"),
        steps,
        onDestroyed: () => localStorage.setItem(key, "1"),
      });
      tour.drive();
    }, 700);
    return () => window.clearTimeout(timer);
  }, [location.pathname, role, i18n.language, t]);

  return null;
}
