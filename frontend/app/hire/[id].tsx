import Ionicons from "@react-native-vector-icons/ionicons";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { Linking, Pressable, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, publicPhoto } from "@/src/api";
import { useToast } from "@/src/components/toast";
import { Avatar, Badge, Btn, Card, ErrorBox, Field, Header, Loading, T, space, statusTone } from "@/src/components/ui";
import { inr, useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

function Contact({ label, u, photo, bid }: { label: string; u: any; photo?: string; bid: string }) {
  const { colors } = useTheme();
  const { t } = useI18n();
  const router = useRouter();
  return (
    <Card style={{ gap: space.sm }}>
      <View style={{ flexDirection: "row", gap: space.md, alignItems: "center" }}>
        <Avatar name={u.name} uri={photo ?? u.picture} />
        <View style={{ flex: 1 }}>
          <T size={12} color={colors.muted}>{label}</T>
          <T weight="800">{u.name}</T>
          <T testID={`contact-phone-${u.user_id}`} size={13}>{u.phone || "—"}</T>
        </View>
      </View>
      {u.phone_masked ? <T size={12} color={colors.muted}>{t("v2.contact_hidden")}</T> : null}
      <View style={{ flexDirection: "row", gap: space.sm }}>
        <Btn small style={{ flex: 1 }} icon="chatbubbles-outline" label={t("v2.chat_with")} onPress={() => router.push(`/chat/${bid}`)} testID={`chat-${u.user_id}`} />
        {!u.phone_masked && u.phone ? <Btn small style={{ flex: 1 }} variant="outline" icon="call-outline" label={t("v2.call")} onPress={() => Linking.openURL(`tel:${u.phone}`)} testID={`call-${u.user_id}`} /> : null}
      </View>
    </Card>
  );
}

export default function HireBooking() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t, fmtDate } = useI18n();
  const toast = useToast();
  const [h, setH] = useState<any>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState("");
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState("");
  const load = useCallback(() => api(`/hire/bookings/${id}`).then(setH).catch((e) => setErr(e.message)), [id]);
  useFocusEffect(useCallback(() => { load(); }, [load]));
  if (err) return <View style={{ flex: 1 }}><Header title={t("v2.hire")} /><ErrorBox message={err} onRetry={load} /></View>;
  if (!h) return <View style={{ flex: 1 }}><Header title={t("v2.hire")} /><Loading /></View>;

  const act = async (a: string, path = `/hire/bookings/${id}/${a}`, body: any = {}) => {
    setBusy(a);
    try { await api(path, { body }); toast(a === "accept" ? t("status.confirmed") : a === "rev" ? t("booking.reviewed") : t(`status.${({ reject: "rejected", start: "started", complete: "completed", cancel: "cancelled" } as any)[a] ?? "confirmed"}`)); await load(); } catch (e: any) { toast(e.message, "error"); }
    setBusy("");
  };
  const other = h.is_driver ? h.customer : h.driver;

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title={t("v2.hire")} />
      <KeyboardAwareScrollView bottomOffset={24} contentContainerStyle={{ padding: space.lg, gap: space.lg, paddingBottom: insets.bottom + space.xl }}>
        <Card style={{ gap: space.sm }}>
          <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
            <T testID="hire-booking-id" weight="800" size={18}>{h.booking_id}</T>
            <Badge testID="hire-booking-status" label={t(`status.${h.status}`)} tone={statusTone(h.status)} />
          </View>
          <Badge icon="key" label={`TRAVOO DRIVER · ${t(`v2.svc.${h.service_type}`)}`} tone="info" />
          <T weight="700">{fmtDate(h.date, { weekday: "long", day: "numeric", month: "long" })} · {h.time} · {h.hours}h</T>
          <T size={13}>{h.city?.name} · {h.pickup}{h.destination ? ` → ${h.destination}` : ""}</T>
          <T size={13}>{t("v2.your_vehicle")}: {h.vehicle_desc} ({h.vehicle_type})</T>
          <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
            <T weight="700">{t("v2.est_charge")}</T>
            <T size={20} weight="800" color={colors.brandPrimary}>{inr(h.service_fee)}</T>
          </View>
          <T size={12} color={colors.muted}>{t("v2.service_fee_note")}</T>
        </Card>
        <Contact label={h.is_driver ? t("v2.customer") : t("trip.driver")} u={other} photo={!h.is_driver && h.driver.has_photo ? publicPhoto(h.driver_id) : undefined} bid={h.booking_id} />
        {h.is_driver && h.status === "pending" ? (
          <View style={{ flexDirection: "row", gap: space.sm }}>
            <Btn style={{ flex: 1 }} testID="hire-accept-button" label={t("trip.accept")} loading={busy === "accept"} onPress={() => act("accept")} />
            <Btn style={{ flex: 1 }} variant="outline" testID="hire-reject-button" label={t("trip.reject")} loading={busy === "reject"} onPress={() => act("reject")} />
          </View>
        ) : null}
        {h.is_driver && h.status === "confirmed" ? <Btn testID="hire-start-button" icon="play" label={t("trip.start")} loading={busy === "start"} onPress={() => act("start")} /> : null}
        {h.is_driver && h.status === "started" ? <Btn testID="hire-complete-button" variant="navy" icon="flag" label={t("trip.complete")} loading={busy === "complete"} onPress={() => act("complete")} /> : null}
        {["pending", "confirmed"].includes(h.status) ? <Btn testID="hire-cancel-button" variant="ghost" label={t("booking.cancel")} onPress={() => act("cancel", undefined, { reason: "Cancelled" })} /> : null}
        {h.status === "completed" && !h.my_reviews.length ? (
          <Card style={{ gap: space.md }}>
            <T weight="800">{t("booking.rate")}</T>
            <View style={{ flexDirection: "row", gap: space.sm }}>
              {[1, 2, 3, 4, 5].map((n) => <Pressable key={n} testID={`hire-rate-${n}`} onPress={() => setRating(n)}><Ionicons name={n <= rating ? "star" : "star-outline"} size={30} color={colors.brandTertiary} /></Pressable>)}
            </View>
            <Field testID="hire-review-input" placeholder={t("booking.review_ph")} value={comment} onChangeText={setComment} multiline />
            <Btn testID="hire-review-submit" label={t("booking.submit")} loading={busy === "rev"} onPress={() => act("rev", "/reviews", { booking_id: h.booking_id, target_id: other.user_id, rating, comment })} />
          </Card>
        ) : h.my_reviews.length ? <Badge label={t("booking.reviewed")} tone="success" /> : null}
      </KeyboardAwareScrollView>
    </View>
  );
}
