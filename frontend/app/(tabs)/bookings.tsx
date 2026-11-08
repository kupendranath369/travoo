import Ionicons from "@react-native-vector-icons/ionicons";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { FlatList, RefreshControl, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { Badge, Card, Chip, Empty, ErrorBox, Loading, T, space, statusTone } from "@/src/components/ui";
import { inr, useI18n } from "@/src/i18n";
import { usesNativeTabs } from "@/src/navigation";
import { useTheme } from "@/src/theme";

export default function BookingsScreen() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t, fmtDate } = useI18n();
  const router = useRouter();
  const [tab, setTab] = useState<"passenger" | "driver" | "hire">("passenger");
  const [rows, setRows] = useState<any[] | null>(null);
  const [err, setErr] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setErr("");
    try {
      setRows(await api(tab === "passenger" ? "/bookings/mine" : tab === "hire" ? "/hire/bookings" : "/trips/mine"));
    } catch (e: any) {
      setErr(e.message);
    }
  }, [tab]);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const status = (s: string) => <Badge label={t(`status.${s}`)} tone={statusTone(s)} />;

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <View style={{ paddingTop: insets.top + space.sm, backgroundColor: colors.surfaceSecondary, borderBottomWidth: 1, borderBottomColor: colors.border }}>
        <T size={22} weight="800" style={{ paddingHorizontal: space.lg }}>{t("tab.bookings")}</T>
        <View style={{ flexDirection: "row", gap: space.sm, paddingHorizontal: space.lg, height: 56, alignItems: "center" }}>
          <Chip testID="bookings-tab-passenger" icon="person-outline" label={t("bookings.as_passenger")} active={tab === "passenger"} onPress={() => { setRows(null); setTab("passenger"); }} />
          <Chip testID="bookings-tab-driver" icon="car-outline" label={t("bookings.as_driver")} active={tab === "driver"} onPress={() => { setRows(null); setTab("driver"); }} />
          <Chip testID="bookings-tab-hire" icon="key-outline" label={t("v2.hire_bookings")} active={tab === "hire"} onPress={() => { setRows(null); setTab("hire"); }} />
        </View>
      </View>
      {err ? (
        <ErrorBox message={err} onRetry={load} />
      ) : rows === null ? (
        <Loading />
      ) : (
        <FlatList
          testID="bookings-list"
          data={rows}
          keyExtractor={(i) => i.booking_id ?? i.trip_id}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} />}
          contentContainerStyle={{ padding: space.lg, gap: space.md, paddingBottom: (usesNativeTabs ? insets.bottom : 0) + space.xl }}
          ListEmptyComponent={<Empty icon="ticket-outline" title={tab === "passenger" ? t("bookings.empty") : t("bookings.rides_empty")} />}
          renderItem={({ item }) =>
            tab === "hire" ? (
              <Card testID={`hire-row-${item.booking_id}`} onPress={() => router.push(`/hire/${item.booking_id}`)} style={{ gap: space.sm }}>
                <View style={{ flexDirection: "row", justifyContent: "space-between", gap: space.sm }}>
                  <T weight="800" style={{ flex: 1 }} numberOfLines={1}>{item.route}</T>
                  {status(item.status)}
                </View>
                <T size={13} color={colors.muted}>{t(`v2.svc.${item.service_type}`)} · {fmtDate(item.date)} · {item.time} · {item.hours}h</T>
                <T weight="800" color={colors.brandPrimary}>{inr(item.service_fee)}</T>
              </Card>
            ) : tab === "passenger" ? (
              <Card testID={`booking-row-${item.booking_id}`} onPress={() => router.push(`/booking/${item.booking_id}`)} style={{ gap: space.sm }}>
                <View style={{ flexDirection: "row", justifyContent: "space-between", gap: space.sm }}>
                  <T weight="800" style={{ flex: 1 }} numberOfLines={1}>{item.route}</T>
                  {status(item.status)}
                </View>
                <T size={13} color={colors.muted}>{fmtDate(item.date)} · {item.time} · {item.seats} {t("trip.seats")}</T>
                <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
                  <T size={12} color={colors.muted}>{t("booking.id")}: {item.booking_id}</T>
                  <T weight="800" color={colors.brandPrimary}>{inr(item.fare_total)}</T>
                </View>
              </Card>
            ) : (
              <Card testID={`my-trip-row-${item.trip_id}`} onPress={() => router.push(`/trip/${item.trip_id}`)} style={{ gap: space.sm }}>
                <View style={{ flexDirection: "row", justifyContent: "space-between", gap: space.sm }}>
                  <T weight="800" style={{ flex: 1 }} numberOfLines={1}>{item.origin.name} → {item.destination.name}</T>
                  {status(item.status)}
                </View>
                <T size={13} color={colors.muted}>{fmtDate(item.date)} · {item.time} · {inr(item.price)} {t("ride.per_seat")}</T>
                <View style={{ flexDirection: "row", gap: space.sm, alignItems: "center" }}>
                  <Ionicons name="people-outline" size={16} color={colors.muted} />
                  <T size={13}>{item.seats_total - item.seats_available}/{item.seats_total}</T>
                  {item.pending_count ? <Badge label={`${item.pending_count} ${t("status.pending")}`} tone="warning" /> : null}
                  {item.is_demo ? <Badge label={t("common.demo")} tone="muted" /> : null}
                </View>
              </Card>
            )
          }
        />
      )}
    </View>
  );
}
