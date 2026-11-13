import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { RefreshControl, ScrollView, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { DateField } from "@/src/components/Calendar";
import { TimeChips } from "@/src/components/DateChips";
import { Area, SERVICE_LABEL, ServiceAreasEditor, ServicesPicker, STATUS_LABEL, Toggle, TYPE_LABEL, Vehicle, VehiclesEditor } from "@/src/components/LocalDriverParts";
import { useToast } from "@/src/components/toast";
import { Badge, Btn, Card, Chip, Empty, ErrorBox, Field, Header, Loading, T, space, statusTone } from "@/src/components/ui";
import { inr, useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

type Tab = "requests" | "settings" | "areas" | "vehicles";

/** Single Local Driver dashboard: status, services, service areas, availability, vehicles, bookings, earnings. */
export default function LocalDriverDashboard() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t, fmtDate } = useI18n();
  const router = useRouter();
  const toast = useToast();
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState("");
  const [tab, setTab] = useState<Tab>("requests");
  const [saving, setSaving] = useState("");
  const [areas, setAreas] = useState<Area[]>([]);
  const [cities, setCities] = useState("");
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [days, setDays] = useState<number[]>([]);
  const [from, setFrom] = useState("08:00");
  const [to, setTo] = useState("20:00");
  const [blocked, setBlocked] = useState<string[]>([]);
  const [blockPick, setBlockPick] = useState<string | null>(null);

  const load = useCallback(() => api("/pro/dashboard").then((r) => {
    setD(r);
    const p = r.profile;
    if (p) {
      setAreas(p.service_areas ?? []); setCities((p.cities_covered ?? []).join(", ")); setVehicles(p.vehicles ?? []);
      setDays(p.days ?? []); setFrom(p.start_time ?? "08:00"); setTo(p.end_time ?? "20:00"); setBlocked(p.blocked_dates ?? []);
    }
  }).catch((e) => setErr(e.message)), []);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  if (err) return <View style={{ flex: 1 }}><Header title="Local Driver" /><ErrorBox message={err} onRetry={load} /></View>;
  if (!d) return <View style={{ flex: 1 }}><Header title="Local Driver" /><Loading /></View>;
  const p = d.profile;
  if (!p) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.surface }}>
        <Header title="Local Driver" />
        <Empty icon="briefcase-outline" title="Become a Travoo Local Driver" body="Register once and offer Rent a Driver, Book a Driver, or both." action={<Btn testID="dash-register" label="Register as Local Driver" onPress={() => router.push("/hire/register")} />} />
      </View>
    );
  }

  const save = async (key: string, body: any, path = "/pro/settings") => {
    setSaving(key);
    try { await api(path, { method: "PUT", body }); toast("Saved"); await load(); } catch (e: any) { toast(e.message, "error"); }
    setSaving("");
  };
  const status = p.availability_status ?? "available";
  const services: string[] = p.services ?? ["rent"];
  const dayNames = t("v2.days").split(",");

  const bookingRow = (h: any) => (
    <Card key={h.booking_id} testID={`dash-booking-${h.booking_id}`} onPress={() => router.push(`/hire/${h.booking_id}`)} style={{ gap: 4 }}>
      <View style={{ flexDirection: "row", gap: space.sm, alignItems: "center" }}>
        <T weight="800" style={{ flex: 1 }} numberOfLines={1}>{h.route}</T>
        <Badge label={t(`status.${h.status}`)} tone={statusTone(h.status)} />
      </View>
      <T size={12} color={colors.muted}>{SERVICE_LABEL[h.service ?? "rent"]} · {TYPE_LABEL[h.service_type] ?? h.service_type} · {fmtDate(h.date)} {h.time}</T>
      <T size={13} weight="700" color={colors.brandPrimary}>{inr(h.service_fee)}</T>
    </Card>
  );

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title="Local Driver dashboard" right={<Btn small variant="ghost" icon="person-outline" label="" testID="dash-profile-link" onPress={() => router.push("/hire/register")} />} />
      <KeyboardAwareScrollView bottomOffset={24} keyboardShouldPersistTaps="handled" refreshControl={<RefreshControl refreshing={false} onRefresh={load} />}
        contentContainerStyle={{ padding: space.lg, gap: space.md, paddingBottom: insets.bottom + space.xl }}>
        <Card style={{ gap: space.sm }}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm }}>
            <T weight="800" size={16} style={{ flex: 1 }}>{p.name}</T>
            <Badge testID="dash-verify-status" label={t(`verify.status.${p.status}`)} tone={statusTone(p.status)} />
          </View>
          <T size={12} color={colors.muted}>Home: {[p.home?.city, `${p.home?.subdistrict_name ?? ""} ${p.home?.sub_label ?? ""}`, p.home?.district_name, p.home?.state_name].filter(Boolean).join(", ")}</T>
          <View style={{ flexDirection: "row", gap: space.sm, flexWrap: "wrap" }}>
            {services.map((s) => <Badge key={s} testID={`dash-service-${s}`} label={SERVICE_LABEL[s]} tone="info" />)}
          </View>
          <T size={13} weight="600">Availability</T>
          <View style={{ flexDirection: "row", gap: space.sm }}>
            {(["available", "busy", "offline"] as const).map((s) => (
              <Chip key={s} testID={`dash-status-${s}`} label={STATUS_LABEL[s]} active={status === s} onPress={() => status !== s && save(`st-${s}`, { availability_status: s })} />
            ))}
          </View>
          {status !== "available" ? <T size={12} color={colors.brandTertiary}>You will not receive new requests while {STATUS_LABEL[status].toLowerCase()}.</T> : null}
          {p.status !== "approved" ? <T size={12} color={colors.muted}>Requests start once your profile is approved.</T> : null}
        </Card>

        {d.earnings ? (
          <View style={{ flexDirection: "row", gap: space.sm }}>
            {[["Completed", String(d.earnings.completed)], ["Total earned", inr(d.earnings.total)], ["This month", inr(d.earnings.this_month)]].map(([k, v]) => (
              <Card key={k} style={{ flex: 1, gap: 2, padding: space.md }}>
                <T size={11} color={colors.muted}>{k}</T>
                <T testID={`dash-earn-${k.replace(/\s/g, "-").toLowerCase()}`} weight="800" size={16}>{v}</T>
              </Card>
            ))}
          </View>
        ) : null}

        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm }}>
          {([["requests", "Bookings"], ["settings", "Services & time"], ["areas", "Service areas"], ["vehicles", "Vehicles"]] as const).map(([k, l]) => (
            <Chip key={k} testID={`dash-tab-${k}`} label={l} active={tab === k} onPress={() => setTab(k)} />
          ))}
        </ScrollView>

        {tab === "requests" ? (
          <>
            <Btn testID="dash-open-requests" icon="mail-unread-outline" variant={d.open_requests ? "primary" : "outline"} label={`Booking requests (${d.open_requests} open)`} onPress={() => router.push("/hire/requests")} />
            <T weight="800">Upcoming bookings</T>
            {d.upcoming.length ? d.upcoming.map(bookingRow) : <T color={colors.muted}>No upcoming bookings</T>}
            <T weight="800">Booking history</T>
            {d.history.length ? d.history.map(bookingRow) : <T color={colors.muted}>No past bookings yet</T>}
          </>
        ) : null}

        {tab === "settings" ? (
          <>
            <T weight="800">Services</T>
            <ServicesPicker testPrefix="dash-svc" value={services} onChange={(v) => save("svc", { services: v })} />
            {!p.vehicles?.length ? <T size={12} color={colors.muted}>Add a vehicle (Vehicles tab) to turn on Book a Driver.</T> : null}
            <Card style={{ gap: space.sm }}>
              <Toggle testID="dash-outstation" label="Accept outstation trips" value={!!p.accepts_outstation} onChange={(v) => save("os", { accepts_outstation: v })} />
              <Toggle testID="dash-outside" label="Accept trips outside my service areas" value={!!p.accepts_outside_area} onChange={(v) => save("oa", { accepts_outside_area: v })} />
            </Card>
            <Card style={{ gap: space.sm }}>
              <T weight="800">Working days and hours</T>
              <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
                {dayNames.map((n, i) => <Chip key={n} testID={`dash-day-${i}`} label={n} active={days.includes(i)} onPress={() => setDays(days.includes(i) ? days.filter((x) => x !== i) : [...days, i])} />)}
              </View>
              <T size={13} weight="600" color={colors.muted}>{t("v2.from_time")}: {from}</T>
              <TimeChips value={from} onChange={setFrom} />
              <T size={13} weight="600" color={colors.muted}>{t("v2.to_time")}: {to}</T>
              <TimeChips value={to} onChange={setTo} />
              <T weight="700">Dates I am not available</T>
              <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
                {blocked.map((b) => <Chip key={b} testID={`dash-blocked-${b}`} icon="close" label={fmtDate(b)} onPress={() => setBlocked(blocked.filter((x) => x !== b))} />)}
              </View>
              <DateField testID="dash-block-date" label="Add an unavailable date" value={blockPick} onChange={(v) => { if (v && !blocked.includes(v)) setBlocked([...blocked, v].sort()); setBlockPick(null); }} />
              <Btn testID="dash-save-time" label="Save availability" disabled={!days.length} loading={saving === "time"} onPress={() => save("time", { days, start_time: from, end_time: to, blocked_dates: blocked })} />
            </Card>
          </>
        ) : null}

        {tab === "areas" ? (
          <Card style={{ gap: space.sm }}>
            <T weight="800">Service-area taluks</T>
            <ServiceAreasEditor testPrefix="dash-areas" areas={areas} onChange={setAreas} homeCode={p.home?.subdistrict_code} />
            <Field testID="dash-cities" label="Cities / towns you cover (comma separated)" value={cities} onChangeText={setCities} />
            <Btn testID="dash-save-areas" label="Save service areas" loading={saving === "areas"} onPress={() => save("areas", { service_taluks: areas.map((a) => a.code), cities_covered: cities.split(",").map((x) => x.trim()).filter(Boolean) })} />
          </Card>
        ) : null}

        {tab === "vehicles" ? (
          <>
            <T size={12} color={colors.muted}>Vehicles are only needed for Book a Driver. Mark a vehicle unavailable to stop matching it.</T>
            <VehiclesEditor testPrefix="dash-veh" vehicles={vehicles} onChange={setVehicles} />
            <Btn testID="dash-save-vehicles" label="Save vehicles" loading={saving === "veh"} onPress={() => save("veh", { vehicles }, "/pro/vehicles")} />
          </>
        ) : null}
      </KeyboardAwareScrollView>
    </View>
  );
}
