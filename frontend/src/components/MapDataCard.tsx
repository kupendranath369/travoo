import React, { useCallback, useEffect, useState } from "react";
import { View } from "react-native";

import { api } from "@/src/api";
import { Badge, Btn, Section, T, space } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

/** Admin: map database health — last sync, counts, provider status, searches with no results, flagged coordinates. */
export function MapDataCard() {
  const { colors } = useTheme();
  const { t } = useI18n();
  const [r, setR] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const load = useCallback(() => api("/admin/geo/report").then(setR).catch((e) => setMsg(e.message)), []);
  useEffect(() => { load(); }, [load]);

  const sync = async () => {
    setBusy(true);
    setMsg("");
    try {
      await api("/admin/geo/sync", { method: "POST" });
      let rep: any;
      for (let i = 0; i < 60; i++) {
        await new Promise((res) => setTimeout(res, 3000));
        rep = await api("/admin/geo/report");
        if (!rep.running) break;
      }
      setR(rep);
      const s = rep.last_stats || {};
      setMsg(`${rep.running ? "running" : rep.last_status}: ${s.refreshed ?? 0} refreshed · ${s.duplicates_merged ?? 0} merged · ${s.outdated ?? 0} outdated`);
    } catch (e: any) {
      setMsg(e.message);
    }
    setBusy(false);
  };

  return (
    <Section title={t("geo.admin_title")}>
      {r ? (
        <View testID="admin-map-data" style={{ gap: space.xs }}>
          <T size={13}>{t("geo.last_sync")}: <T size={13} weight="700" testID="admin-map-last-sync">{r.last_success_at ? new Date(r.last_success_at).toLocaleString() : "—"}</T></T>
          <T size={13} color={colors.muted}>{r.counts.locations} places · {r.counts.openstreetmap} OSM · {r.counts.curated} curated · {r.counts.pincodes} PIN codes · {r.outdated} outdated · {r.pending_requests} requests</T>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.xs }}>
            {r.providers.map((p: any) => <Badge key={p.name} label={`${p.name} ${p.errors ? `· ${p.errors} err` : ""}`} tone={!p.available ? "error" : p.errors && !p.ok ? "warning" : "success"} />)}
          </View>
          {r.misses.length ? <T size={12} color={colors.muted}>{t("geo.misses")}: {r.misses.slice(0, 10).map((m: any) => `${m.q} (${m.count})`).join(", ")}</T> : null}
          {r.flagged.length ? <T size={12} color={colors.error}>{t("geo.flagged")}: {r.flagged.map((f: any) => `${f.name} (${f.osm_offset_km} km)`).join(", ")}</T> : null}
          {r.last_errors?.length ? <T size={11} color={colors.error}>{r.last_errors[0]}</T> : null}
        </View>
      ) : null}
      {msg ? <T size={12} color={colors.muted} testID="admin-map-sync-msg">{msg}</T> : null}
      <Btn small variant="outline" icon="sync" label={t("geo.sync_now")} loading={busy} onPress={sync} testID="admin-map-sync-button" />
      <T size={10} color={colors.muted}>{r?.attribution}</T>
    </Section>
  );
}
