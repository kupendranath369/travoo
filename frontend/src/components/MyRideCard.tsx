import Ionicons from "@react-native-vector-icons/ionicons";
import { useRouter } from "expo-router";
import React from "react";
import { View } from "react-native";

import { Badge, Card, T, space, statusTone } from "@/src/components/ui";
import { inr, useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

export function MyRideCard({ item }: { item: any }) {
  const { colors } = useTheme();
  const { t, fmtDate } = useI18n();
  const router = useRouter();
  return (
    <Card testID={`my-trip-row-${item.trip_id}`} onPress={() => router.push(`/trip/${item.trip_id}`)} style={{ gap: space.sm }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", gap: space.sm }}>
        <T weight="800" style={{ flex: 1 }} numberOfLines={1}>{item.origin.name} → {item.destination.name}</T>
        <Badge label={t(`status.${item.status}`)} tone={statusTone(item.status)} />
      </View>
      <T size={13} color={colors.muted}>{fmtDate(item.date)} · {item.time} · {inr(item.price)} {t("ride.per_seat")}</T>
      <View style={{ flexDirection: "row", gap: space.sm, alignItems: "center" }}>
        <Ionicons name="people-outline" size={16} color={colors.muted} />
        <T size={13}>{item.seats_total - item.seats_available}/{item.seats_total}</T>
        {item.pending_count ? <Badge label={`${item.pending_count} ${t("status.pending")}`} tone="warning" /> : null}
        {item.is_demo ? <Badge label={t("common.demo")} tone="muted" /> : null}
      </View>
    </Card>
  );
}
