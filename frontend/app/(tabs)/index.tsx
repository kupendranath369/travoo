import Ionicons from "@react-native-vector-icons/ionicons";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { Pressable, RefreshControl, ScrollView, View } from "react-native";
import Animated, { FadeInDown } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { Logo } from "@/src/components/Logo";
import { Card, IconName, T, radius, space } from "@/src/components/ui";
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
  const [unread, setUnread] = useState(0);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    const [r, n] = await Promise.all([api("/searches").catch(() => []), api("/notifications").catch(() => ({ unread: 0 }))]);
    setRecent(r);
    setUnread(n.unread);
  }, []);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const icon = (name: IconName, onPress: () => void, testID: string, dot?: boolean) => (
    <Pressable testID={testID} onPress={onPress} hitSlop={6} style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center" }}>
      <Ionicons name={name} size={20} color={colors.brand} />
      {dot ? <View testID={`${testID}-dot`} style={{ position: "absolute", top: 7, right: 8, width: 9, height: 9, borderRadius: 5, backgroundColor: colors.brandTertiary }} /> : null}
    </Pressable>
  );

  const service = (testID: string, ic: IconName, title: string, sub: string, bg: string, fg: string, onPress: () => void, delay: number) => (
    <Animated.View entering={FadeInDown.delay(delay).duration(400)}>
      <Pressable testID={testID} onPress={onPress} style={({ pressed }) => ({ backgroundColor: bg, borderRadius: radius.lg, padding: space.lg, flexDirection: "row", alignItems: "center", gap: space.md, opacity: pressed ? 0.9 : 1 })}>
        <View style={{ width: 52, height: 52, borderRadius: 26, backgroundColor: "rgba(255,255,255,0.18)", alignItems: "center", justifyContent: "center" }}>
          <Ionicons name={ic} size={26} color={fg} />
        </View>
        <View style={{ flex: 1 }}>
          <T size={17} weight="800" color={fg}>{title}</T>
          <T size={12} color={fg} style={{ opacity: 0.85 }}>{sub}</T>
        </View>
        <Ionicons name="arrow-forward" size={20} color={fg} />
      </Pressable>
    </Animated.View>
  );

  const repeat = (s: any) => {
    if (s.kind === "hire") router.push({ pathname: "/hire", params: { city: JSON.stringify(s.origin), service: s.service ?? "hourly" } });
    else router.push({ pathname: "/search", params: { from: JSON.stringify(s.origin), to: JSON.stringify(s.destination), date: s.date && s.date >= new Date().toISOString().slice(0, 10) ? s.date : "", seats: String(s.seats || 1) } });
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <View style={{ paddingTop: insets.top + space.sm, paddingHorizontal: space.lg, paddingBottom: space.sm, flexDirection: "row", alignItems: "center", backgroundColor: colors.surfaceSecondary, borderBottomWidth: 1, borderBottomColor: colors.border, gap: space.sm }}>
        <View style={{ flex: 1 }}><Logo size={34} /></View>
        {user?.role === "admin" && icon("shield-checkmark-outline", () => router.push("/admin"), "home-admin-button")}
        {icon("language-outline", () => router.push("/language?from=profile"), "home-language-button")}
        {icon("notifications-outline", () => router.push("/notifications"), "home-notifications-button", !!unread)}
        {icon("person-circle-outline", () => router.push("/profile"), "home-profile-button")}
        {icon("menu", () => router.push("/more"), "home-menu-button")}
      </View>
      <ScrollView
        testID="home-scroll"
        contentContainerStyle={{ padding: space.lg, gap: space.md, paddingBottom: (usesNativeTabs ? insets.bottom : 0) + space.xl }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} />}
      >
        {service("home-find-ride-button", "car-sport", t("v2.find_intercity"), t("v2.find_intercity_d"), colors.brand, colors.onBrand, () => router.push("/search"), 0)}
        {service("home-hire-driver-button", "key", t("v2.hire"), t("v2.hire_d"), colors.brandPrimary, colors.onBrandPrimary, () => router.push("/hire"), 80)}
        {service("home-offer-ride-button", "add-circle", t("btn.offer"), t("v2.offer_d"), colors.brandTertiary, colors.onBrandTertiary, () => router.push("/offer"), 160)}

        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: space.md }}>
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
      </ScrollView>
    </View>
  );
}
