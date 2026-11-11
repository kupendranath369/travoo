import Ionicons from "@react-native-vector-icons/ionicons";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { Pressable, RefreshControl, ScrollView, View } from "react-native";
import Animated, { FadeInDown } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Loc, pictureUrl } from "@/src/api";
import { DateField } from "@/src/components/Calendar";
import { HireDriverArt } from "@/src/components/HireDriverArt";
import { LocationField } from "@/src/components/LocationField";
import { Logo } from "@/src/components/Logo";
import { RideCard } from "@/src/components/RideCard";
import { Avatar, Btn, Card, IconName, Stepper, T, radius, space } from "@/src/components/ui";
import { useAuth } from "@/src/auth";
import { useI18n } from "@/src/i18n";
import { usesNativeTabs } from "@/src/navigation";
import { useTheme } from "@/src/theme";

export default function Home() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t, fmtDate } = useI18n();
  const router = useRouter();
  const { user } = useAuth();
  const [recent, setRecent] = useState<any[]>([]);
  const [featured, setFeatured] = useState<any[]>([]);
  const [unread, setUnread] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const [from, setFrom] = useState<Loc | null>(null);
  const [to, setTo] = useState<Loc | null>(null);
  const [date, setDate] = useState<string | null>(null);
  const [seats, setSeats] = useState(1);
  const [formErr, setFormErr] = useState("");

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

  const shortcut = (testID: string, ic: IconName | null, title: string, bg: string, fg: string, onPress: () => void) => (
    <Pressable testID={testID} onPress={onPress} style={({ pressed }) => ({ flex: 1, minHeight: 56, backgroundColor: bg, borderRadius: radius.lg, paddingHorizontal: space.md, flexDirection: "row", alignItems: "center", gap: space.sm, opacity: pressed ? 0.85 : 1, transform: [{ scale: pressed ? 0.98 : 1 }] })}>
      {ic ? (
        <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: colors.surfaceSecondary, alignItems: "center", justifyContent: "center" }}>
          <Ionicons name={ic} size={18} color={fg} />
        </View>
      ) : <HireDriverArt size={40} />}
      <T weight="800" size={14} color={fg} numberOfLines={1} style={{ flex: 1 }}>{title}</T>
    </Pressable>
  );

  const find = () => {
    if (!from || !to) return setFormErr(t("search.pick_both"));
    if (from.loc_id === to.loc_id) return setFormErr(t("home.same_place"));
    setFormErr("");
    router.push({ pathname: "/search", params: { from: JSON.stringify(from), to: JSON.stringify(to), date: date ?? "", seats: String(seats) } });
  };

  const repeat = (s: any) => {
    if (s.kind === "hire") router.push({ pathname: "/hire", params: { city: JSON.stringify(s.origin), service: s.service ?? "hourly" } });
    else router.push({ pathname: "/search", params: { from: JSON.stringify(s.origin), to: JSON.stringify(s.destination), date: s.date && s.date >= new Date().toISOString().slice(0, 10) ? s.date : "", seats: String(s.seats || 1) } });
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <View style={{ paddingTop: insets.top + space.sm, paddingHorizontal: space.lg, paddingBottom: space.sm, flexDirection: "row", alignItems: "center", backgroundColor: colors.surfaceSecondary, borderBottomWidth: 1, borderBottomColor: colors.border, gap: space.sm }}>
        <View style={{ flex: 1 }}><Logo size={34} /></View>
        {user?.role === "admin" && icon("shield-checkmark-outline", () => router.push("/admin/login"), "home-admin-button")}
        {icon("language-outline", () => router.push("/language?from=profile"), "home-language-button")}
        {icon("notifications-outline", () => router.push("/notifications"), "home-notifications-button", !!unread)}
        <Pressable testID="home-profile-button" accessibilityLabel={t("tab.profile")} onPress={() => router.push("/profile")} hitSlop={6}>
          <Avatar name={user?.name} uri={pictureUrl(user?.picture)} size={40} />
        </Pressable>
        {icon("menu", () => router.push("/more"), "home-menu-button")}
      </View>
      <ScrollView
        testID="home-scroll"
        contentContainerStyle={{ padding: space.lg, gap: space.md, paddingBottom: (usesNativeTabs ? insets.bottom : 0) + space.xl }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} />}
      >
        <Animated.View entering={FadeInDown.duration(400)}>
          <Card testID="home-booking-card" style={{ gap: space.sm, paddingVertical: space.md }}>
            <T size={20} weight="800">{t("home.where_to")}</T>
            <View>
              <LocationField testID="home-from-field" label={t("search.from")} value={from} onChange={(l) => { setFrom(l); setFormErr(""); }} icon="radio-button-on" />
              <View style={{ height: 1, backgroundColor: colors.divider }} />
              <LocationField testID="home-to-field" label={t("search.to")} value={to} onChange={(l) => { setTo(l); setFormErr(""); }} icon="location" />
              <Pressable testID="home-swap-button" accessibilityLabel={t("home.swap")} hitSlop={6} onPress={() => { setFrom(to); setTo(from); }}
                style={{ position: "absolute", right: 0, top: "50%", marginTop: -20, width: 40, height: 40, borderRadius: 20, backgroundColor: colors.surfaceTertiary, borderWidth: 1, borderColor: colors.border, alignItems: "center", justifyContent: "center" }}>
                <Ionicons name="swap-vertical" size={18} color={colors.brandPrimary} />
              </Pressable>
            </View>
            <DateField testID="home-date" label={t("search.date")} value={date} onChange={setDate} allowClear />
            <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
              <T weight="600">{t("search.passengers")}</T>
              <Stepper testID="home-passengers" value={seats} max={8} onChange={setSeats} />
            </View>
            {formErr ? <T testID="home-form-error" size={13} color={colors.error} weight="600">{formErr}</T> : null}
            <Btn testID="home-find-ride-button" icon="car-sport" label={t("btn.find")} onPress={find} />
          </Card>
        </Animated.View>

        <Animated.View entering={FadeInDown.delay(80).duration(400)} style={{ flexDirection: "row", gap: space.md }}>
          {shortcut("home-hire-driver-button", null, t("v2.hire"), colors.brandSoft, colors.brandPrimary, () => router.push("/hire"))}
          {shortcut("home-offer-ride-button", "add-circle", t("btn.offer"), colors.accentSoft, colors.brandTertiary, () => router.push("/offer"))}
        </Animated.View>

        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: space.sm }}>
          <T size={18} weight="800">{t("v2.recent")}</T>
          {recent.length ? <Pressable testID="home-clear-recent" onPress={async () => { await api("/searches", { method: "DELETE" }); setRecent([]); }} hitSlop={8}><T weight="700" color={colors.brandPrimary}>{t("v2.clear")}</T></Pressable> : null}
        </View>
        {recent.length === 0 ? <T testID="home-recent-empty" color={colors.muted}>{t("v2.recent_empty")}</T> : null}
        {recent.map((s) => (
          <Card key={s.key} testID={`recent-search-${s.key}`} onPress={() => repeat(s)} style={{ flexDirection: "row", gap: space.md, alignItems: "center", padding: space.md }}>
            <Ionicons name={s.kind === "hire" ? "key-outline" : "time-outline"} size={20} color={colors.brandPrimary} />
            <View style={{ flex: 1 }}>
              <T weight="700" numberOfLines={1}>{s.kind === "hire" ? `${s.origin?.name} · ${t(`v2.svc.${s.service ?? "hourly"}`)}` : `${s.origin?.name} → ${s.destination?.name}`}</T>
              <T size={12} color={colors.muted}>{s.kind === "hire" ? t("v2.hire") : t("v2.find_intercity")} · {s.date ? fmtDate(s.date) : t("search.any_date")} · {fmtDate(s.at, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</T>
            </View>
            <Ionicons name="refresh" size={18} color={colors.muted} />
          </Card>
        ))}

        {featured.length ? (
          <View testID="home-featured-section" style={{ gap: space.sm, marginTop: space.md }}>
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
