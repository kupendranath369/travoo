import Ionicons from "@react-native-vector-icons/ionicons";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useEffect, useState } from "react";
import { FlatList, Pressable, ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Loc, locPayload, publicPhoto } from "@/src/api";
import { DateField } from "@/src/components/Calendar";
import { isoDate, TimeChips } from "@/src/components/DateChips";
import { HireDriverArt } from "@/src/components/HireDriverArt";
import { BOOK_OPTIONS, feeNote, RENT_OPTIONS, SERVICE_LABEL, VEHICLE_CATS } from "@/src/components/LocalDriverParts";
import { LocationField } from "@/src/components/LocationField";
import { HomeLoc, Taluk, TalukPicker } from "@/src/components/TalukPicker";
import { useToast } from "@/src/components/toast";
import { Avatar, Badge, Btn, Card, Chip, Empty, Field, Header, Loading, Rating, Stepper, T, space } from "@/src/components/ui";
import { inr, useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

const RENT_VTYPES = ["hatchback", "sedan", "suv", "muv", "luxury", "automatic", "ev"];
const GROUP: Record<string, [string, "success" | "info" | "accent"]> = { local: ["SERVES YOUR DESTINATION", "success"], nearby: ["NEARBY AREA", "info"], pickup_area: ["FROM PICKUP AREA · OUTSTATION", "accent"] };
const emptyLoc: HomeLoc = { taluk: null, city: "", city_code: null, village_code: null, village_name: null };

/** Identify the LGD taluk of a picked place. */
function useTaluk(loc: Loc | null) {
  const [taluk, setTaluk] = useState<Taluk | null>(null);
  const [method, setMethod] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    setTaluk(null);
    if (!loc?.loc_id) return;
    setBusy(true);
    api(`/hire/identify-taluk?loc_id=${encodeURIComponent(loc.loc_id)}&pickup=${encodeURIComponent(loc.name)}`)
      .then((r) => { setTaluk(r.subdistrict); setMethod(r.subdistrict ? r.method : "unmatched"); })
      .catch(() => setMethod("unmatched"))
      .finally(() => setBusy(false));
  }, [loc?.loc_id]); // eslint-disable-line react-hooks/exhaustive-deps
  return { taluk, setTaluk: (t: Taluk | null) => { setTaluk(t); setMethod("manual"); }, method, busy };
}

function ServiceChooser({ onPick, favs }: { onPick: (s: "rent" | "book") => void; favs: any[] }) {
  const { colors } = useTheme();
  const router = useRouter();
  const option = (s: "rent" | "book", icon: any, line: string) => (
    <Card testID={`hire-choose-${s}`} onPress={() => onPick(s)} style={{ flexDirection: "row", alignItems: "center", gap: space.md, paddingVertical: space.lg }}>
      <View style={{ width: 56, height: 56, borderRadius: 28, backgroundColor: s === "rent" ? colors.brandSoft : colors.surfaceTertiary, alignItems: "center", justifyContent: "center" }}>
        {s === "rent" ? <HireDriverArt size={36} /> : <Ionicons name={icon} size={28} color={colors.brandPrimary} />}
      </View>
      <View style={{ flex: 1 }}>
        <T size={17} weight="800">{SERVICE_LABEL[s].toUpperCase()}</T>
        <T color={colors.muted}>{line}</T>
      </View>
      <Ionicons name="chevron-forward" size={22} color={colors.muted} />
    </Card>
  );
  return (
    <View style={{ gap: space.md }}>
      {option("rent", "key-outline", "I have a car. I need a driver.")}
      {option("book", "car-sport-outline", "I need a car and a driver.")}
      <T size={12} color={colors.muted}>Drivers are matched by your DESTINATION taluk. Your pickup is shown to drivers so they can decide if they can reach it.</T>
      {favs.length ? (
        <View style={{ gap: space.sm, marginTop: space.md }}>
          <T weight="800">Favourite drivers</T>
          {favs.map((f) => (
            <Card key={f.user_id} testID={`hire-fav-${f.user_id}`} onPress={() => router.push(`/user/${f.user_id}`)} style={{ flexDirection: "row", alignItems: "center", gap: space.md }}>
              <Avatar name={f.user.name} uri={f.user.has_photo ? publicPhoto(f.user_id) : null} />
              <View style={{ flex: 1 }}>
                <T weight="700">{f.user.name}</T>
                <T size={12} color={colors.muted}>{f.services.map((s: string) => SERVICE_LABEL[s]).join(" · ")} · {f.home?.subdistrict_name ?? ""}</T>
              </View>
              <Ionicons name="heart" size={18} color={colors.error} />
            </Card>
          ))}
        </View>
      ) : null}
    </View>
  );
}

export default function HireScreen() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t } = useI18n();
  const router = useRouter();
  const toast = useToast();
  const [service, setService] = useState<"rent" | "book" | null>(null);
  const [favs, setFavs] = useState<any[]>([]);
  const [pickup, setPickup] = useState<Loc | null>(null);
  const [dest, setDest] = useState<Loc | null>(null);
  const [date, setDate] = useState<string | null>(isoDate(new Date(Date.now() + 86400000)));
  const [time, setTime] = useState("09:00");
  const [stype, setStype] = useState("hourly");
  const [hours, setHours] = useState(4);
  const [days, setDays] = useState(2);
  const [vtype, setVtype] = useState("");
  const [vdesc, setVdesc] = useState("");
  const [passengers, setPassengers] = useState(1);
  const [notes, setNotes] = useState("");
  const [rows, setRows] = useState<any[] | null>(null);
  const [nearby, setNearby] = useState<{ rows: any[]; scope: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [sending, setSending] = useState("");
  const [err, setErr] = useState("");
  const [changeTaluk, setChangeTaluk] = useState(false);
  const [manual, setManual] = useState<HomeLoc>(emptyLoc);
  const dt = useTaluk(dest);
  const pt = useTaluk(pickup);

  useFocusEffect(useCallback(() => { api("/hire/favourites").then(setFavs).catch(() => {}); }, []));
  useEffect(() => { setRows(null); setNearby(null); }, [service, dest?.loc_id, dt.taluk?.code, stype, date, time, hours, days, vtype, passengers]);
  useEffect(() => { setChangeTaluk(!!dest && !dt.busy && !dt.taluk); }, [dest, dt.busy, dt.taluk]);
  const pick = (s: "rent" | "book") => { setService(s); setStype(s === "rent" ? "hourly" : "one_way"); setVtype(s === "rent" ? "" : "sedan"); setErr(""); };

  const multi = stype === "multi_day" || stype === "outstation";
  const params = () => {
    const q = new URLSearchParams({ subdistrict_code: dt.taluk!.code, date: date!, time, service: service!, service_type: stype, hours: String(hours), days: String(days), vehicle_type: vtype, passengers: String(passengers) });
    if (pt.taluk) q.set("pickup_subdistrict_code", pt.taluk.code);
    return q;
  };
  const find = async () => {
    if (!pickup || !dest) return setErr("Enter pickup location and destination");
    if (!date) return setErr("Choose a travel date");
    if (!dt.taluk) return setErr("Choose the destination taluk / sub-district");
    if (service === "book" && !vtype) return setErr("Choose a vehicle category");
    setErr("");
    setBusy(true);
    try {
      const r = await api(`/hire/local-drivers?${params()}`);
      setRows(r.local);
    } catch (e: any) { setErr(e.message); }
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
  const send = async (key: string, extra: { include_nearby?: boolean; driver_id?: string }) => {
    setSending(key);
    try {
      const r = await api("/hire/requests", { body: { service, service_type: stype, date, time, hours, days, city: locPayload(pickup!), pickup: pickup!.name, destination: dest!.name, passengers, vehicle_type: vtype, vehicle_desc: vdesc.trim(), notes: notes.trim(), subdistrict_code: dt.taluk!.code, pickup_subdistrict_code: pt.taluk?.code ?? null, taluk_method: dt.method || "manual", ...extra } });
      toast(`Request sent to ${r.notified} driver${r.notified > 1 ? "s" : ""}`);
      router.push("/hire/requests");
    } catch (e: any) { setErr(e.message); toast(e.message, "error"); }
    setSending("");
  };
  const toggleFav = async (id: string) => {
    try {
      const r = await api(`/hire/favourites/${id}`, { method: "POST" });
      const upd = (l: any[]) => l.map((d) => (d.user_id === id ? { ...d, favourite: r.favourite } : d));
      setRows((l) => (l ? upd(l) : l));
      setNearby((n) => (n ? { ...n, rows: upd(n.rows) } : n));
      api("/hire/favourites").then(setFavs).catch(() => {});
    } catch (e: any) { toast(e.message, "error"); }
  };

  const opts = service === "book" ? BOOK_OPTIONS : RENT_OPTIONS;
  const form = !service ? <ServiceChooser onPick={pick} favs={favs} /> : (
    <View style={{ gap: space.md }}>
      <View style={{ flexDirection: "row", gap: space.sm }}>
        {(["rent", "book"] as const).map((s) => <Chip key={s} testID={`hire-service-tab-${s}`} label={SERVICE_LABEL[s]} active={service === s} onPress={() => pick(s)} />)}
      </View>
      <T size={13} color={colors.muted}>{service === "rent" ? "I have a car. I need a driver." : "I need a car and a driver."}</T>
      <Card style={{ gap: 0, paddingVertical: space.sm }}>
        <LocationField testID="hire-pickup-field" label={t("v2.pickup_loc")} value={pickup} onChange={setPickup} icon="location-outline" />
        <LocationField testID="hire-destination-field" label="Destination" value={dest} onChange={setDest} icon="navigate-outline" />
        <DateField testID="hire-date" label="Travel date" value={date} onChange={setDate} />
      </Card>
      {dest ? (
        <Card testID="hire-dest-taluk-card" style={{ gap: space.xs }}>
          <T size={12} color={colors.muted}>Destination taluk (drivers are matched for this area)</T>
          {dt.busy ? <T testID="hire-taluk-identifying" color={colors.muted}>Identifying taluk…</T> : dt.taluk ? (
            <T testID="hire-dest-taluk" weight="800">{dt.taluk.name} {dt.taluk.sub_label ?? ""} · {dt.taluk.district_name}, {dt.taluk.state_name}</T>
          ) : <T testID="hire-taluk-unmatched" color={colors.brandTertiary} weight="600">We could not identify the destination taluk. Please choose it below.</T>}
          {pickup ? <T testID="hire-pickup-taluk" size={12} color={colors.muted}>Pickup: {pickup.name}{pt.taluk ? ` · ${pt.taluk.name} ${pt.taluk.sub_label ?? ""}` : ""}</T> : null}
          {changeTaluk ? <TalukPicker testPrefix="hire-taluk" value={manual} onChange={(v) => { setManual(v); if (v.taluk) dt.setTaluk(v.taluk); }} /> : (
            <Btn small variant="ghost" testID="hire-change-taluk" label="Change destination taluk" onPress={() => setChangeTaluk(true)} style={{ alignSelf: "flex-start" }} />
          )}
        </Card>
      ) : null}
      <T size={13} weight="600" color={colors.muted}>{service === "rent" ? "Booking option" : "Trip type"}</T>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm }}>
        {opts.map(([k, l]) => <Chip key={k} testID={`hire-type-${k}`} label={l} active={stype === k} onPress={() => setStype(k)} />)}
      </ScrollView>
      <T size={13} weight="600" color={colors.muted}>{t("v2.start_time")}: {time}</T>
      <TimeChips value={time} onChange={setTime} />
      {multi ? (
        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
          <T weight="600">Number of days</T>
          <Stepper testID="hire-days" value={days} max={30} onChange={setDays} />
        </View>
      ) : ["hourly", "one_way"].includes(stype) ? (
        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
          <T weight="600">{stype === "one_way" ? "Estimated trip hours" : "Duration (hours)"}</T>
          <Stepper testID="hire-hours" value={hours} max={24} onChange={setHours} />
        </View>
      ) : null}
      {service === "book" ? (
        <>
          <T size={13} weight="600" color={colors.muted}>Vehicle category</T>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm }}>
            {[...VEHICLE_CATS, "any"].map((v) => <Chip key={v} testID={`hire-vcat-${v}`} label={v === "any" ? "ANY" : v.toUpperCase()} active={vtype === v} onPress={() => setVtype(v)} />)}
          </ScrollView>
        </>
      ) : (
        <>
          <T size={13} weight="600" color={colors.muted}>Your vehicle type (optional)</T>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm }}>
            {RENT_VTYPES.map((v) => <Chip key={v} testID={`hire-vtype-${v}`} label={v.toUpperCase()} active={vtype === v} onPress={() => setVtype(vtype === v ? "" : v)} />)}
          </ScrollView>
          <Field testID="hire-vehicle-desc" label="Your car (optional)" value={vdesc} onChangeText={setVdesc} placeholder="Honda City, automatic" />
        </>
      )}
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
        <T weight="600">{t("search.passengers")}</T>
        <Stepper testID="hire-passengers" value={passengers} max={service === "book" ? 20 : 8} onChange={setPassengers} />
      </View>
      <Field testID="hire-notes" label={service === "rent" ? "Additional instructions" : "Additional requirements"} value={notes} onChangeText={setNotes} multiline maxLength={500} />
      {err ? <T testID="hire-error" color={colors.error}>{err}</T> : null}
      <Btn testID="hire-find-button" icon="search" label={t("v2.find_drivers")} onPress={find} loading={busy && !rows} />
      <T size={12} color={colors.muted}>{feeNote(service)}</T>
      {rows ? (
        <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm, marginTop: space.sm }}>
          <Ionicons name="location" size={18} color={colors.brandPrimary} />
          <T testID="hire-local-heading" size={16} weight="800" style={{ flex: 1 }}>DRIVERS FOR {dt.taluk?.name?.toUpperCase()} ({rows.length})</T>
        </View>
      ) : null}
      {rows && rows.length ? <Btn testID="hire-broadcast-button" variant="outline" icon="megaphone-outline" label={`Send request to all ${rows.length} driver${rows.length > 1 ? "s" : ""}`} loading={sending === "all"} onPress={() => send("all", { include_nearby: false })} /> : null}
    </View>
  );

  const card = (item: any) => {
    const [gl, gt] = GROUP[item.group] ?? GROUP.nearby;
    return (
      <Card key={item.user_id} testID={`hire-driver-${item.user_id}`} style={{ gap: space.sm }}>
        <Pressable onPress={() => router.push(`/user/${item.user_id}`)} style={{ flexDirection: "row", gap: space.md, alignItems: "center" }}>
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
        </Pressable>
        <View style={{ flexDirection: "row", gap: space.sm, flexWrap: "wrap" }}>
          <Badge testID={`hire-driver-group-${item.user_id}`} icon="location" label={gl} tone={gt} />
          <Badge label={`Home: ${item.home?.subdistrict_name}`} tone="muted" />
          {item.match_vehicle ? <Badge testID={`hire-driver-vehicle-${item.user_id}`} icon="car-outline" label={`${item.match_vehicle.name} · ${item.match_vehicle.category.toUpperCase()} · ${item.match_vehicle.seats} seats`} tone="info" /> : null}
          {item.accepts_outstation ? <Badge label="Outstation OK" tone="muted" /> : null}
        </View>
        <View style={{ flexDirection: "row", gap: space.sm }}>
          <Btn small style={{ flex: 1 }} icon="send" testID={`hire-request-driver-${item.user_id}`} label="Request this driver" loading={sending === item.user_id} onPress={() => send(item.user_id, { driver_id: item.user_id })} />
          <Btn small variant="outline" icon={item.favourite ? "heart" : "heart-outline"} testID={`hire-fav-toggle-${item.user_id}`} label="" onPress={() => toggleFav(item.user_id)} />
        </View>
      </Card>
    );
  };

  const footer = rows ? (
    <View style={{ gap: space.md }}>
      {!nearby ? (
        <Btn testID="hire-nearby-button" variant={rows.length ? "ghost" : "outline"} icon="git-network-outline" label="Search nearby areas too" loading={busy && !!rows} onPress={findNearby} />
      ) : (
        <>
          <T testID="hire-nearby-heading" size={16} weight="800">NEARBY-AREA DRIVERS ({nearby.rows.length})</T>
          <T size={12} color={colors.muted}>{nearby.scope}.</T>
          {nearby.rows.length ? nearby.rows.map(card) : <Empty icon="person-outline" title="No eligible drivers in nearby areas either" />}
          {nearby.rows.length ? <Btn testID="hire-broadcast-nearby-button" variant="outline" icon="megaphone-outline" label="Send request to all + nearby drivers" loading={sending === "nearby"} onPress={() => send("nearby", { include_nearby: true })} /> : null}
        </>
      )}
    </View>
  ) : null;

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title={service ? SERVICE_LABEL[service] : t("v2.hire_title")} right={
        <View style={{ flexDirection: "row" }}>
          <Btn small variant="ghost" icon="mail-unread-outline" label="" onPress={() => router.push("/hire/requests")} testID="hire-requests-link" />
          <Btn small variant="ghost" icon="briefcase-outline" label="" onPress={() => router.push("/hire/driver")} testID="hire-driver-dashboard-link" />
        </View>} />
      <FlatList
        data={rows ?? []}
        keyExtractor={(d) => d.user_id}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{ padding: space.lg, gap: space.md, paddingBottom: insets.bottom + space.xl }}
        ListHeaderComponent={form}
        ListFooterComponent={footer ?? undefined}
        ListEmptyComponent={busy && !rows ? <Loading /> : rows ? <Empty icon="person-outline" title={`No eligible ${service ? SERVICE_LABEL[service] : ""} drivers for ${dt.taluk?.name ?? "this taluk"} right now`} /> : undefined}
        renderItem={({ item }) => card(item)}
      />
    </View>
  );
}

