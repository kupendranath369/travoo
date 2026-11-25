import Ionicons from "@react-native-vector-icons/ionicons";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { Pressable, RefreshControl, ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, pictureUrl } from "@/src/api";
import { float, ServiceCard, Switch, Tile } from "@/src/components/localdriver/parts";
import { useToast } from "@/src/components/toast";
import { Avatar, Badge, ErrorBox, Header, Loading, T, radius, space } from "@/src/components/ui";
import { inr, useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

function OnlineToggle({ online, busy, onChange, upcoming }: { online: boolean; busy: boolean; onChange: (v: boolean) => void; upcoming: number }) {
  const { colors } = useTheme();
  return (
    <Pressable testID="dash-online-toggle" role="switch" aria-checked={online} disabled={busy} onPress={() => onChange(!online)}
      style={({ pressed }) => [float, { flexDirection: "row", alignItems: "center", gap: space.md, padding: space.lg, borderRadius: radius.lg,
        backgroundColor: online ? colors.success : colors.brandTertiary, opacity: busy ? 0.7 : 1, transform: [{ scale: pressed ? 0.98 : 1 }] }]}>
      <View style={{ width: 52, height: 52, borderRadius: 26, backgroundColor: "rgba(255,255,255,0.22)", alignItems: "center", justifyContent: "center" }}>
        <Ionicons name="power" size={28} color="#fff" />
      </View>
      <View style={{ flex: 1, gap: 2 }}>
        <T testID="dash-online-label" size={20} weight="800" color="#fff">{online ? "You're Online" : "Go Online"}</T>
        <T size={12} color="#fff" style={{ opacity: 0.9 }}>
          {online ? "Receiving immediate booking requests · tap to go offline" : `Offline · not receiving immediate requests${upcoming ? ` · ${upcoming} scheduled period${upcoming > 1 ? "s" : ""} still active` : ""}`}
        </T>
      </View>
    </Pressable>
  );
}

export default function LocalDriverDashboard() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { fmtDate } = useI18n();
  const router = useRouter();
  const toast = useToast();
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState("");
  const load = useCallback(() => api("/pro/dashboard").then((r) => {
    if (!r.profile || r.profile.status !== "approved") return router.replace("/hire/register");
    setD(r);
  }).catch((e) => setErr(e.message)), [router]);
  useFocusEffect(useCallback(() => { load(); }, [load]));
  if (err) return <View style={{ flex: 1 }}><Header title="Local Driver" /><ErrorBox message={err} onRetry={load} /></View>;
  if (!d) return <View style={{ flex: 1 }}><Header title="Local Driver" /><Loading /></View>;

  const p = d.profile;
  const save = async (key: string, body: any, msg: string) => {
    setBusy(key);
    try { const r = await api("/pro/settings", { method: "PUT", body }); setD((x: any) => ({ ...x, ...r })); toast(msg); } catch (e: any) { toast(e.message, "error"); }
    setBusy("");
  };
  const svc = (s: string) => {
    const on = p.services.includes(s);
    if (on && p.services.length === 1) return toast("Keep at least one service on. Go offline to pause all requests.", "error");
    save(`svc-${s}`, { services: on ? p.services.filter((x: string) => x !== s) : [...p.services, s] }, on ? "Service paused" : "Service enabled");
  };
  const nowIso = new Date().toISOString();
  const upcomingPeriods = (p.availability ?? []).filter((a: any) => new Date(a.to).toISOString() > nowIso).length;

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title="Local Driver" />
      <ScrollView refreshControl={<RefreshControl refreshing={false} onRefresh={load} />} contentContainerStyle={{ padding: space.lg, gap: space.lg, paddingBottom: insets.bottom + space.xxl }}>
        <View testID="dash-header" style={{ flexDirection: "row", alignItems: "center", gap: space.md }}>
          <Avatar name={p.name} uri={pictureUrl(d.photos?.profile)} size={56} />
          <View style={{ flex: 1, gap: 2 }}>
            <T testID="dash-name" size={18} weight="800">{p.name}</T>
            <T testID="dash-taluk" size={12} color={colors.muted}>{p.home?.subdistrict_name} {p.home?.sub_label}, {p.home?.district_name}</T>
            <View style={{ flexDirection: "row", gap: space.xs, flexWrap: "wrap" }}>
              <Badge testID="dash-verified-badge" icon="shield-checkmark" label="Verified driver" tone="success" />
              <Badge testID="dash-status-badge" label={p.online ? "Online" : "Offline"} tone={p.online ? "success" : "muted"} />
            </View>
          </View>
        </View>

        <OnlineToggle online={p.online} busy={busy === "online"} upcoming={upcomingPeriods}
          onChange={(v) => save("online", { availability_status: v ? "available" : "offline" }, v ? "You're online" : "You're offline — confirmed bookings are not affected")} />

        <View style={{ gap: space.sm }}>
          <T weight="800">My services</T>
          <View style={{ flexDirection: "row", gap: space.md }}>
            <ServiceCard testID="dash-service-rent" icon="key-outline" title="Rent a Driver" desc="Customer's vehicle" active={p.services.includes("rent")} onPress={() => svc("rent")} />
            <ServiceCard testID="dash-service-book" icon="car-sport-outline" title="Book a Driver" desc="Your vehicle" active={p.services.includes("book") && d.book_ready} disabled={!d.book_ready}
              note={d.book_ready ? undefined : "Needs an approved vehicle"} onPress={() => svc("book")} />
          </View>
        </View>

        <View style={[float, { flexDirection: "row", alignItems: "center", gap: space.md, padding: space.md, borderRadius: radius.lg, backgroundColor: colors.surfaceSecondary }]}>
          <Ionicons name="map-outline" size={22} color={colors.brandTertiary} />
          <View style={{ flex: 1 }}>
            <T weight="700">Accept outstation trips</T>
            <T size={12} color={colors.muted}>{p.acceptOutstationTrips ? "On · trips outside your home taluk" : "Off · local trips only"}</T>
          </View>
          <Switch testID="dash-outstation-toggle" value={!!p.acceptOutstationTrips} disabled={busy === "out"} onChange={(v) => save("out", { acceptOutstationTrips: v }, v ? "Outstation trips on" : "Local trips only")} />
        </View>

        <View style={{ flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between", rowGap: space.md }}>
          <Tile testID="dash-tile-availability" icon="calendar-outline" label="Schedule Availability" onPress={() => router.push("/hire/availability")} badge={upcomingPeriods || undefined} />
          <Tile testID="dash-tile-requests" icon="notifications-outline" label="Booking Requests" onPress={() => router.push("/hire/requests")} badge={d.open_requests || undefined} />
          <Tile testID="dash-tile-vehicles" icon="car-outline" label="My Vehicles" onPress={() => router.push("/hire/vehicles")} />
          <Tile testID="dash-tile-earnings" icon="wallet-outline" label="My Earnings" onPress={() => router.push("/earnings")} />
        </View>
        <Pressable testID="dash-verification-details" onPress={() => router.push("/hire/register?view=details")} style={{ alignSelf: "center", padding: space.sm }}>
          <T size={13} weight="700" color={colors.brandPrimary}>Verification details</T>
        </Pressable>

        {d.upcoming.length ? (
          <View style={{ gap: space.sm }}>
            <T weight="800">Upcoming trips</T>
            {d.upcoming.map((h: any) => (
              <Pressable key={h.booking_id} testID={`dash-upcoming-${h.booking_id}`} onPress={() => router.push(`/hire/${h.booking_id}`)}
                style={[float, { padding: space.md, borderRadius: radius.lg, backgroundColor: colors.surfaceSecondary, gap: 2 }]}>
                <T weight="700">{h.route}</T>
                <T size={12} color={colors.muted}>{fmtDate(h.date)} · {h.time} · {h.service === "book" ? "Book a Driver" : "Rent a Driver"} · {inr(h.service_fee)}</T>
              </Pressable>
            ))}
          </View>
        ) : null}
      </ScrollView>
    </View>
  );
}
