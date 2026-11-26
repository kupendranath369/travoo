import { useFocusEffect } from "expo-router";
import React, { useCallback, useState } from "react";
import { ScrollView, View } from "react-native";

import { api } from "@/src/api";
import { float } from "@/src/components/localdriver/parts";
import { Chip, T, radius, space } from "@/src/components/ui";
import { inr, useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

const SVC = [["all", "All"], ["carpool", "Carpooling"], ["rent", "Rent a Driver"], ["book", "Book a Car"]] as const;
const PER = [["today", "Today"], ["week", "This week"], ["month", "This month"]] as const;

/** Unified earnings from completed bookings only (carpool + local driver), no simulated numbers. */
export function UnifiedEarnings() {
  const { colors } = useTheme();
  const { fmtDate } = useI18n();
  const [d, setD] = useState<any>(null);
  const [svc, setSvc] = useState<string>("all");
  useFocusEffect(useCallback(() => { api("/driver/earnings-summary").then(setD).catch(() => setD(null)); }, []));
  if (!d) return null;
  const tt = d.totals[svc];
  const items = d.items.filter((i: any) => svc === "all" || i.service === svc);
  return (
    <View testID="unified-earnings" style={{ gap: space.md }}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm }}>
        {SVC.map(([k, l]) => <Chip key={k} testID={`earn-svc-${k}`} label={l} active={svc === k} onPress={() => setSvc(k)} />)}
      </ScrollView>
      <View style={{ flexDirection: "row", gap: space.sm }}>
        {PER.map(([k, l]) => (
          <View key={k} testID={`earn-${k}`} style={[float, { flex: 1, padding: space.md, borderRadius: radius.lg, backgroundColor: colors.surfaceSecondary, gap: 2 }]}>
            <T size={11} color={colors.muted}>{l}</T>
            <T testID={`earn-${k}-net`} size={17} weight="800">{inr(tt[k].net)}</T>
            <T size={11} color={colors.muted}>{tt[k].trips} trips</T>
          </View>
        ))}
      </View>
      <View style={[float, { flexDirection: "row", justifyContent: "space-between", padding: space.md, borderRadius: radius.lg, backgroundColor: colors.accentSoft }]}>
        <View><T size={11} color={colors.muted}>Completed trips</T><T testID="earn-all-trips" weight="800" size={16}>{tt.all.trips}</T></View>
        <View><T size={11} color={colors.muted}>Total earned</T><T testID="earn-all-net" weight="800" size={16}>{inr(tt.all.net)}</T></View>
        <View><T size={11} color={colors.muted}>Commission ({d.commission_pct}%)</T><T testID="earn-commission" weight="800" size={16}>{inr(tt.all.commission)}</T></View>
      </View>
      {items.length === 0 ? <T testID="earn-empty" size={13} color={colors.muted}>No completed trips yet. Earnings appear here after a trip is completed.</T> : null}
      {items.slice(0, 30).map((i: any) => (
        <View key={i.id} testID={`earn-item-${i.id}`} style={{ flexDirection: "row", alignItems: "center", gap: space.sm, paddingVertical: space.xs }}>
          <View style={{ flex: 1 }}>
            <T size={13} weight="700" numberOfLines={1}>{i.route}</T>
            <T size={11} color={colors.muted}>{i.service === "carpool" ? "Carpooling" : i.service === "book" ? "Book a Car" : "Rent a Driver"} · {fmtDate(i.at.slice(0, 10))}</T>
          </View>
          <T weight="800">{inr(i.net)}</T>
        </View>
      ))}
    </View>
  );
}
