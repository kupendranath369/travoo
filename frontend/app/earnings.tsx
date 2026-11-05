import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { Badge, Card, Empty, ErrorBox, Header, Loading, Section, T, space } from "@/src/components/ui";
import { inr, useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

const LEDGER_LABEL: Record<string, string> = { expected: "earn.confirmed", expected_reversed: "earn.cancelled", finalized: "earn.completed", settled_cash: "earn.cash", settled_upi: "earn.upi" };

export default function EarningsScreen() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t, fmtDate } = useI18n();
  const router = useRouter();
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState("");
  const load = useCallback(async () => {
    try {
      setD(await api("/earnings"));
      setErr("");
    } catch (e: any) {
      setErr(e.message);
    }
  }, []);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  if (err) return <View style={{ flex: 1 }}><Header title={t("earn.title")} /><ErrorBox message={err} onRetry={load} /></View>;
  if (!d) return <View style={{ flex: 1 }}><Header title={t("earn.title")} /><Loading /></View>;
  const s = d.summary;
  const tiles: [string, string, string][] = [
    ["earn.expected", inr(s.expected), "earn-expected"],
    ["earn.confirmed", inr(s.confirmed_value), "earn-confirmed"],
    ["earn.cancelled", inr(s.cancelled), "earn-cancelled"],
    ["earn.trips", String(s.completed_trips), "earn-trips"],
    ["earn.seats", String(s.seats), "earn-seats"],
    ["earn.cash", inr(s.cash), "earn-cash"],
    ["earn.upi", inr(s.upi), "earn-upi"],
  ];

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title={t("earn.title")} />
      <ScrollView contentContainerStyle={{ padding: space.lg, gap: space.lg, paddingBottom: insets.bottom + space.xl }}>
        <Card style={{ backgroundColor: colors.brand, borderColor: colors.brand, gap: space.xs }}>
          <T color={colors.onBrand} style={{ opacity: 0.8 }}>{t("earn.completed")}</T>
          <T testID="earn-completed" size={32} weight="800" color={colors.onBrand}>{inr(s.completed)}</T>
          <T size={12} color={colors.onBrand} style={{ opacity: 0.8 }}>{t("earn.no_commission")}</T>
        </Card>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.md }}>
          {tiles.map(([k, v, id]) => (
            <Card key={k} style={{ width: "47%", flexGrow: 1, gap: 4, padding: space.md }}>
              <T size={12} color={colors.muted}>{t(k)}</T>
              <T testID={id} size={18} weight="800">{v}</T>
            </Card>
          ))}
        </View>
        <Section title={t("earn.by_trip")}>
          {d.by_trip.length === 0 ? <Empty icon="wallet-outline" title={t("earn.empty")} /> : null}
          {d.by_trip.map((x: any) => (
            <Card key={x.trip_id} testID={`earn-trip-${x.trip_id}`} onPress={() => router.push(`/trip/${x.trip_id}`)} style={{ gap: 4 }}>
              <T weight="800">{x.route}</T>
              <T size={12} color={colors.muted}>{fmtDate(x.date)} · {inr(x.price)} × {x.seats}</T>
              <View style={{ flexDirection: "row", gap: space.sm }}>
                {x.expected ? <Badge label={`${t("earn.expected")} ${inr(x.expected)}`} tone="warning" /> : null}
                {x.completed ? <Badge label={`${t("earn.completed")} ${inr(x.completed)}`} tone="success" /> : null}
              </View>
            </Card>
          ))}
        </Section>
        <Section title={t("earn.history")}>
          {d.history.map((h: any) => (
            <View key={h.entry_id} style={{ flexDirection: "row", justifyContent: "space-between", paddingVertical: space.sm, borderBottomWidth: 1, borderBottomColor: colors.divider, gap: space.md }}>
              <View style={{ flex: 1 }}>
                <T size={13} weight="700">{t(LEDGER_LABEL[h.type] ?? h.type)}</T>
                <T size={11} color={colors.muted}>{h.route} · {h.booking_id}</T>
              </View>
              <T weight="800" color={h.amount < 0 ? colors.error : h.type.startsWith("settled") ? colors.success : colors.onSurface}>{h.amount < 0 ? "−" : ""}{inr(Math.abs(h.amount))}</T>
            </View>
          ))}
        </Section>
      </ScrollView>
    </View>
  );
}
