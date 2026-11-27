import { formatClock } from "@/src/components/ClockTimePicker";
import { useI18n } from "@/src/i18n";

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const HHMM = /^\d{2}:\d{2}$/;

/** Notification / system-message text with ISO dates and 24h times shown in friendly form. */
export function useNotifText() {
  const { t, fmtDate } = useI18n();
  return (type: string, params?: Record<string, any>) => {
    const p = { ...(params || {}) };
    if (typeof p.date === "string" && ISO_DATE.test(p.date)) p.date = fmtDate(p.date);
    if (typeof p.time === "string" && HHMM.test(p.time)) p.time = formatClock(p.time);
    return t(`notif.${type}`, p);
  };
}
