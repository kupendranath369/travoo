import Ionicons from "@react-native-vector-icons/ionicons";
import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useEffect, useState } from "react";
import { FlatList, ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Loc, locPayload, publicPhoto } from "@/src/api";
import { DateField } from "@/src/components/Calendar";
import { isoDate, TimeChips } from "@/src/components/DateChips";
import { LocationField } from "@/src/components/LocationField";
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

  useEffect(() => { if (service === "half_day") setHours(4); if (service === "full_day") setHours(8); }, [service]);

  const find = async () => {
    if (!city || !date) return setErr(`${t("v2.city")} *`);
    if (!pickup || !vdesc.trim()) return setErr(`${t("v2.pickup_loc")} / ${t("v2.your_vehicle")} *`);
    setErr("");
    setBusy(true);
    try {
      const q = new URLSearchParams({ lat: String(city.lat), lng: String(city.lng), date, service, hours: String(hours), vehicle_type: vtype, min_exp: String(minExp) });
      if (lang) q.set("language", lang);
      setRows(await api(`/hire/drivers?${q}`));
      api("/searches", { body: { kind: "hire", origin: locPayload(city), date, service } }).catch(() => {});
    } catch (e: any) {
      setErr(e.message);
    }
    setBusy(false);
  };

  const request = (d: any) => router.push({ pathname: "/user/[id]", params: { id: d.user_id, hire: JSON.stringify({ driver_id: d.user_id, service_type: service, date, time, hours, city: locPayload(city!), pickup: locPayload(pickup!), destination: dest ? locPayload(dest) : null, vehicle_type: vtype, vehicle_desc: vdesc.trim(), estimate: d.estimate }) } });

  const form = (
    <View style={{ gap: space.md }}>
      <Card style={{ gap: 0, paddingVertical: space.sm }}>
        <LocationField testID="hire-city-field" label={t("v2.city")} value={city} onChange={setCity} icon="business-outline" />
        <DateField testID="hire-date" label={t("search.date")} value={date} onChange={setDate} />
      </Card>
      <LocationField testID="hire-pickup-field" label={t("v2.pickup_loc")} value={pickup} onChange={setPickup} icon="location-outline" />
      <LocationField testID="hire-destination-field" label={t("v2.destination_opt")} value={dest} onChange={setDest} icon="navigate-outline" />
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
    </View>
  );

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title={t("v2.hire_title")} right={<Btn small variant="ghost" icon="briefcase-outline" label="" onPress={() => router.push("/hire/register")} testID="hire-register-link" />} />
      <FlatList
        data={rows ?? []}
        keyExtractor={(d) => d.user_id}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{ padding: space.lg, gap: space.md, paddingBottom: insets.bottom + space.xl }}
        ListHeaderComponent={form}
        ListEmptyComponent={busy ? <Loading /> : rows ? <Empty icon="person-outline" title={t("v2.no_drivers")} /> : undefined}
        renderItem={({ item }) => (
          <Card testID={`hire-driver-${item.user_id}`} onPress={() => request(item)} style={{ gap: space.sm }}>
            <View style={{ flexDirection: "row", gap: space.md, alignItems: "center" }}>
              <Avatar name={item.user.name} uri={item.user.has_photo ? publicPhoto(item.user_id) : item.user.picture} size={52} />
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
            <T size={13} numberOfLines={2} color={colors.muted}>{item.bio}</T>
            <View style={{ flexDirection: "row", gap: space.sm, flexWrap: "wrap" }}>
              {item.has_photo || item.user.has_photo ? <Badge icon="camera" label={t("v2.verified_photo")} tone="success" /> : null}
              <Badge label={`${inr(item.rate_hourly)}/h`} tone="muted" />
              <Badge label={item.city?.name} tone="info" />
            </View>
          </Card>
        )}
      />
    </View>
  );
}
