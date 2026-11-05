import Ionicons from "@react-native-vector-icons/ionicons";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import React, { useCallback, useEffect, useState } from "react";
import { Linking, Pressable, Share, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { LogoMark } from "@/src/components/Logo";
import { useToast } from "@/src/components/toast";
import { Avatar, Badge, Btn, Card, Chip, ErrorBox, Field, Header, Loading, Rating, T, space, statusTone } from "@/src/components/ui";
import { inr, useI18n } from "@/src/i18n";
import { openRouteInMaps } from "@/src/maps";
import { useTheme } from "@/src/theme";

export default function BookingScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t, fmtDate } = useI18n();
  const router = useRouter();
  const toast = useToast();
  const [b, setB] = useState<any>(null);
  const [err, setErr] = useState("");
  const [reasons, setReasons] = useState<string[]>([]);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [refund, setRefund] = useState("");
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState("");
  const [actionErr, setActionErr] = useState("");

  const load = useCallback(async () => {
    try {
      setB(await api(`/bookings/${id}`));
      setErr("");
    } catch (e: any) {
      setErr(e.message);
    }
  }, [id]);
  useFocusEffect(useCallback(() => { load(); }, [load]));
  useEffect(() => { api("/settings").then((s) => setReasons(s.cancellation_reasons || [])).catch(() => {}); }, []);

  if (err) return <View style={{ flex: 1 }}><Header title={t("booking.confirmation")} /><ErrorBox message={err} onRetry={load} /></View>;
  if (!b) return <View style={{ flex: 1 }}><Header title={t("booking.confirmation")} /><Loading /></View>;
  const trip = b.trip;
  const active = ["confirmed", "started", "completed"].includes(b.status);
  const other = b.is_driver ? b.passenger : b.driver;

  const run = async (key: string, fn: () => Promise<any>, msg?: string) => {
    setBusy(key);
    setActionErr("");
    try {
      await fn();
      if (msg) toast(msg);
      await load();
    } catch (e: any) {
      setActionErr(e.message);
    }
    setBusy("");
  };

  const share = () =>
    Share.share({
      message: `Travoo trip ${b.booking_id}\n${b.route}\n${b.date} ${b.time} (from ${trip.pickup_point})\nDriver: ${b.driver.name}, ${trip.vehicle.make} ${trip.vehicle.model}\nStatus: ${b.status}`,
    });

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title={t("booking.confirmation")} />
      <KeyboardAwareScrollView bottomOffset={24} contentContainerStyle={{ padding: space.lg, gap: space.lg, paddingBottom: insets.bottom + space.xl }}>
        <Card testID="booking-confirmation-card" style={{ gap: space.md, borderColor: colors.brandPrimary }}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: space.md }}>
            <LogoMark size={40} />
            <View style={{ flex: 1 }}>
              <T size={12} color={colors.muted}>{t("booking.id")}</T>
              <T testID="booking-id" size={18} weight="800">{b.booking_id}</T>
            </View>
            <Badge testID="booking-status" label={t(`status.${b.status}`)} tone={statusTone(b.status)} />
          </View>
          <View style={{ height: 1, backgroundColor: colors.divider }} />
          <T size={18} weight="800">{b.route}</T>
          <T color={colors.muted}>{fmtDate(b.date, { weekday: "long", day: "numeric", month: "long" })} · {b.time} → {trip.arrival_time}</T>
          <T size={13}>{t("trip.pickup")}: <T weight="700" size={13}>{trip.pickup_point}</T></T>
          <T size={13}>{t("trip.drop")}: <T weight="700" size={13}>{trip.drop_point}</T></T>
          <T size={13}>{t("trip.vehicle")}: {trip.vehicle.make} {trip.vehicle.model} {trip.vehicle.color ? `(${trip.vehicle.color})` : ""}</T>
          <T size={13}>{t("trip.passenger_names")}: {b.passenger_names.join(", ")}</T>
          <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
            <T weight="700">{b.seats} × {inr(b.price)}</T>
            <T testID="booking-fare" size={20} weight="800" color={colors.brandPrimary}>{inr(b.fare_total)}</T>
          </View>
          {b.status === "cancelled" ? <T size={12} color={colors.error}>{b.cancel_reason} {b.refund_note ? `· ${b.refund_note}` : ""}</T> : null}
        </Card>

        {!b.is_driver ? (
          <Card testID="booking-payment-instructions" style={{ backgroundColor: colors.accentSoft, borderColor: colors.brandTertiary, gap: space.sm }}>
            <View style={{ flexDirection: "row", gap: space.sm, alignItems: "center" }}>
              <Ionicons name="cash" size={22} color={colors.brandTertiary} />
              <T weight="800" style={{ flex: 1 }}>{t("pay.direct")}</T>
            </View>
            <T size={13}>{t("pay.method")}: <T weight="700" size={13}>{b.payment_method === "upi" ? t("pay.upi_m") : t("pay.cash")}</T></T>
            {active && b.driver.upi_id ? <T testID="booking-driver-upi" size={13}>{t("pay.upi")}: <T weight="800" size={13}>{b.driver.upi_id}</T></T> : null}
            <T size={12} color={colors.muted}>{t("pay.note")}</T>
            <Badge label={b.settlement?.status === "received" ? `${t("settle.received")} · ${b.settlement.method.toUpperCase()}` : t("settle.unpaid")} tone={b.settlement?.status === "received" ? "success" : "muted"} />
          </Card>
        ) : null}

        <Card style={{ gap: space.md }}>
          <View style={{ flexDirection: "row", gap: space.md, alignItems: "center" }}>
            <Avatar name={other.name} uri={other.picture} />
            <View style={{ flex: 1 }}>
              <T size={12} color={colors.muted}>{b.is_driver ? t("search.passengers") : t("trip.driver")}</T>
              <T weight="800">{other.name}</T>
              <Rating value={other.rating_avg} count={other.rating_count} />
            </View>
            {!b.is_driver && b.driver.driver_status === "approved" ? <Badge icon="shield-checkmark" label={t("ride.verified")} tone="success" /> : null}
          </View>
          {active ? (
            <View style={{ flexDirection: "row", gap: space.sm }}>
              <Btn small style={{ flex: 1 }} testID="booking-chat-button" icon="chatbubbles-outline" label={t("booking.chat")} onPress={() => router.push(`/chat/${b.booking_id}`)} />
              {other.phone ? <Btn small style={{ flex: 1 }} variant="outline" testID="booking-call-button" icon="call-outline" label={t("trip.contact")} onPress={() => Linking.openURL(`tel:${other.phone}`)} /> : null}
            </View>
          ) : null}
        </Card>

        <View style={{ flexDirection: "row", gap: space.sm, flexWrap: "wrap" }}>
          <Chip testID="booking-share-button" icon="share-social-outline" label={t("booking.share")} onPress={share} />
          <Chip testID="booking-map-button" icon="map-outline" label={t("trip.map")} onPress={() => openRouteInMaps(trip)} />
          <Chip testID="booking-sos-button" icon="warning-outline" label={t("booking.sos")} onPress={() => router.push(`/support?tab=sos&booking=${b.booking_id}`)} />
          <Chip testID="booking-report-button" icon="flag-outline" label={t("booking.report")} onPress={() => router.push(`/support?type=report_user&booking=${b.booking_id}&user=${other.user_id}`)} />
        </View>

        {actionErr ? <T testID="booking-action-error" color={colors.error} weight="600">{actionErr}</T> : null}

        {b.status === "completed" ? (
          b.my_reviews.length ? (
            <Badge testID="booking-reviewed" icon="star" label={t("booking.reviewed")} tone="success" />
          ) : (
            <Card style={{ gap: space.md }}>
              <T weight="800">{b.is_driver ? t("booking.rate_passenger") : t("booking.rate")}</T>
              <View style={{ flexDirection: "row", gap: space.sm }}>
                {[1, 2, 3, 4, 5].map((n) => (
                  <Pressable key={n} testID={`rate-star-${n}`} onPress={() => setRating(n)} hitSlop={6}>
                    <Ionicons name={n <= rating ? "star" : "star-outline"} size={32} color={colors.brandTertiary} />
                  </Pressable>
                ))}
              </View>
              <Field testID="review-comment-input" placeholder={t("booking.review_ph")} value={comment} onChangeText={setComment} multiline />
              <Btn testID="review-submit-button" label={t("booking.submit")} loading={busy === "rev"} onPress={() => run("rev", () => api("/reviews", { body: { booking_id: b.booking_id, target_id: other.user_id, rating, comment } }), t("booking.reviewed"))} />
            </Card>
          )
        ) : null}

        {["pending", "confirmed"].includes(b.status) ? (
          cancelOpen ? (
            <Card style={{ gap: space.md }}>
              <T weight="800">{t("booking.cancel_reason")}</T>
              <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
                {reasons.map((r) => <Chip key={r} testID={`cancel-reason-${r}`} label={r} active={reason === r} onPress={() => setReason(r)} />)}
              </View>
              <Field testID="cancel-refund-note" label={t("booking.refund_note")} value={refund} onChangeText={setRefund} />
              <Btn testID="booking-cancel-confirm" variant="danger" label={t("common.confirm")} loading={busy === "cancel"} onPress={() => run("cancel", () => api(`/bookings/${b.booking_id}/cancel`, { body: { reason, refund_note: refund } }), t("status.cancelled"))} />
              <Btn variant="ghost" label={t("common.close")} onPress={() => setCancelOpen(false)} testID="booking-cancel-close" />
            </Card>
          ) : (
            <Btn testID="booking-cancel-button" variant="outline" label={t("booking.cancel")} onPress={() => setCancelOpen(true)} />
          )
        ) : null}
        <Btn testID="booking-view-trip" variant="ghost" label={t("trip.details")} onPress={() => router.push(`/trip/${b.trip_id}`)} />
      </KeyboardAwareScrollView>
    </View>
  );
}
