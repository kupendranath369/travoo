import Ionicons from "@react-native-vector-icons/ionicons";
import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useEffect, useState } from "react";
import { ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, publicPhoto } from "@/src/api";
import { useToast } from "@/src/components/toast";
import { Avatar, Badge, Btn, Card, ErrorBox, Header, Loading, Rating, Section, T, space } from "@/src/components/ui";
import { inr, useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

export default function DriverProfile() {
  const { id, hire } = useLocalSearchParams<{ id: string; hire?: string }>();
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t, fmtDate } = useI18n();
  const router = useRouter();
  const toast = useToast();
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const req = hire ? JSON.parse(hire) : null;

  useEffect(() => { api(`/users/${id}/profile`).then(setD).catch((e) => setErr(e.message)); }, [id]);
  if (err) return <View style={{ flex: 1 }}><Header title={t("v2.view_profile")} /><ErrorBox message={err} /></View>;
  if (!d) return <View style={{ flex: 1 }}><Header title={t("v2.view_profile")} /><Loading /></View>;
  const u = d.user;

  const send = async () => {
    setBusy(true);
    try {
      const { estimate, ...body } = req;
      const r = await api("/hire/bookings", { body });
      toast(t("v2.hire_sent"));
      router.replace(`/hire/${r.booking_id}`);
    } catch (e: any) {
      toast(e.message, "error");
    }
    setBusy(false);
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title={t("v2.view_profile")} />
      <ScrollView contentContainerStyle={{ padding: space.lg, gap: space.lg, paddingBottom: insets.bottom + space.xl }}>
        <Card style={{ alignItems: "center", gap: space.sm }}>
          <Avatar name={u.name} uri={u.has_photo ? publicPhoto(u.user_id) : u.picture} size={96} />
          <View style={{ flexDirection: "row", gap: 6, alignItems: "center" }}>
            <T testID="profile-driver-name" size={20} weight="800">{u.name}</T>
            {d.verified ? <Ionicons name="shield-checkmark" size={18} color={colors.success} /> : null}
          </View>
          <View style={{ flexDirection: "row", gap: space.sm }}>
            {d.verified ? <Badge label={t("ride.verified")} tone="success" /> : null}
            {u.has_photo ? <Badge icon="camera" label={t("v2.verified_photo")} tone="info" /> : null}
          </View>
          <Rating value={u.rating_avg} count={u.rating_count} />
          <T size={12} color={colors.muted}>{t("v2.completed_journeys")}: {d.completed_journeys}</T>
        </Card>
        <Section title={t("v2.about_me")}>
          <T testID="profile-bio">{d.pro?.bio || u.bio || "—"}</T>
        </Section>
        {d.pro ? (
          <Card style={{ gap: 4 }}>
            <T size={13}>{t("v2.city")}: <T weight="700" size={13}>{d.pro.city?.name}</T></T>
            <T size={13}>{t("v2.languages")}: {d.pro.languages.join(", ")}</T>
            <T size={13}>{t("v2.experience")}: {t("v2.years", { n: d.pro.experience_years })}</T>
            <T size={13}>{t("v2.vehicle_types")}: {d.pro.vehicle_types.join(", ").toUpperCase()}</T>
            <T size={13}>₹{d.pro.rate_hourly}/h · ₹{d.pro.rate_half_day} (4h) · ₹{d.pro.rate_full_day} (8h)</T>
          </Card>
        ) : null}
        {d.vehicles.length ? <Section title={t("trip.vehicle")}>{d.vehicles.map((v: any, i: number) => <T key={i}>{v.make} {v.model} · {v.vtype} {v.verified ? "✓" : ""}</T>)}</Section> : null}
        <Section title={t("v2.reviews")}>
          {d.reviews.length === 0 ? <T color={colors.muted}>{t("v2.no_reviews")}</T> : null}
          {d.reviews.map((r: any) => (
            <Card key={r.review_id} style={{ gap: 2, padding: space.md }}>
              <T weight="700">{"★".repeat(r.rating)} · {r.reviewer_name}</T>
              {r.comment ? <T size={13}>{r.comment}</T> : null}
              <T size={11} color={colors.muted}>{fmtDate(r.created_at)}</T>
            </Card>
          ))}
        </Section>
        {req && d.pro ? (
          <Card style={{ gap: space.sm, borderColor: colors.brandPrimary }}>
            <T weight="800">{t(`v2.svc.${req.service_type}`)} · {fmtDate(req.date)} {req.time} · {req.hours}h</T>
            <T size={13}>{req.pickup}{req.destination ? ` → ${req.destination}` : ""} · {req.vehicle_desc}</T>
            <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
              <T weight="700">{t("v2.est_charge")}</T>
              <T testID="hire-request-estimate" size={20} weight="800" color={colors.brandPrimary}>{inr(req.estimate)}</T>
            </View>
            <T size={12} color={colors.muted}>{t("v2.service_fee_note")}</T>
            <Btn testID="hire-send-request-button" icon="send" label={t("v2.request_driver")} onPress={send} loading={busy} />
          </Card>
        ) : null}
      </ScrollView>
    </View>
  );
}
