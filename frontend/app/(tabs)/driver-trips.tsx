import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { FlatList, RefreshControl, View } from "react-native";

import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { Badge, Card, Chip, Empty, Header, Loading, T, space, statusTone } from "@/src/components/ui";
import { inr, useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

const TABS = [["upcoming", "Upcoming"], ["done", "Completed"], ["carpool", "Carpool rides"]] as const;

/** Driver mode "Trips" tab: local-driver trips (as driver) and published carpool rides. */
export default function DriverTripsTab() {
  const { colors } = useTheme();
  const { fmtDate } = useI18n();
  const { user } = useAuth();
  const router = useRouter();
  const [tab, setTab] = useState<string>("upcoming");
  const [hires, setHires] = useState<any[] | null>(null);
  const [rides, setRides] = useState<any[]>([]);
  const load = useCallback(async () => {
    const [h, r] = await Promise.all([api("/hire/bookings").catch(() => []), api("/trips/mine").catch(() => [])]);
    setHires(h.filter((x: any) => x.driver_id === user?.user_id));
    setRides(r);
  }, [user?.user_id]);
  useFocusEffect(useCallback(() => { load(); }, [load]));
  const data = !hires ? [] : tab === "carpool" ? rides : hires.filter((h) => (tab === "done" ? ["completed", "cancelled", "rejected"] : ["pending", "confirmed", "started"]).includes(h.status));
  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title="My Trips" back={false} />
      <View style={{ flexDirection: "row", gap: space.sm, padding: space.lg, paddingBottom: 0 }}>
        {TABS.map(([k, l]) => <Chip key={k} testID={`trips-tab-${k}`} label={l} active={tab === k} onPress={() => setTab(k)} />)}
      </View>
      {!hires ? <Loading /> : (
        <FlatList data={data} keyExtractor={(i) => i.booking_id ?? i.trip_id} refreshControl={<RefreshControl refreshing={false} onRefresh={load} />}
          contentContainerStyle={{ padding: space.lg, gap: space.md, paddingBottom: 120 }}
          ListEmptyComponent={<Empty icon="car-outline" title="No trips here yet" body={tab === "carpool" ? "Rides you publish appear here." : "Accepted Rent / Book Car trips appear here."} />}
          renderItem={({ item }) => tab === "carpool" ? (
            <Card testID={`trips-ride-${item.trip_id}`} onPress={() => router.push(`/trip/${item.trip_id}`)} style={{ gap: space.xs }}>
              <View style={{ flexDirection: "row", justifyContent: "space-between", gap: space.sm }}>
                <T weight="800" style={{ flex: 1 }} numberOfLines={1}>{item.origin.name} → {item.destination.name}</T>
                <Badge label={item.status} tone={statusTone(item.status)} />
              </View>
              <T size={13} color={colors.muted}>{fmtDate(item.date)} · {item.time} · {item.seats_total - item.seats_available}/{item.seats_total} seats · {inr(item.price)}/seat</T>
            </Card>
          ) : (
            <Card testID={`trips-hire-${item.booking_id}`} onPress={() => router.push(`/hire/${item.booking_id}`)} style={{ gap: space.xs }}>
              <View style={{ flexDirection: "row", justifyContent: "space-between", gap: space.sm }}>
                <T weight="800" style={{ flex: 1 }} numberOfLines={1}>{item.route}</T>
                <Badge label={item.status} tone={statusTone(item.status)} />
              </View>
              <T size={13} color={colors.muted}>{fmtDate(item.date)} · {item.time} · {item.service === "book" ? "Book Car" : "Rent a Driver"} · {item.hours} h</T>
              <T weight="800" color={colors.success}>{inr(item.service_fee)}</T>
            </Card>
          )} />
      )}
    </View>
  );
}
