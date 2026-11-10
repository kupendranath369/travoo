import { useLocalSearchParams } from "expo-router";
import React, { useCallback, useEffect, useState } from "react";
import { ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { adminApi } from "@/src/adminApi";
import { useToast } from "@/src/components/toast";
import { Badge, Btn, Card, ErrorBox, Header, Loading, Section, T, space } from "@/src/components/ui";
import { inr } from "@/src/i18n";
import { useTheme } from "@/src/theme";

export default function AdminPassengerDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const toast = useToast();
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setErr("");
    try {
      setD(await adminApi(`/admin/passengers/${id}/detail`));
    } catch (e: any) {
      setErr(e.message);
    }
  }, [id]);
  useEffect(() => { load(); }, [load]);

  const toggle = async () => {
    setBusy(true);
    try {
      await adminApi(`/admin/users/${id}/suspend`, { body: { suspended: !d.user.suspended } });
      toast(d.user.suspended ? "Account reactivated" : "Account suspended");
      await load();
    } catch (e: any) {
      toast(e.message, "error");
    }
    setBusy(false);
  };

  if (err) return <View style={{ flex: 1, backgroundColor: colors.surface }}><Header title="Passenger" /><ErrorBox message={err} onRetry={load} /></View>;
  if (!d) return <View style={{ flex: 1, backgroundColor: colors.surface }}><Header title="Passenger" /><Loading /></View>;
  const u = d.user;
  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title="Passenger" />
      <ScrollView contentContainerStyle={{ padding: space.lg, gap: space.lg, paddingBottom: insets.bottom + space.xl, width: "100%", maxWidth: 900, alignSelf: "center" }}>
        <Card style={{ gap: 4 }}>
          <T testID="admin-passenger-name" size={18} weight="800">{u.name}</T>
          <T size={13} color={colors.muted}>{u.email} {u.phone ? `· ${u.phone}` : ""}</T>
          <T size={12} color={colors.muted}>ID {u.user_id} · joined {new Date(u.created_at + "Z").toLocaleDateString()}</T>
          <T testID="admin-passenger-stats" size={13}>Rides {d.stats.total} · completed {d.stats.completed} · cancelled {d.stats.cancelled} · spent {inr(d.stats.spent)}</T>
          {u.suspended ? <T color={colors.error} weight="700">Account suspended</T> : null}
          {u.role !== "admin" ? <Btn testID="admin-passenger-suspend" variant={u.suspended ? "primary" : "danger"} label={u.suspended ? "Reactivate account" : "Suspend account"} loading={busy} onPress={toggle} /> : null}
        </Card>
        <Section title="Ride history">
          {d.rides.length === 0 ? <T color={colors.muted}>No rides yet</T> : null}
          {d.rides.map((r: any) => (
            <Card key={r.booking_id} testID={`admin-passenger-ride-${r.booking_id}`} style={{ gap: 2, padding: space.md }}>
              <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
                <T weight="700" style={{ flex: 1 }}>{r.route}</T>
                <Badge label={r.status} tone={r.status === "completed" ? "success" : r.status === "cancelled" ? "error" : "info"} />
              </View>
              <T size={12} color={colors.muted}>{r.date} {r.time} · {r.seats} seat · {inr(r.fare_total)} · driver {r.driver_name} · {r.booking_id}</T>
            </Card>
          ))}
        </Section>
        <Section title="Complaints & support tickets">
          {d.tickets.length === 0 ? <T color={colors.muted}>No complaints</T> : null}
          {d.tickets.map((tk: any) => (
            <Card key={tk.ticket_id} style={{ gap: 2, padding: space.md }}>
              <T weight="700">{tk.ticket_id} · {tk.type} · {tk.status}</T>
              <T size={12}>{tk.message ?? tk.subject ?? ""}</T>
            </Card>
          ))}
        </Section>
      </ScrollView>
    </View>
  );
}
