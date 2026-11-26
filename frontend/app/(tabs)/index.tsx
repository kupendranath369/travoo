import Ionicons from "@react-native-vector-icons/ionicons";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { Pressable, RefreshControl, ScrollView, View } from "react-native";
import Animated, { FadeInDown } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Loc, pictureUrl } from "@/src/api";
import { DateField } from "@/src/components/Calendar";
import { FloatingImage } from "@/src/components/FloatingImage";
import { LocationField } from "@/src/components/LocationField";
import { IMG } from "@/src/components/Brand";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { RideCard } from "@/src/components/RideCard";
import { Avatar, Btn, Card, IconName, T, radius, space } from "@/src/components/ui";
import { useAuth } from "@/src/auth";
import { DriverHome } from "@/src/components/DriverHome";
import { useI18n } from "@/src/i18n";
import { usesNativeTabs } from "@/src/navigation";
import { useTheme } from "@/src/theme";

export default function Home() {
  const { user } = useAuth();
  return user?.account_type === "driver" ? <DriverHome /> : <PassengerHome />;
}

function PassengerHome() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t, fmtDate } = useI18n();
  const router = useRouter();
  const { user } = useAuth();
  const [recent, setRecent] = useState<any[]>([]);
  const [from, setFrom] = useState<Loc | null>(null);
  const [to, setTo] = useState<Loc | null>(null);
  const [date, setDate] = useState<string | null>(null);
  const [formErr, setFormErr] = useState("");
  const [featured, setFeatured] = useState<any[]>([]);
  const [unread, setUnread] = useState(0);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    const [r, n, f] = await Promise.all([api("/searches").catch(() => []), api("/notifications").catch(() => ({ unread: 0 })), api("/featured").catch(() => [])]);
    setRecent(r);
    setUnread(n.unread);
    setFeatured(f);
  }, []);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const icon = (name: IconName, onPress: () => void, testID: string, dot?: boolean) => (
    <Pressable testID={testID} onPress={onPress} hitSlop={6} style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center" }}>
      <Ionicons name={name} size={20} color={colors.brand} />
      {dot ? <View testID={`${testID}-dot`} style={{ position: "absolute", top: 7, right: 8, width: 9, height: 9, borderRadius: 5, backgroundColor: colors.brandTertiary }} /> : null}
    </Pressable>
  );

  const repeat = (s: any) => {
    if (s.kind === "hire") router.push({ pathname: "/hire", params: { city: JSON.stringify(s.origin), service: s.service ?? "hourly" } });
    else router.push({ pathname: "/search", params: { from: JSON.stringify(s.origin), to: JSON.stringify(s.destination), date: s.date && s.date >= new Date().toISOString().slice(0, 10) ? s.date : "", seats: String(s.seats || 1) } });
  };

  const find = () => {
    if (!from || !to) return setFormErr(t("search.pick_both"));
    if (from.loc_id === to.loc_id) return setFormErr(t("home.same_place"));
    setFormErr("");
    router.push({ pathname: "/search", params: { from: JSON.stringify(from), to: JSON.stringify(to), date: date ?? "", seats: "1" } });
  };
  const art = (testID: string, img: number, title: string, sub: string, bg: string, onPress: () => void, delay: number) => (
    <Pressable testID={testID} onPress={onPress} style={({ pressed }) => ({ flex: 1, borderRadius: radius.lg, backgroundColor: bg, overflow: "hidden", padding: space.sm, gap: 2,
      shadowColor: "#14233A", shadowOpacity: 0.08, shadowRadius: 12, shadowOffset: { width: 0, height: 6 }, elevation: 3, transform: [{ scale: pressed ? 0.97 : 1 }] })}>
      <FloatingImage source={img} delay={delay} style={{ width: "100%", height: 130 }} testID={`${testID}-image`} />
      <T size={12} weight="700" center accessibilityLabel={title}>{sub}</T>
    </Pressable>
  );

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <ScrollView
        testID="home-scroll"
        contentContainerStyle={{ gap: space.md, paddingBottom: (usesNativeTabs ? insets.bottom : 0) + space.xl }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} />}
      >
        <View testID="home-header" style={{ height: 190 + insets.top }}>
          <Image source={{ uri: IMG.header }} style={{ position: "absolute", width: "100%", height: "100%" }} contentFit="cover" />
          <LinearGradient colors={["rgba(255,255,255,0.95)", "rgba(255,255,255,0.6)", "rgba(255,255,255,0)"]} style={{ position: "absolute", width: "100%", height: "80%" }} />
          <Pressable testID="home-profile-section" onPress={() => router.push("/profile")} style={{ paddingTop: insets.top + space.sm, paddingHorizontal: space.lg, flexDirection: "row", alignItems: "center", gap: space.md }}>
            <Avatar name={user?.name ?? ""} uri={pictureUrl(user?.picture)} size={48} />
            <View style={{ flex: 1 }}>
              <T size={20} weight="800">Hi, {user?.name?.split(" ")[0] || "there"}</T>
              <T size={13}>Plan your next trip with Travoo</T>
            </View>
            {user?.role === "admin" && icon("shield-checkmark-outline", () => router.push("/admin/login"), "home-admin-button")}
          </Pressable>
        </View>
        <Animated.View entering={FadeInDown.duration(400)} style={{ marginHorizontal: space.lg, marginTop: -90 }}>
          <Card testID="home-search-card" style={{ gap: space.sm, borderWidth: 0, shadowColor: "#14233A", shadowOpacity: 0.1, shadowRadius: 16, shadowOffset: { width: 0, height: 8 }, elevation: 5 }}>
<View style={{ paddingRight: 44, gap: space.sm }}>
            <LocationField testID="home-from-field" label="Leaving from" value={from} onChange={(l) => { setFrom(l); setFormErr(""); }} icon="location-outline" />
            <Pressable testID="home-swap-button" accessibilityLabel="Swap Leaving from and Going to" onPress={() => { setFrom(to); setTo(from); setFormErr(""); }} hitSlop={8}
              style={{ position: "absolute", right: 0, top: 46, zIndex: 2, width: 36, height: 36, borderRadius: 18, backgroundColor: colors.brandSoft, alignItems: "center", justifyContent: "center", borderWidth: 2, borderColor: colors.surfaceSecondary }}>
              <Ionicons name="swap-vertical" size={18} color={colors.brandPrimary} />
            </Pressable>
            <LocationField testID="home-to-field" label="Going to" value={to} onChange={(l) => { setTo(l); setFormErr(""); }} icon="navigate-outline" />
            </View>
            <DateField testID="home-date" label="Date (any date if empty)" value={date} onChange={setDate} allowClear />
            {formErr ? <T testID="home-form-error" color={colors.error} weight="600">{formErr}</T> : null}
            <Btn testID="home-find-ride-button" icon="search" label="Find a Ride" onPress={find} />
          </Card>
        </Animated.View>
        <Animated.View entering={FadeInDown.delay(80).duration(400)} style={{ flexDirection: "row", gap: space.md, paddingHorizontal: space.lg }}>
          {art("home-rent-driver-card", require("@/assets/images/tile-rent-driver.png"), "Rent a Driver", "Driver for your car", colors.brandSoft, () => router.push("/hire?service=rent"), 0)}
          {art("home-book-car-card", require("@/assets/images/tile-book-car.png"), "Book Car", "Car with driver", colors.accentSoft, () => router.push("/hire?service=book"), 400)}
        </Animated.View>

        <Animated.View entering={FadeInDown.delay(120).duration(400)} style={{ gap: space.sm, paddingHorizontal: space.lg }}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
            <T size={16} weight="800">Recent Searches</T>
            {recent.length > 0 ? (
              <Pressable testID="home-clear-recent" onPress={async () => { await api("/searches", { method: "DELETE" }); setRecent([]); }} hitSlop={8}>
                <T size={12} weight="700" color={colors.brandPrimary}>Clear All</T>
              </Pressable>
            ) : null}
          </View>
          {recent.length === 0 ? (
            <T testID="home-recent-empty" size={13} color={colors.muted} style={{ textAlign: "center", padding: space.md }}>No recent searches</T>
          ) : (
            <View style={{ gap: space.sm }}>
              {recent.slice(0, 4).map((s) => (
                <Card key={s.key} testID={`recent-search-${s.key}`} onPress={() => repeat(s)} style={{ flexDirection: "row", gap: space.sm, alignItems: "center", padding: space.sm, backgroundColor: colors.surfaceSecondary }}>
                  <Ionicons name={s.kind === "hire" ? "key-outline" : "time-outline"} size={18} color={colors.brandPrimary} />
                  <View style={{ flex: 1 }}>
                    <T weight="700" size={13} numberOfLines={1}>{s.kind === "hire" ? `${s.origin?.name} · ${t(`v2.svc.${s.service ?? "hourly"}`)}` : `${s.origin?.name} → ${s.destination?.name}`}</T>
                    <T size={11} color={colors.muted}>{s.date ? fmtDate(s.date) : t("search.any_date")} · {fmtDate(s.at, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</T>
                  </View>
                  <Pressable testID={`remove-recent-${s.key}`} onPress={async () => { await api(`/searches/${s.key}`, { method: "DELETE" }); setRecent(recent.filter((r: any) => r.key !== s.key)); }} hitSlop={8}>
                    <Ionicons name="close-circle" size={20} color={colors.muted} />
                  </Pressable>
                </Card>
              ))}
            </View>
          )}
        </Animated.View>

        {featured.length ? (
          <View testID="home-featured-section" style={{ gap: space.sm, marginTop: space.md, paddingHorizontal: space.lg }}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm }}>
              <Ionicons name="star" size={18} color={colors.brandTertiary} />
              <T size={18} weight="800" style={{ flex: 1 }}>{t("feat.home_title")}</T>
              <T size={11} color={colors.muted}>{t("feat.sponsored")}</T>
            </View>
            <ScrollView testID="home-featured-list" horizontal showsHorizontalScrollIndicator={false} style={{ marginHorizontal: -space.lg }} contentContainerStyle={{ gap: space.md, paddingHorizontal: space.lg }}>
              {featured.map((tr) => (
                <View key={tr.trip_id} testID={`home-featured-${tr.trip_id}`} style={{ width: 310, flexShrink: 0 }}>
                  <RideCard trip={tr} />
                </View>
              ))}
            </ScrollView>
          </View>
        ) : null}
      </ScrollView>
    </View>
  );
}
