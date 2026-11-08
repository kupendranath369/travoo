import { useFocusEffect } from "expo-router";
import React, { useCallback, useState } from "react";
import { ScrollView, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Loc, locPayload } from "@/src/api";
import { useAuth } from "@/src/auth";
import { TimeChips } from "@/src/components/DateChips";
import { DocPhotos } from "@/src/components/DocPhotos";
import { LocationField } from "@/src/components/LocationField";
import { useToast } from "@/src/components/toast";
import { Badge, Btn, Card, Chip, Field, Header, Loading, Stepper, T, space, statusTone } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

const VTYPES = ["hatchback", "sedan", "suv", "muv", "luxury", "automatic", "ev"];
const LANGS = ["Hindi", "English", "Tamil", "Telugu", "Kannada", "Marathi", "Bengali", "Malayalam", "Gujarati", "Punjabi", "Odia", "Urdu", "Assamese"];

export default function ProRegister() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t } = useI18n();
  const { user } = useAuth();
  const toast = useToast();
  const [me, setMe] = useState<any>(null);
  const [city, setCity] = useState<Loc | null>(null);
  const [f, setF] = useState({ areas: "", licence_no: "", licence_expiry: "", bio: user?.bio ?? "", rate_hourly: "", rate_half_day: "", rate_full_day: "", rate_one_way: "" });
  const [langs, setLangs] = useState<string[]>([]);
  const [vt, setVt] = useState<string[]>(["sedan"]);
  const [days, setDays] = useState<number[]>([0, 1, 2, 3, 4, 5]);
  const [exp, setExp] = useState(3);
  const [from, setFrom] = useState("08:00");
  const [to, setTo] = useState("20:00");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (v: string) => setF({ ...f, [k]: k.startsWith("rate") ? v.replace(/\D/g, "") : v });
  const toggle = <X,>(arr: X[], x: X, fn: (a: X[]) => void) => fn(arr.includes(x) ? arr.filter((y) => y !== x) : [...arr, x]);
  const load = useCallback(() => api("/pro/me").then(setMe).catch((e) => setErr(e.message)), []);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  if (!me) return <View style={{ flex: 1 }}><Header title={t("v2.local_register")} /><Loading /></View>;
  const status = me.profile?.status;
  const locked = status === "under_review" || status === "approved";
  const dayNames = t("v2.days").split(",");

  const submit = async () => {
    setErr("");
    if (!city) return setErr(`${t("v2.city")} *`);
    if (!langs.length) return setErr(`${t("v2.languages")} *`);
    if (f.bio.trim().length < 20) return setErr(`${t("v2.about_me")} * (20+)`);
    if (!f.rate_hourly || !f.rate_half_day || !f.rate_full_day) return setErr(`${t("v2.rate_hourly")} *`);
    setBusy(true);
    try {
      const r = await api("/pro/register", { body: { city: locPayload(city), areas: f.areas.split(",").map((x) => x.trim()).filter(Boolean), languages: langs, experience_years: exp, licence_no: f.licence_no.replace(/\s/g, ""), licence_expiry: f.licence_expiry, vehicle_types: vt, days, start_time: from, end_time: to, bio: f.bio.trim(), rate_hourly: Number(f.rate_hourly), rate_half_day: Number(f.rate_half_day), rate_full_day: Number(f.rate_full_day), rate_one_way: f.rate_one_way ? Number(f.rate_one_way) : null } });
      toast(t(`verify.status.${r.status}`));
      load();
    } catch (e: any) {
      setErr(e.message);
    }
    setBusy(false);
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title={t("v2.local_register")} />
      <KeyboardAwareScrollView bottomOffset={24} keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: space.lg, gap: space.md, paddingBottom: insets.bottom + space.xl }}>
        <Card style={{ gap: space.xs }}>
          <T weight="800">{t("v2.local_status")}</T>
          <Badge testID="pro-status" label={t(`verify.status.${status ?? "not_submitted"}`)} tone={statusTone(status ?? "")} />
          <T size={12} color={colors.muted}>{user?.name} · {user?.email} · {user?.phone || "—"}</T>
        </Card>
        <T weight="800">{t("verify.photos")}</T>
        <DocPhotos photos={me.photos} editable={!locked && user?.driver_status !== "under_review" && user?.driver_status !== "approved"} onUploaded={load} />
        {locked ? (
          <Card style={{ gap: 4 }}>
            <T weight="700">{me.profile.city?.name} · {t("v2.years", { n: me.profile.experience_years })}</T>
            <T size={13}>{me.profile.bio}</T>
            <T size={12} color={colors.muted}>{me.profile.languages.join(", ")} · ₹{me.profile.rate_hourly}/h</T>
          </Card>
        ) : (
          <>
            <Card style={{ paddingVertical: space.xs }}><LocationField testID="pro-city-field" label={t("v2.city")} value={city} onChange={setCity} icon="business-outline" /></Card>
            <Field testID="pro-areas-input" label={t("v2.areas")} value={f.areas} onChangeText={set("areas")} />
            <T size={13} weight="600" color={colors.muted}>{t("v2.languages")}</T>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>{LANGS.map((l) => <Chip key={l} testID={`pro-lang-${l}`} label={l} active={langs.includes(l)} onPress={() => toggle(langs, l, setLangs)} />)}</View>
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
              <T weight="600">{t("v2.experience")}: {t("v2.years", { n: exp })}</T>
              <Stepper testID="pro-exp" value={exp} max={50} onChange={setExp} />
            </View>
            <Field testID="pro-licence-input" label={t("verify.licence")} value={f.licence_no} onChangeText={(v) => set("licence_no")(v.toUpperCase())} autoCapitalize="characters" />
            <Field testID="pro-licence-exp-input" label={t("verify.licence_exp")} value={f.licence_expiry} onChangeText={set("licence_expiry")} placeholder="31-12-2035" maxLength={10} />
            <T size={13} weight="600" color={colors.muted}>{t("v2.vehicle_types")}</T>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>{VTYPES.map((v) => <Chip key={v} testID={`pro-vt-${v}`} label={v.toUpperCase()} active={vt.includes(v)} onPress={() => toggle(vt, v, setVt)} />)}</View>
            <T size={13} weight="600" color={colors.muted}>{t("v2.availability")}</T>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm }}>{dayNames.map((d, i) => <Chip key={d} testID={`pro-day-${i}`} label={d} active={days.includes(i)} onPress={() => toggle(days, i, setDays)} />)}</ScrollView>
            <T size={13} weight="600" color={colors.muted}>{t("v2.from_time")}: {from}</T>
            <TimeChips value={from} onChange={setFrom} />
            <T size={13} weight="600" color={colors.muted}>{t("v2.to_time")}: {to}</T>
            <TimeChips value={to} onChange={setTo} />
            <Field testID="pro-bio-input" label={`${t("v2.about_me")} (${f.bio.length}/500)`} value={f.bio} onChangeText={set("bio")} multiline maxLength={500} placeholder={t("v2.about_me_ph")} />
            <Field testID="pro-rate-hourly" label={t("v2.rate_hourly")} value={f.rate_hourly} onChangeText={set("rate_hourly")} keyboardType="number-pad" />
            <Field testID="pro-rate-half" label={t("v2.rate_half")} value={f.rate_half_day} onChangeText={set("rate_half_day")} keyboardType="number-pad" />
            <Field testID="pro-rate-full" label={t("v2.rate_full")} value={f.rate_full_day} onChangeText={set("rate_full_day")} keyboardType="number-pad" />
            <Field testID="pro-rate-oneway" label={t("v2.rate_one_way")} value={f.rate_one_way} onChangeText={set("rate_one_way")} keyboardType="number-pad" />
            {err ? <T testID="pro-error" color={colors.error}>{err}</T> : null}
            <Btn testID="pro-submit-button" label={t("verify.submit")} onPress={submit} loading={busy} />
          </>
        )}
      </KeyboardAwareScrollView>
    </View>
  );
}
