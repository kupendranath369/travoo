import Ionicons from "@react-native-vector-icons/ionicons";
import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useEffect, useState } from "react";
import { FlatList, ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Loc, locPayload, publicPhoto } from "@/src/api";
import { DateField } from "@/src/components/Calendar";
import { isoDate, TimeChips } from "@/src/components/DateChips";
import { LocationField } from "@/src/components/LocationField";
import { HomeLoc, TalukPicker } from "@/src/components/TalukPicker";
import { useToast } from "@/src/components/toast";
import { Avatar, Badge, Btn, Card, Chip, Empty, Field, Header, Loading, Rating, Stepper, T, space } from "@/src/components/ui";
import { inr, useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

export const SERVICES = ["hourly", "half_day", "full_day", "one_way", "airport", "outstation", "custom"];
export const VTYPES = ["hatchback", "sedan", "suv", "muv", "luxury", "automatic", "ev"];
const LANGS = ["Hindi", "English", "Tamil", "Telugu", "Kannada", "Marathi", "Bengali", "Malayalam", "Gujarati", "Punjabi"];

export default function HireScreen() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t } = useI18n();
  const router = useRouter();
  const p = useLocalSearchParams<{ city?: string; service?: string }>();
  const [city, setCity] = useState<Loc | null>(p.city ? JSON.parse(p.city) : null);
  const [pickup, setPickup] = useState<Loc | null>(null);
  const [dest, setDest] = useState<Loc | null>(null);
  const [date, setDate] = useState<string | null>(isoDate(new Date(Date.now() + 86400000)));
  const [time, setTime] = useState("09:00");
  const [service, setService] = useState(p.service || "hourly");
  const [hours, setHours] = useState(4);
  const [vtype, setVtype] = useState("sedan");
  const [vdesc, setVdesc] = useState("");
  const [lang, setLang] = useState<string | null>(null);
  const [minExp, setMinExp] = useState(0);
  const [rows, setRows] = useState<any[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [taluk, setTaluk] = useState<HomeLoc>({ taluk: null, city: "", city_code: null, village_code: null, village_name: null });
  const [talukMethod, setTalukMethod] = useState("");
  const [identifying, setIdentifying] = useState(false);
  const [changeTaluk, setChangeTaluk] = useState(false);
  const [passengers, setPassengers] = useState(1);
  const [nearby, setNearby] = useState<{ rows: any[]; scope: string } | null>(null);
  const [sending, setSending] = useState(false);
  const toast = useToast();

  // Pickup (never destination) decides the matching taluk
  useEffect(() => {
    setNearby(null);
    setRows(null);
    if (!pickup?.loc_id) return;
    setIdentifying(true);
    api(`/hire/identify-taluk?loc_id=${encodeURIComponent(pickup.loc_id)}&pickup=${encodeURIComponent(pickup.name)}`)
      .then((r) => { setTaluk((v) => ({ ...v, taluk: r.subdistrict })); setTalukMethod(r.subdistrict ? r.method : "unmatched"); setChangeTaluk(!r.subdistrict); })
      .catch(() => { setTalukMethod("unmatched"); setChangeTaluk(true); })
      .finally(() => setIdentifying(false));
  }, [pickup?.loc_id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { if (service === "half_day") setHours(4); if (service === "full_day") setHours(8); }, [service]);

  const params = () => {
    const q = new URLSearchParams({ subdistrict_code: taluk.taluk!.code, date: date!, time, service, hours: String(hours), vehicle_type: vtype, min_exp: String(minExp) });
    if (lang) q.set("language", lang);
    return q;
  };
  const find = async () => {
    if (!city || !date) return setErr(`${t("v2.city")} *`);
    if (!pickup || !vdesc.trim()) return setErr(`${t("v2.pickup_loc")} / ${t("v2.your_vehicle")} *`);
    if (!taluk.taluk) return setErr("Choose the pickup taluk / sub-district");
    setErr("");
    setBusy(true);
    setNearby(null);
    try {
      const r = await api(`/hire/local-drivers?${params()}`);
      setRows(r.local);
      api("/searches", { body: { kind: "hire", origin: locPayload(city), date, service } }).catch(() => {});
    } catch (e: any) {
      setErr(e.message);
    }
    setBusy(false);
  };
  const findNearby = async () => {
    setBusy(true);
    try {
      const r = await api(`/hire/local-drivers?${params()}&nearby=true`);
      setNearby({ rows: r.nearby ?? [], scope: r.nearby_scope });
    } catch (e: any) { setErr(e.message); }
    setBusy(false);
  };
  const broadcast = async (includeNearby: boolean) => {
    setSending(true);
    try {
      const r = await api("/hire/requests", { body: { service_type: service, date, time, hours, city: locPayload(city!), pickup: pickup!.name, destination: dest?.name ?? "", passengers, vehicle_type: vtype, vehicle_desc: vdesc.trim(), subdistrict_code: taluk.taluk!.code, taluk_method: talukMethod || "manual", include_nearby: includeNearby } });
      toast(`Request sent to ${r.notified} driver${r.notified > 1 ? "s" : ""}`);
      router.push("/hire/requests");
    } catch (e: any) { setErr(e.message); }
    setSending(false);
  };

  const request = (d: any) => router.push({ pathname: "/user/[id]", params: { id: d.user_id, hire: JSON.stringify({ driver_id: d.user_id, service_type: service, date, time, hours, city: locPayload(city!), pickup: locPayload(pickup!), destination: dest ? locPayload(dest) : null, vehicle_type: vtype, vehicle_desc: vdesc.trim(), estimate: d.estimate }) } });

  const form = (
    <View style={{ gap: space.md }}>
      <Card style={{ gap: 0, paddingVertical: space.sm }}>
        <LocationField testID="hire-city-field" label={t("v2.city")} value={city} onChange={setCity} icon="business-outline" />
        <DateField testID="hire-date" label={t("search.date")} value={date} onChange={setDate} />
        <LocationField testID="hire-pickup-field" label={t("v2.pickup_loc")} value={pickup} onChange={setPickup} icon="location-outline" />
        <LocationField testID="hire-destination-field" label={t("v2.destination_opt")} value={dest} onChange={setDest} icon="navigate-outline" />
      </Card>
      {pickup ? (
        <Card testID="hire-pickup-taluk-card" style={{ gap: space.xs }}>
          <T size={12} color={colors.muted}>Pickup taluk (drivers are matched from here, not the destination)</T>
          {identifying ? <T testID="hire-taluk-identifying" color={colors.muted}>Identifying taluk…</T> : taluk.taluk ? (
            <T testID="hire-pickup-taluk" weight="800">{taluk.taluk.name} {taluk.taluk.sub_label ?? ""} · {taluk.taluk.district_name}, {taluk.taluk.state_name}</T>
          ) : <T testID="hire-taluk-unmatched" color={colors.brandTertiary} weight="600">We couldn't identify the taluk for this pickup. Please choose it below.</T>}
          {taluk.taluk && !identifying ? <T size={11} color={colors.muted}>{talukMethod === "manual" ? "Chosen by you" : "Detected automatically from the pickup location — correct it if wrong"}</T> : null}
          {changeTaluk ? <TalukPicker testPrefix="hire-taluk" value={taluk} onChange={(v) => { setTaluk(v); setTalukMethod("manual"); setRows(null); setNearby(null); }} /> : (
            <Btn small variant="ghost" testID="hire-change-taluk" label="Change taluk" onPress={() => setChangeTaluk(true)} style={{ alignSelf: "flex-start" }} />
          )}
        </Card>
      ) : null}
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
        <T weight="600">{t("search.passengers")}</T>
        <Stepper testID="hire-passengers" value={passengers} max={8} onChange={setPassengers} />
      </View>
      <T size={13} weight="600" color={colors.muted}>{t("v2.service")}</T>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm }}>
        {SERVICES.map((s) => <Chip key={s} testID={`hire-service-${s}`} label={t(`v2.svc.${s}`)} active={service === s} onPress={() => setService(s)} />)}
      </ScrollView>
      <T size={13} weight="600" color={colors.muted}>{t("v2.start_time")}: {time}</T>
      <TimeChips value={time} onChange={setTime} />
      {["hourly", "custom", "outstation", "airport", "one_way"].includes(service) ? (
        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
          <T weight="600">{t("v2.hours")}</T>
          <Stepper testID="hire-hours" value={hours} max={72} onChange={setHours} />
        </View>
      ) : null}
      <T size={13} weight="600" color={colors.muted}>{t("v2.vehicle_type")}</T>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm }}>
        {VTYPES.map((v) => <Chip key={v} testID={`hire-vtype-${v}`} label={v.toUpperCase()} active={vtype === v} onPress={() => setVtype(v)} />)}
      </ScrollView>
      <Field testID="hire-vehicle-desc" label={t("v2.your_vehicle")} value={vdesc} onChangeText={setVdesc} placeholder="Honda City" />
      <T size={13} weight="600" color={colors.muted}>{t("v2.driver_language")}</T>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm }}>
        {LANGS.map((l) => <Chip key={l} testID={`hire-lang-${l}`} label={l} active={lang === l} onPress={() => setLang(lang === l ? null : l)} />)}
      </ScrollView>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
        <T weight="600">{t("v2.min_exp")} ({t("v2.years", { n: minExp })})</T>
        <Stepper testID="hire-min-exp" value={minExp} min={0} max={30} onChange={setMinExp} />
      </View>
      {err ? <T testID="hire-error" color={colors.error}>{err}</T> : null}
      <Btn testID="hire-find-button" icon="search" label={t("v2.find_drivers")} onPress={find} loading={busy} />
      <T size={12} color={colors.muted}>{t("v2.service_fee_note")}</T>
      {rows ? (
        <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm, marginTop: space.sm }}>
          <Ionicons name="location" size={18} color={colors.brandPrimary} />
          <T testID="hire-local-heading" size={16} weight="800" style={{ flex: 1 }}>LOCAL TALUK DRIVERS · {taluk.taluk?.name} ({rows.length})</T>
        </View>
      ) : null}
      {rows && rows.length ? <Btn testID="hire-broadcast-button" variant="outline" icon="megaphone-outline" label={`Send request to all ${rows.length} local driver${rows.length > 1 ? "s" : ""}`} loading={sending} onPress={() => broadcast(false)} /> : null}
    </View>
  );

  const card = (item: any, group: "local" | "nearby") => (
    <Card key={item.user_id} testID={`hire-driver-${item.user_id}`} onPress={() => request(item)} style={{ gap: space.sm }}>
      <View style={{ flexDirection: "row", gap: space.md, alignItems: "center" }}>
        <Avatar name={item.user.name} uri={item.user.has_photo ? publicPhoto(item.user_id) : null} size={52} />
        <View style={{ flex: 1 }}>
          <View style={{ flexDirection: "row", gap: 4, alignItems: "center" }}>
            <T weight="800">{item.user.name}</T>
            <Ionicons name="shield-checkmark" size={14} color={colors.success} />
          </View>
          <Rating value={item.user.rating_avg} count={item.user.rating_count} />
          <T size={12} color={colors.muted}>{t("v2.years", { n: item.experience_years })} · {item.languages.join(", ")}</T>
        </View>
        <View style={{ alignItems: "flex-end" }}>
          <T testID={`hire-estimate-${item.user_id}`} size={18} weight="800" color={colors.brandPrimary}>{inr(item.estimate)}</T>
          <T size={11} color={colors.muted}>{t("v2.est_charge")}</T>
        </View>
      </View>
      <View style={{ flexDirection: "row", gap: space.sm, flexWrap: "wrap" }}>
        <Badge testID={`hire-driver-group-${item.user_id}`} icon="location" label={group === "local" ? "LOCAL TALUK DRIVER" : "NEARBY TALUK"} tone={group === "local" ? "success" : "info"} />
        <Badge icon="shield-checkmark" label="Verified" tone="success" />
        <Badge label={`Home: ${item.home?.subdistrict_name}`} tone="muted" />
        <Badge label="Available · accepting bookings" tone="success" />
        <Badge label={item.vehicle_types.map((v: string) => v.toUpperCase()).join(", ")} tone="muted" />
      </View>
    </Card>
  );

  const footer = rows ? (
    <View style={{ gap: space.md }}>
      {!nearby ? (
        <Btn testID="hire-nearby-button" variant={rows.length ? "ghost" : "outline"} icon="git-network-outline" label={`Search nearby ${taluk.taluk?.sub_label?.toLowerCase() ?? "taluk"}s too`} loading={busy && !!rows} onPress={findNearby} />
      ) : (
        <>
          <T testID="hire-nearby-heading" size={16} weight="800">NEARBY TALUK DRIVERS ({nearby.rows.length})</T>
          <T size={12} color={colors.muted}>{nearby.scope}. These drivers are not from your pickup taluk.</T>
          {nearby.rows.length ? nearby.rows.map((d) => card(d, "nearby")) : <Empty icon="person-outline" title="No eligible drivers in nearby taluks either" />}
          {nearby.rows.length ? <Btn testID="hire-broadcast-nearby-button" variant="outline" icon="megaphone-outline" label="Send request to local + nearby drivers" loading={sending} onPress={() => broadcast(true)} /> : null}
        </>
      )}
    </View>
  ) : null;

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title={t("v2.hire_title")} right={
        <View style={{ flexDirection: "row" }}>
          <Btn small variant="ghost" icon="mail-unread-outline" label="" onPress={() => router.push("/hire/requests")} testID="hire-requests-link" />
          <Btn small variant="ghost" icon="briefcase-outline" label="" onPress={() => router.push("/hire/register")} testID="hire-register-link" />
        </View>} />
      <FlatList
        data={rows ?? []}
        keyExtractor={(d) => d.user_id}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{ padding: space.lg, gap: space.md, paddingBottom: insets.bottom + space.xl }}
        ListHeaderComponent={form}
        ListFooterComponent={footer ?? undefined}
        ListEmptyComponent={busy && !rows ? <Loading /> : rows ? <Empty icon="person-outline" title={`No eligible drivers registered in ${taluk.taluk?.name ?? "this taluk"} right now`} /> : undefined}
        renderItem={({ item }) => card(item, "local")}
      />
    </View>
  );
}
