import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { RefreshControl, ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { useToast } from "@/src/components/toast";
import { Badge, Btn, Card, Chip, Empty, Header, Loading, T, space } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

/** Local-taluk hire requests: customers see their broadcast requests; hire drivers see requests from their home taluk. */
export default function HireRequests() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { fmtDate } = useI18n();
  const router = useRouter();
  const toast = useToast();
  const [data, setData] = useState<{ mine: any[]; inbox: any[] } | null>(null);
  const [tab, setTab] = useState<"inbox" | "mine">("inbox");
  const [busy, setBusy] = useState("");
  const load = useCallback(() => api("/hire/requests").then((r) => { setData(r); if (!r.inbox.length && r.mine.length) setTab("mine"); }).catch(() => setData({ mine: [], inbox: [] })), []);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const act = async (rid: string, action: string) => {
    setBusy(rid + action);
    try {
      const r = await api(`/hire/requests/${rid}/${action}`, { method: "POST" });
      toast(action === "accept" ? "Accepted — booking confirmed" : action === "decline" ? "Declined" : "Request cancelled");
      if (r.booking_id) router.push(`/hire/${r.booking_id}`);
      await load();
    } catch (e: any) { toast(e.message, "error"); await load(); }
    setBusy("");
  };

  const when = (r: any) => `${fmtDate(r.date)} · ${r.time} · ${r.passengers} passenger${r.passengers > 1 ? "s" : ""}`;
  const rows = tab === "inbox" ? data?.inbox ?? [] : data?.mine ?? [];
  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title="Local hire requests" />
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ flexGrow: 0 }} contentContainerStyle={{ gap: space.sm, paddingHorizontal: space.lg, height: 56, alignItems: "center" }}>
        <View style={{ flexShrink: 0 }}><Chip testID="hire-requests-tab-inbox" label={`For me (${data?.inbox.length ?? 0})`} active={tab === "inbox"} onPress={() => setTab("inbox")} /></View>
        <View style={{ flexShrink: 0 }}><Chip testID="hire-requests-tab-mine" label={`My requests (${data?.mine.length ?? 0})`} active={tab === "mine"} onPress={() => setTab("mine")} /></View>
      </ScrollView>
      {!data ? <Loading /> : (
        <ScrollView refreshControl={<RefreshControl refreshing={false} onRefresh={load} />} contentContainerStyle={{ padding: space.lg, gap: space.md, paddingBottom: insets.bottom + space.xl }}>
          {rows.length === 0 ? <Empty icon="people-outline" title={tab === "inbox" ? "No requests from your taluk yet" : "No local hire requests yet"} /> : null}
          {rows.map((r) => (
            <Card key={r.request_id} testID={`hire-request-${r.request_id}`} style={{ gap: space.xs }}>
              <View style={{ flexDirection: "row", gap: space.sm, alignItems: "center" }}>
                <T weight="800" style={{ flex: 1 }}>{r.city?.name} → {r.destination || "Local"}</T>
                <Badge testID={`hire-request-status-${r.request_id}`} label={r.status === "open" ? "Open" : r.status === "fulfilled" ? "Driver confirmed" : r.status === "expired" ? "Expired" : r.status === "cancelled" ? "Cancelled" : r.status} tone={r.status === "open" ? "warning" : r.status === "fulfilled" ? "success" : "muted"} />
              </View>
              <T size={13}>Pickup: {r.pickup}</T>
              <T size={12} color={colors.muted}>{when(r)} · {r.pickup_taluk?.name} {r.pickup_taluk?.sub_label}, {r.pickup_taluk?.district_name}</T>
              {tab === "inbox" ? (
                <>
                  {r.dispatch?.group === "nearby" ? <Badge label="Nearby taluk request" tone="info" /> : <Badge label="From your registered taluk" tone="success" />}
                  {r.status === "open" && !r.dispatch?.response ? (
                    <View style={{ flexDirection: "row", gap: space.sm, marginTop: space.xs }}>
                      <Btn style={{ flex: 1 }} testID={`hire-request-accept-${r.request_id}`} label="Accept" loading={busy === r.request_id + "accept"} onPress={() => act(r.request_id, "accept")} />
                      <Btn variant="outline" testID={`hire-request-decline-${r.request_id}`} label="Reject" loading={busy === r.request_id + "decline"} onPress={() => act(r.request_id, "decline")} />
                    </View>
                  ) : <T size={12} weight="700" color={colors.muted}>{r.dispatch?.response === "accepted" ? "You accepted this request" : r.dispatch?.response === "declined" ? "You rejected this request" : "Closed"}</T>}
                </>
              ) : (
                <>
                  {r.status === "fulfilled" && r.booking_id ? <Btn small testID={`hire-request-open-booking-${r.request_id}`} label="Open booking" onPress={() => router.push(`/hire/${r.booking_id}`)} /> : null}
                  {r.status === "open" ? <Btn variant="outline" testID={`hire-request-cancel-${r.request_id}`} label="Cancel request" loading={busy === r.request_id + "cancel"} onPress={() => act(r.request_id, "cancel")} /> : null}
                </>
              )}
            </Card>
          ))}
        </ScrollView>
      )}
    </View>
  );
}
