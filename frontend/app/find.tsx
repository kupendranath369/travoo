import Ionicons from "@react-native-vector-icons/ionicons";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { Pressable, ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Loc } from "@/src/api";
import { DateField } from "@/src/components/Calendar";
import { float } from "@/src/components/localdriver/parts";
import { LocationField } from "@/src/components/LocationField";
import { Btn, Header, Stepper, T, radius, space } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

export default function FindRide() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t } = useI18n();
  const router = useRouter();
  const [from, setFrom] = useState<Loc | null>(null);
  const [to, setTo] = useState<Loc | null>(null);
  const [date, setDate] = useState<string | null>(null);
  const [seats, setSeats] = useState(1);
  const [err, setErr] = useState("");
  const [routes, setRoutes] = useState<any[]>([]);
  useFocusEffect(useCallback(() => {
    api("/searches").then((r: any[]) => {
      const seen = new Set<string>();
      setRoutes(r.filter((s) => s.kind !== "hire" && s.destination && !seen.has(`${s.origin.loc_id}>${s.destination.loc_id}`) && seen.add(`${s.origin.loc_id}>${s.destination.loc_id}`)).slice(0, 5));
    }).catch(() => {});
  }, []));
  const go = (f: Loc | null, d: Loc | null, dt: string | null) => {
    if (!f || !d) return setErr(t("search.pick_both"));
    if (f.loc_id === d.loc_id) return setErr(t("home.same_place"));
    setErr("");
    router.push({ pathname: "/search", params: { from: JSON.stringify(f), to: JSON.stringify(d), date: dt ?? "", seats: String(seats) } });
  };
  const box = { ...float, backgroundColor: colors.surfaceSecondary, borderRadius: radius.lg, paddingHorizontal: space.md };
  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title="Find a Ride" />
      <ScrollView contentContainerStyle={{ padding: space.lg, gap: space.md, paddingBottom: insets.bottom + space.xxl }}>
        <View style={box}><LocationField testID="find-from-field" label="Leaving from" value={from} onChange={(l) => { setFrom(l); setErr(""); }} icon="location" /></View>
        <View style={box}><LocationField testID="find-to-field" label="Going to" value={to} onChange={(l) => { setTo(l); setErr(""); }} icon="location" /></View>
        <Pressable testID="find-swap-button" onPress={() => { setFrom(to); setTo(from); }} style={{ alignSelf: "flex-end", marginTop: -space.sm, flexDirection: "row", gap: 4, alignItems: "center" }}>
          <Ionicons name="swap-vertical" size={16} color={colors.brandSecondary} /><T size={12} weight="700" color={colors.brandSecondary}>Swap</T>
        </Pressable>
        <View style={[box, { paddingVertical: space.sm }]}><DateField testID="find-date" label="Travel Date" value={date} onChange={setDate} allowClear /></View>
        <View style={[box, { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingVertical: space.md }]}>
          <T weight="700">Passengers</T>
          <Stepper testID="find-seats" value={seats} min={1} max={6} onChange={setSeats} />
        </View>
        {err ? <T testID="find-error" color={colors.error} weight="600">{err}</T> : null}
        <Btn testID="find-ride-button" icon="arrow-forward" label="Find a Ride" onPress={() => go(from, to, date)} />
        <T size={16} weight="800" style={{ marginTop: space.md }}>Popular Routes</T>
        {routes.length === 0 ? <T testID="find-routes-empty" size={13} color={colors.muted}>Your frequent routes will appear here.</T> : null}
        {routes.map((s) => (
          <Pressable key={s.key} testID={`find-route-${s.key}`} onPress={() => go(s.origin, s.destination, null)} style={[box, { flexDirection: "row", alignItems: "center", gap: space.md, minHeight: 52 }]}>
            <Ionicons name="time-outline" size={18} color={colors.muted} />
            <T weight="700" style={{ flex: 1 }} numberOfLines={1}>{s.origin.name} → {s.destination.name}</T>
            <Ionicons name="chevron-forward" size={18} color={colors.muted} />
          </Pressable>
        ))}
      </ScrollView>
    </View>
  );
}
