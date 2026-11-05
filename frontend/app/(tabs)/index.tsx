import Ionicons from "@react-native-vector-icons/ionicons";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { Pressable, RefreshControl, ScrollView, View } from "react-native";
import Animated, { FadeInDown } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Loc } from "@/src/api";
import { DateChips, isoDate } from "@/src/components/DateChips";
import { LocationField } from "@/src/components/LocationField";
import { Logo } from "@/src/components/Logo";
import { Badge, Btn, Card, Section, Stepper, T, radius, space } from "@/src/components/ui";
import { inr, useI18n } from "@/src/i18n";
import { usesNativeTabs } from "@/src/navigation";
import { useTheme } from "@/src/theme";

const HERO = "https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?w=1200&q=70";

export default function Home() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t } = useI18n();
  const router = useRouter();
  const [from, setFrom] = useState<Loc | null>(null);
  const [to, setTo] = useState<Loc | null>(null);
  const [date, setDate] = useState<string | null>(isoDate(new Date()));
  const [pax, setPax] = useState(1);
  const [routes, setRoutes] = useState<any[]>([]);
  const [unread, setUnread] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const [err, setErr] = useState("");
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const [r, n] = await Promise.all([api("/routes/popular"), api("/notifications")]);
      setRoutes(r);
      setUnread(n.unread);
    } catch (e: any) {
      setErr(e.message);
    }
  }, []);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const find = (o = from, d = to) => {
    if (!o || !d) return setErr(t("search.pick_both"));
    setErr("");
    router.push({ pathname: "/search", params: { from: JSON.stringify(o), to: JSON.stringify(d), date: date ?? "", seats: String(pax) } });
  };

  const how = [["search", 1], ["ticket", 2], ["car-sport", 3], ["cash", 4]] as const;
  const why = [["shield-checkmark", "verified"], ["wallet", "afford"], ["alert-circle", "safety"], ["language", "lang"]] as const;

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <ScrollView
        testID="home-scroll"
        contentContainerStyle={{ paddingBottom: (usesNativeTabs ? insets.bottom : 0) + space.xl }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} />}
      >
        <View style={{ height: 330 + insets.top }}>
          <Image source={{ uri: HERO }} style={{ position: "absolute", width: "100%", height: "100%" }} contentFit="cover" />
          <LinearGradient colors={["rgba(7,59,130,0.75)", "rgba(7,59,130,0.35)", "rgba(7,59,130,0.9)"]} style={{ position: "absolute", width: "100%", height: "100%" }} />
          <View style={{ paddingTop: insets.top + space.md, paddingHorizontal: space.lg, flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
            <View style={{ backgroundColor: colors.surfaceSecondary, padding: 6, paddingRight: space.md, borderRadius: radius.md }}>
              <Logo size={32} />
            </View>
            <Pressable testID="home-notifications-button" onPress={() => router.push("/notifications")} style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: "rgba(255,255,255,0.2)", alignItems: "center", justifyContent: "center" }}>
              <Ionicons name="notifications" size={22} color={colors.onBrand} />
              {unread ? <View testID="home-unread-dot" style={{ position: "absolute", top: 8, right: 9, width: 10, height: 10, borderRadius: 5, backgroundColor: colors.brandTertiary }} /> : null}
            </Pressable>
          </View>
          <Animated.View entering={FadeInDown.duration(500)} style={{ paddingHorizontal: space.lg, marginTop: space.xl, gap: space.sm }}>
            <T testID="home-hero-title" size={30} weight="800" color={colors.onBrand}>{t("home.hero")}</T>
            <T size={15} color={colors.onBrand} style={{ opacity: 0.9 }}>{t("home.sub")}</T>
          </Animated.View>
        </View>

        <Animated.View entering={FadeInDown.delay(120).duration(500)} style={{ marginHorizontal: space.lg, marginTop: -70 }}>
          <Card testID="home-search-widget" style={{ gap: 0, paddingVertical: space.sm }}>
            <LocationField testID="home-from-field" label={t("search.from")} value={from} onChange={setFrom} icon="radio-button-on" />
            <View style={{ height: 1, backgroundColor: colors.divider }} />
            <LocationField testID="home-to-field" label={t("search.to")} value={to} onChange={setTo} icon="location" />
            <View style={{ height: 1, backgroundColor: colors.divider }} />
            <View style={{ paddingVertical: space.sm, gap: space.xs }}>
              <T size={12} color={colors.muted}>{t("search.date")}</T>
              <DateChips value={date} onChange={setDate} allowAny days={30} testID="home-date" />
            </View>
            <View style={{ height: 1, backgroundColor: colors.divider }} />
            <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingVertical: space.sm }}>
              <View style={{ flexDirection: "row", gap: space.md, alignItems: "center" }}>
                <Ionicons name="people-outline" size={20} color={colors.brandPrimary} />
                <T weight="600">{t("search.passengers")}</T>
              </View>
              <Stepper testID="home-passengers" value={pax} onChange={setPax} />
            </View>
            {err ? <T testID="home-search-error" size={13} color={colors.error}>{err}</T> : null}
            <View style={{ flexDirection: "row", gap: space.sm, paddingTop: space.sm }}>
              <Btn testID="home-find-ride-button" style={{ flex: 1 }} icon="search" label={t("btn.find")} onPress={() => find()} />
              <Btn testID="home-offer-ride-button" style={{ flex: 1 }} variant="accent" icon="add-circle" label={t("btn.offer")} onPress={() => router.push("/offer")} />
            </View>
          </Card>
        </Animated.View>

        <View style={{ padding: space.lg, gap: space.xxl, paddingTop: space.xl }}>
          <Section title={t("home.popular")}>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.md }}>
              {routes.map((r) => (
                <Pressable key={r.route_id} testID={`popular-route-${r.route_id}`} onPress={() => { setFrom(r.origin); setTo(r.destination); find(r.origin, r.destination); }} style={{ width: 200, borderRadius: radius.lg, padding: space.lg, backgroundColor: colors.brand, gap: space.sm }}>
                  <Ionicons name="trail-sign" size={20} color={colors.brandTertiary} />
                  <T weight="800" color={colors.onBrand} numberOfLines={1}>{r.origin.name}</T>
                  <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
                    <Ionicons name="arrow-forward" size={14} color={colors.brandTertiary} />
                    <T weight="800" color={colors.onBrand} numberOfLines={1}>{r.destination.name}</T>
                  </View>
                  <T size={12} color={colors.onBrand} style={{ opacity: 0.8 }}>~{inr(r.price_hint)} {t("ride.per_seat")}</T>
                </Pressable>
              ))}
            </ScrollView>
          </Section>

          <Section title={t("home.how")}>
            {how.map(([icon, n]) => (
              <View key={n} style={{ flexDirection: "row", gap: space.md, alignItems: "center" }}>
                <View style={{ width: 48, height: 48, borderRadius: 24, backgroundColor: n === 4 ? colors.accentSoft : colors.brandSoft, alignItems: "center", justifyContent: "center" }}>
                  <Ionicons name={icon} size={22} color={n === 4 ? colors.brandTertiary : colors.brandPrimary} />
                </View>
                <View style={{ flex: 1 }}>
                  <T weight="700">{n}. {t(`how.${n}.t`)}</T>
                  <T size={13} color={colors.muted}>{t(`how.${n}.d`)}</T>
                </View>
              </View>
            ))}
          </Section>

          <Card style={{ backgroundColor: colors.accentSoft, borderColor: colors.brandTertiary, flexDirection: "row", gap: space.md, alignItems: "center" }}>
            <Ionicons name="cash-outline" size={28} color={colors.brandTertiary} />
            <View style={{ flex: 1 }}>
              <T weight="800">{t("pay.direct")}</T>
              <T size={12} color={colors.muted}>{t("pay.note")}</T>
            </View>
          </Card>

          <Section title={t("home.why")}>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.md }}>
              {why.map(([icon, k]) => (
                <Card key={k} style={{ width: "47%", flexGrow: 1, gap: space.sm }}>
                  <Ionicons name={icon} size={24} color={colors.brandPrimary} />
                  <T weight="700">{t(`why.${k}.t`)}</T>
                  <T size={12} color={colors.muted}>{t(`why.${k}.d`)}</T>
                </Card>
              ))}
            </View>
          </Section>

          <Section title={t("safety.title")} right={<Btn small variant="ghost" label={t("common.view_all")} onPress={() => router.push("/support")} testID="home-safety-link" />}>
            <Card style={{ gap: space.sm }}>
              {[1, 2, 3, 4].map((i) => (
                <View key={i} style={{ flexDirection: "row", gap: space.sm }}>
                  <Ionicons name="checkmark-circle" size={18} color={colors.success} />
                  <T size={13} style={{ flex: 1 }}>{t(`safety.${i}`)}</T>
                </View>
              ))}
            </Card>
          </Section>

          <Section title={t("home.testimonials")} right={<Badge label={t("home.sample")} tone="muted" />}>
            {[["Rohit, Pune", 1], ["Lakshmi, Madurai", 2]].map(([n, i]) => (
              <Card key={i} style={{ gap: space.sm }}>
                <Ionicons name="chatbox-ellipses" size={20} color={colors.brandTertiary} />
                <T size={14}>“{t(`testi.${i}`)}”</T>
                <T size={12} weight="700" color={colors.muted}>— {n}</T>
              </Card>
            ))}
          </Section>

          <Section title={t("home.faq")}>
            {[1, 2, 3, 4].map((i) => (
              <Card key={i} testID={`faq-${i}`} onPress={() => setOpenFaq(openFaq === i ? null : i)} style={{ gap: space.sm, padding: space.md }}>
                <View style={{ flexDirection: "row", justifyContent: "space-between", gap: space.sm }}>
                  <T weight="700" style={{ flex: 1 }}>{t(`faq.${i}.q`)}</T>
                  <Ionicons name={openFaq === i ? "chevron-up" : "chevron-down"} size={18} color={colors.muted} />
                </View>
                {openFaq === i ? <T size={13} color={colors.muted}>{t(`faq.${i}.a`)}</T> : null}
              </Card>
            ))}
          </Section>

          <Section title={t("home.contact")}>
            <T color={colors.muted}>{t("home.contact_body")}</T>
            <T size={12} color={colors.muted}>{t("support.grievance")}</T>
          </Section>

          <View testID="home-footer" style={{ alignItems: "center", gap: space.sm, paddingTop: space.lg, borderTopWidth: 1, borderTopColor: colors.border }}>
            <Logo size={34} />
            <T size={12} weight="700" color={colors.brandPrimary}>{t("app.motto")}</T>
            <View style={{ flexDirection: "row", gap: space.md, flexWrap: "wrap", justifyContent: "center" }}>
              {["terms", "privacy", "cancellation"].map((d) => (
                <T key={d} size={12} color={colors.muted} onPress={() => router.push(`/legal?doc=${d}`)} testID={`footer-${d}-link`}>{t(`legal.${d}`)}</T>
              ))}
            </View>
            <T size={11} color={colors.muted}>{t("footer.rights")}</T>
          </View>
        </View>
      </ScrollView>
    </View>
  );
}
