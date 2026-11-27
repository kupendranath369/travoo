import Ionicons from "@react-native-vector-icons/ionicons";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { Pressable, RefreshControl, ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, pictureUrl } from "@/src/api";
import { useBookingAlertSound } from "@/src/alerts";
import { float, ServiceCard, Switch } from "@/src/components/localdriver/parts";
import { useToast } from "@/src/components/toast";
import { NotificationBell } from "@/src/components/NotificationBell";
import { Avatar, Badge, ErrorBox, Header, IconName, Loading, T, radius, space } from "@/src/components/ui";
import { inr, useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

function GridTile({ icon, label, onPress, testID, badge, tint }: { icon: IconName; label: string; onPress: () => void; testID: string; badge?: number; tint: string }) {
  const { colors } = useTheme();
  return (
    <Pressable testID={testID} onPress={onPress} style={({ pressed }) => [float, { width: "31%", minHeight: 92, padding: space.sm, gap: 6, borderRadius: radius.lg, alignItems: "center",
      justifyContent: "center", backgroundColor: colors.surfaceSecondary, transform: [{ scale: pressed ? 0.96 : 1 }] }]}>
      <Ionicons name={icon} size={30} color={tint} />
      <T size={12} weight="700" center numberOfLines={2}>{label}</T>
      {badge ? <View testID={`${testID}-badge`} style={{ position: "absolute", top: 6, right: 10, minWidth: 20, height: 20, borderRadius: 10, paddingHorizontal: 5, backgroundColor: colors.error, alignItems: "center", justifyContent: "center" }}>
        <T size={11} weight="800" color="#fff">{badge}</T>
      </View> : null}
    </Pressable>
  );
}

export function LocalDriverDashboard({ embedded = false }: { embedded?: boolean }) {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { fmtDate } = useI18n();
  const router = useRouter();
  const toast = useToast();
  const [d, setD] = useState<any>(null);
  const [earn, setEarn] = useState<any>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState("");
  const [showServices, setShowServices] = useState(false);
  const load = useCallback(() => {
    api("/driver/earnings-summary").then((r) => setEarn(r.totals.all)).catch(() => {});
    return api("/pro/dashboard").then((r) => {
      if (!r.profile || r.profile.status !== "approved") return embedded ? setErr("Local driver profile is not approved") : router.replace("/hire/register");
      setD(r);
    }).catch((e) => setErr(e.message));
  }, [router, embedded]);
  useFocusEffect(useCallback(() => { load(); }, [load]));
  useBookingAlertSound(api, d?.profile?.status === "approved");
  if (err) return <View style={{ flex: 1 }}><Header title="Local Driver" /><ErrorBox message={err} onRetry={load} /></View>;
  if (!d) return <View style={{ flex: 1 }}>{embedded ? null : <Header title="Local Driver" />}<Loading /></View>;

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
  const upcomingPeriods = (p.availability ?? []).filter((a: any) => new Date(a.to) > new Date()).length;

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      {embedded ? null : <Header title="Local Driver" />}
      <ScrollView refreshControl={<RefreshControl refreshing={false} onRefresh={load} />} contentContainerStyle={{ padding: space.lg, paddingTop: embedded ? insets.top + space.sm : space.lg, gap: space.lg, paddingBottom: insets.bottom + space.xxl }}>
        <Pressable testID="dash-header" onPress={() => router.push("/profile")} style={{ flexDirection: "row", alignItems: "center", gap: space.md }}>
          <Avatar name={p.name} uri={pictureUrl(d.photos?.profile)} size={60} />
          <View style={{ flex: 1, gap: 3 }}>
            <T testID="dash-name" size={20} weight="800">Hi, {p.name?.split(" ")[0]}</T>
            <Badge testID="dash-verified-badge" icon="shield-checkmark" label="Verified Driver" tone="warning" />
            <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
              <Ionicons name="location-outline" size={13} color={colors.muted} />
              <T testID="dash-taluk" size={12} color={colors.muted} style={{ flexShrink: 1 }}>{p.home?.place_name ? `${p.home.place_name}, ` : ""}{p.home?.subdistrict_name}, {p.home?.district_name}</T>
              <Pressable testID="dash-change-home" hitSlop={8} onPress={() => router.push("/hire/home-location")}><T size={12} weight="800" color={colors.brandSecondary}>Change</T></Pressable>
            </View>
          </View>
          {embedded ? <View testID="dash-mode-pill" style={{ alignSelf: "flex-start", paddingHorizontal: space.md, paddingVertical: 6, borderRadius: radius.pill, backgroundColor: colors.brandSecondary }}><T size={12} weight="800" color="#fff">Driver Mode</T></View> : null}
          {embedded ? <NotificationBell testID="dash-notifications-button" /> : null}
        </Pressable>

        <View testID="dash-online-card" style={[float, { flexDirection: "row", alignItems: "center", gap: space.md, padding: space.md, borderRadius: radius.lg, backgroundColor: p.online ? colors.brandSoft : colors.surfaceSecondary }]}>
          <Ionicons name="location" size={26} color={p.online ? colors.brandPrimary : colors.muted} />
          <View style={{ flex: 1 }}>
            <T testID="dash-online-label" size={17} weight="800">{p.online ? "Online" : "Offline"}</T>
            <T size={12} color={colors.muted}>{p.online ? "You are available for booking requests" : `Not taking immediate requests${upcomingPeriods ? ` · ${upcomingPeriods} scheduled` : ""}`}</T>
          </View>
          <Switch testID="dash-online-toggle" value={!!p.online} disabled={busy === "online"}
            onChange={(v) => save("online", { availability_status: v ? "available" : "offline" }, v ? "You're online" : "You're offline. Confirmed bookings are not affected")} />
        </View>

        <View testID="dash-earnings-row" style={{ flexDirection: "row", gap: space.sm }}>
          {([["today", "Today"], ["week", "This Week"], ["month", "This Month"]] as const).map(([k, l]) => (
            <View key={k} testID={`dash-earn-${k}`} style={[float, { flex: 1, padding: space.md, borderRadius: radius.lg, backgroundColor: colors.surfaceSecondary, gap: 2 }]}>
              <T size={12} color={colors.muted}>{l}</T>
              <T size={18} weight="800">{inr(earn?.[k]?.net ?? 0)}</T>
            </View>
          ))}
        </View>

        <View style={{ flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between", rowGap: space.md }}>
          <GridTile testID="dash-tile-requests" icon="notifications" tint={colors.brandSecondary} label="Booking Requests" badge={d.open_requests || undefined} onPress={() => router.push("/hire/requests")} />
          <GridTile testID="dash-tile-trips" icon="car-sport" tint={colors.brandSecondary} label="My Trips" onPress={() => router.push("/driver-trips")} />
          <GridTile testID="dash-tile-earnings" icon="wallet" tint={colors.brandTertiary} label="My Earnings" onPress={() => router.push("/earnings")} />
          <GridTile testID="dash-tile-availability" icon="calendar" tint={colors.brandTertiary} label="Availability" badge={upcomingPeriods || undefined} onPress={() => router.push("/hire/availability")} />
          <GridTile testID="dash-tile-vehicles" icon="car" tint={colors.brandPrimary} label="My Vehicles" onPress={() => router.push("/hire/vehicles")} />
          <GridTile testID="dash-tile-services" icon="apps" tint={colors.brandSecondary} label="My Services" onPress={() => setShowServices(!showServices)} />
          <GridTile testID="dash-tile-home" icon="home" tint={colors.brandPrimary} label="Home Location" onPress={() => router.push("/hire/home-location")} />
        </View>

        {showServices ? (
          <View testID="dash-services-panel" style={{ gap: space.md }}>
            <View style={{ flexDirection: "row", gap: space.md }}>
              <ServiceCard testID="dash-service-rent" icon="key-outline" title="Driver Only" desc="Customer's vehicle (Rent a Driver)" active={p.services.includes("rent")} onPress={() => svc("rent")} />
              <ServiceCard testID="dash-service-book" icon="car-sport-outline" title="Car with Driver" desc="Your vehicle (Book a Car)" active={p.services.includes("book") && d.book_ready} disabled={!d.book_ready}
                note={d.book_ready ? undefined : "Needs an approved vehicle"} onPress={() => svc("book")} />
            </View>
            <View style={[float, { flexDirection: "row", alignItems: "center", gap: space.md, padding: space.md, borderRadius: radius.lg, backgroundColor: colors.surfaceSecondary }]}>
              <T weight="700" style={{ flex: 1 }}>Accept Outstation Trips</T>
              <Switch testID="dash-outstation-toggle" value={!!p.acceptOutstationTrips} disabled={busy === "out"} onChange={(v) => save("out", { acceptOutstationTrips: v }, v ? "Outstation trips on" : "Local trips only")} />
            </View>
          </View>
        ) : null}

        <View style={{ flexDirection: "row", justifyContent: "center", gap: space.lg }}>
          {embedded ? <Pressable testID="dash-offer-ride" onPress={() => router.push("/offer")}><T size={13} weight="700" color={colors.brandSecondary}>Offer a ride</T></Pressable> : null}
          <Pressable testID="dash-verification-details" onPress={() => router.push("/hire/register?view=details")}><T size={13} weight="700" color={colors.brandSecondary}>Verification details</T></Pressable>
        </View>

        {d.upcoming.length ? (
          <View style={{ gap: space.sm }}>
            <T weight="800">Upcoming trips</T>
            {d.upcoming.map((h: any) => (
              <Pressable key={h.booking_id} testID={`dash-upcoming-${h.booking_id}`} onPress={() => router.push(`/hire/${h.booking_id}`)}
                style={[float, { padding: space.md, borderRadius: radius.lg, backgroundColor: colors.surfaceSecondary, gap: 2 }]}>
                <T weight="700">{h.route}</T>
                <T size={12} color={colors.muted}>{fmtDate(h.date)} · {h.time} · {h.service === "book" ? "Car with Driver" : "Driver Only"} · {inr(h.service_fee)}</T>
              </Pressable>
            ))}
          </View>
        ) : null}
      </ScrollView>
    </View>
  );
}
