import Ionicons from "@react-native-vector-icons/ionicons";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { Linking, Pressable, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, publicPhoto } from "@/src/api";
import { confirmAction, feeNote, SERVICE_LABEL, TYPE_LABEL } from "@/src/components/LocalDriverParts";
import { useToast } from "@/src/components/toast";
import { Avatar, Badge, Btn, Card, ErrorBox, Field, Header, Loading, T, space, statusTone } from "@/src/components/ui";
import { inr, useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

function Contact({ label, u, photo, bid, status }: { label: string; u: any; photo?: string; bid: string; status: string }) {
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
      {u.phone_masked && ["pending", "confirmed"].includes(status) ? <T size={12} color={colors.muted}>{t("v2.contact_hidden")}</T> : null}
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
  const [reporting, setReporting] = useState(false);
  const [report, setReport] = useState("");
  const load = useCallback(() => api(`/hire/bookings/${id}`).then(setH).catch((e) => setErr(e.message)), [id]);
  useFocusEffect(useCallback(() => { load(); }, [load]));
  if (err) return <View style={{ flex: 1 }}><Header title={t("v2.hire")} /><ErrorBox message={err} onRetry={load} /></View>;
  if (!h) return <View style={{ flex: 1 }}><Header title={t("v2.hire")} /><Loading /></View>;

  const act = async (a: string, path = `/hire/bookings/${id}/${a}`, body: any = {}) => {
    setBusy(a);
    try { await api(path, { body }); toast(a === "accept" ? t("status.confirmed") : a === "rev" ? t("booking.reviewed") : a === "arriving" ? "Customer notified you're arriving" : a === "fav" ? "Favourites updated" : a === "report" ? "Report sent to Travoo support" : t(`status.${({ reject: "rejected", start: "started", complete: "completed", cancel: "cancelled" } as any)[a] ?? "confirmed"}`)); await load(); } catch (e: any) { toast(e.message, "error"); }
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
          <Badge icon="key" label={`${SERVICE_LABEL[h.service ?? "rent"].toUpperCase()} · ${TYPE_LABEL[h.service_type] ?? h.service_type}${h.days > 1 ? ` · ${h.days} days` : ""}`} tone="info" />
          <T weight="700">{fmtDate(h.date, { weekday: "long", day: "numeric", month: "long" })} · {h.time} · {h.hours}h</T>
          <T size={13}>Pickup: {h.pickup}{h.pickup_taluk ? ` (${h.pickup_taluk.name})` : ""}</T>
          {h.destination ? <T size={13}>Destination: {h.destination}{h.dest_taluk ? ` (${h.dest_taluk.name} ${h.dest_taluk.sub_label ?? ""})` : ""}</T> : null}
          {h.vehicle ? <T testID="hire-booking-vehicle" size={13}>Vehicle provided: {h.vehicle.name} · {h.vehicle.reg_no} · {h.vehicle.category.toUpperCase()} · {h.vehicle.seats} seats</T>
            : h.vehicle_desc || h.vehicle_type ? <T size={13}>{t("v2.your_vehicle")}: {h.vehicle_desc || "—"}{h.vehicle_type ? ` (${h.vehicle_type})` : ""}</T> : null}
          {h.notes ? <T size={12} color={colors.muted}>Notes: {h.notes}</T> : null}
          {h.arriving_at && h.status === "confirmed" ? <Badge testID="hire-arriving-badge" icon="navigate" label="Driver is arriving" tone="success" /> : null}
          <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
            <T weight="700">{t("v2.est_charge")}</T>
            <T size={20} weight="800" color={colors.brandPrimary}>{inr(h.service_fee)}</T>
          </View>
          <T size={12} color={colors.muted}>{feeNote(h.service)}</T>
        </Card>
        <Contact label={h.is_driver ? t("v2.customer") : t("trip.driver")} u={other} photo={!h.is_driver && h.driver.has_photo ? publicPhoto(h.driver_id) : undefined} bid={h.booking_id} status={h.status} />
        {h.is_driver && h.status === "pending" ? (
          <View style={{ flexDirection: "row", gap: space.sm }}>
            <Btn style={{ flex: 1 }} testID="hire-accept-button" label={t("trip.accept")} loading={busy === "accept"} onPress={() => act("accept")} />
            <Btn style={{ flex: 1 }} variant="outline" testID="hire-reject-button" label={t("trip.reject")} loading={busy === "reject"} onPress={() => act("reject")} />
          </View>
        ) : null}
        {h.is_driver && h.status === "confirmed" && !h.arriving_at ? <Btn testID="hire-arriving-button" variant="outline" icon="navigate-outline" label="I am arriving" loading={busy === "arriving"} onPress={() => act("arriving")} /> : null}
        {h.is_driver && h.status === "confirmed" ? <Btn testID="hire-start-button" icon="play" label={t("trip.start")} loading={busy === "start"} onPress={() => act("start")} /> : null}
        {h.is_driver && h.status === "started" ? <Btn testID="hire-complete-button" variant="navy" icon="flag" label={t("trip.complete")} loading={busy === "complete"} onPress={() => act("complete")} /> : null}
        {["pending", "confirmed"].includes(h.status) ? <Btn testID="hire-cancel-button" variant="ghost" label={t("booking.cancel")} onPress={() => confirmAction("Cancel this booking?", "The other person will be notified.", () => act("cancel", undefined, { reason: "Cancelled" }))} /> : null}
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
        {!h.is_driver ? <Btn testID="hire-fav-button" variant="outline" icon={h.favourite ? "heart" : "heart-outline"} label={h.favourite ? "Favourite driver" : "Add to favourite drivers"} loading={busy === "fav"} onPress={() => act("fav", `/hire/favourites/${h.driver_id}`)} /> : null}
        {reporting ? (
          <Card style={{ gap: space.sm }}>
            <T weight="800">Report a problem</T>
            <Field testID="hire-report-input" placeholder="Describe what happened" value={report} onChangeText={setReport} multiline maxLength={2000} />
            <Btn testID="hire-report-submit" label="Send report" disabled={report.trim().length < 5} loading={busy === "report"}
              onPress={async () => { await act("report", "/tickets", { type: h.is_driver ? "complaint" : "report_user", subject: `${h.is_driver ? "Customer" : "Driver"} report · ${h.booking_id}`, message: report.trim(), booking_id: h.booking_id, reported_user_id: other.user_id }); setReporting(false); setReport(""); }} />
          </Card>
        ) : <Btn testID="hire-report-button" variant="ghost" icon="flag-outline" label={h.is_driver ? "Report customer" : "Report driver"} onPress={() => setReporting(true)} />}
      </KeyboardAwareScrollView>
    </View>
  );
}
