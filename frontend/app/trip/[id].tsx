import Ionicons from "@react-native-vector-icons/ionicons";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { Pressable, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, publicPhoto } from "@/src/api";
import { DriverReviews } from "@/src/components/DriverReviews";
import { FeatureCard } from "@/src/components/FeatureCard";
import { OsmMap } from "@/src/components/OsmMap";
import { fmtDur } from "@/src/components/RideCard";
import { useToast } from "@/src/components/toast";
import { Avatar, Badge, Btn, Card, Chip, ErrorBox, Field, Header, Loading, Rating, Stepper, T, space, statusTone } from "@/src/components/ui";
import { inr, useI18n } from "@/src/i18n";
import { openRouteInMaps } from "@/src/maps";
import { useTheme } from "@/src/theme";

export default function TripScreen() {
  const { id, seats: s0 } = useLocalSearchParams<{ id: string; seats?: string }>();
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t, fmtDate } = useI18n();
  const router = useRouter();
  const toast = useToast();
  const [trip, setTrip] = useState<any>(null);
  const [err, setErr] = useState("");
  const [seats, setSeats] = useState(Number(s0 || 1));
  const [names, setNames] = useState<string[]>([]);
  const [pay, setPay] = useState<"cash" | "upi">("cash");
  const [busy, setBusy] = useState("");
  const [actionErr, setActionErr] = useState("");
  const [cancelOpen, setCancelOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [edit, setEdit] = useState<any>(null);

  const load = useCallback(async () => {
    try {
      setTrip(await api(`/trips/${id}`));
      setErr("");
    } catch (e: any) {
      setErr(e.message);
    }
  }, [id]);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  const act = async (key: string, path: string, body: any = {}, msg?: string) => {
    setBusy(key);
    setActionErr("");
    try {
      const r = await api(path, { body });
      if (msg) toast(msg);
      await load();
      return r;
    } catch (e: any) {
      setActionErr(e.message);
    } finally {
      setBusy("");
    }
  };

  if (err) return <View style={{ flex: 1 }}><Header title={t("trip.details")} /><ErrorBox message={err} onRetry={load} /></View>;
  if (!trip) return <View style={{ flex: 1 }}><Header title={t("trip.details")} /><Loading /></View>;
  const v = trip.vehicle || {};
  const booked = trip.seats_total - trip.seats_available;
  const active = (trip.bookings || []).filter((b: any) => ["confirmed", "started", "completed"].includes(b.status));
  const expected = active.reduce((a: number, b: any) => a + b.fare_total, 0);

  const book = async () => {
    const r = await act("book", "/bookings", { trip_id: trip.trip_id, seats, passenger_names: names.slice(0, seats), payment_method: pay }, t("booking.success"));
    if (r) router.replace(`/booking/${r.booking_id}`);
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title={t("trip.details")} right={trip.is_demo ? <Badge label={t("common.demo")} tone="muted" /> : null} />
      <KeyboardAwareScrollView bottomOffset={24} keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: space.lg, gap: space.lg, paddingBottom: insets.bottom + space.xl }}>
        <Card style={{ gap: space.md }}>
          <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
            <T weight="700" color={colors.muted}>{fmtDate(trip.date, { weekday: "long", day: "numeric", month: "long" })}</T>
            <Badge testID="trip-status" label={t(`status.${trip.status}`)} tone={statusTone(trip.status)} />
          </View>
          {[
            [trip.time, trip.origin, trip.pickup_point, colors.brandPrimary],
            ...trip.stops.map((s: any) => ["", s, t("trip.stops"), colors.muted]),
            [trip.arrival_time, trip.destination, trip.drop_point, colors.brandTertiary],
          ].map(([tm, l, sub, c]: any, i: number) => (
            <View key={i} style={{ flexDirection: "row", gap: space.md }}>
              <T weight="800" style={{ width: 48 }}>{tm}</T>
              <Ionicons name={i === 0 ? "radio-button-on" : "location"} size={18} color={c} />
              <View style={{ flex: 1 }}>
                <T weight="800">{l.name}</T>
                <T size={12} color={colors.muted}>{sub} · {[l.district, l.state].filter(Boolean).join(", ")}</T>
              </View>
            </View>
          ))}
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
            <Badge icon="speedometer-outline" label={`${t("ride.distance")} ${trip.route_source === "osrm" ? "" : "~"}${trip.distance_km} km`} tone="muted" />
            <Badge icon="time-outline" label={`${t("ride.duration")} ${fmtDur(trip.duration_min)}${trip.route_source === "osrm" ? "" : ` (${t("ride.est")})`}`} tone="muted" />
            <Badge icon={trip.instant_booking ? "flash" : "hand-left-outline"} label={trip.instant_booking ? t("trip.instant") : t("trip.request")} tone="warning" />
          </View>
          <OsmMap testID="trip-route-map" style={{ height: 200 }}
            markers={[
              { lat: trip.origin.lat, lng: trip.origin.lng, color: colors.brandPrimary, label: trip.origin.name },
              ...trip.stops.map((x: any) => ({ lat: x.lat, lng: x.lng, color: colors.muted, label: x.name })),
              { lat: trip.destination.lat, lng: trip.destination.lng, color: colors.brandTertiary, label: trip.destination.name },
            ]}
            lines={[{ coords: trip.route ?? [trip.origin, ...trip.stops, trip.destination].map((x: any) => [x.lat, x.lng]), color: colors.brandPrimary, dashed: !trip.route }]} />
          {trip.route_via?.length ? <T size={12} color={colors.muted}>{t("geo.via")} {trip.route_via.join(", ")}</T> : null}
          <Btn testID="trip-open-map-button" small variant="outline" icon="map-outline" label={t("trip.map")} onPress={() => openRouteInMaps(trip)} />
        </Card>

        <Card style={{ gap: space.md }}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: space.md }}>
            <Avatar name={trip.driver.name} uri={trip.driver.has_photo ? publicPhoto(trip.driver_id) : trip.driver.picture} size={52} />
            <View style={{ flex: 1 }}>
              <T testID="trip-driver-name" weight="800" size={16}>{trip.driver.name}</T>
              <Rating value={trip.driver.rating_avg} count={trip.driver.rating_count} />
            </View>
            {trip.driver.driver_status === "approved" ? <Badge icon="shield-checkmark" label={t("ride.verified")} tone="success" /> : null}
          </View>
          <View style={{ height: 1, backgroundColor: colors.divider }} />
          <View style={{ flexDirection: "row", gap: space.md, alignItems: "center" }}>
            <Ionicons name="car-sport-outline" size={22} color={colors.brandPrimary} />
            <View style={{ flex: 1 }}>
              <T weight="700">{v.make} {v.model} {v.color ? `· ${v.color}` : ""}</T>
              <T size={12} color={colors.muted}>{v.vtype?.toUpperCase()} · {v.ac ? t("ride.ac") : t("ride.nonac")} · {t("ride.luggage")}: {t(`vehicle.${v.luggage}`)}</T>
            </View>
          </View>
          {trip.notes ? <T size={13} color={colors.muted}>{t("trip.notes")}: {trip.notes}</T> : null}
          {trip.driver.bio ? <T testID="trip-driver-bio" size={13}><T weight="700" size={13}>{t("v2.about_me")}: </T>{trip.driver.bio}</T> : null}
          <Btn small variant="ghost" icon="person-outline" label={t("v2.view_profile")} onPress={() => router.push(`/user/${trip.driver_id}`)} testID="trip-driver-profile-link" />
        </Card>

        {!trip.is_driver ? (
          <DriverReviews avg={trip.driver.rating_avg} count={trip.driver.rating_count} reviews={trip.driver_reviews ?? []} onSeeAll={() => router.push(`/user/${trip.driver_id}`)} />
        ) : null}

        {trip.is_driver && trip.status === "scheduled" && trip.seats_available > 0 ? <FeatureCard tripId={trip.trip_id} /> : null}

        {trip.price_suggestion || trip.cost_breakdown ? (
          <Card testID="trip-price-suggestion" style={{ gap: 2 }}>
            <T size={13} weight="800" color={colors.brandPrimary}>{t("trip.suggested_price")}: {inr(trip.price)}</T>
            {trip.is_driver && trip.price_suggestion ? <T size={12} color={colors.muted}>{t("offer.suggested_label")}: {inr(trip.price_suggestion.recommended)} {t("offer.per_person_short")}</T> : null}
            <T size={11} color={colors.muted}>Set by the driver to share travel costs. Not a fuel bill or a fixed fare.</T>
          </Card>
        ) : null}


        <Card style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
          <View>
            <T testID="trip-price" size={24} weight="800" color={colors.brandPrimary}>{inr(trip.price)}</T>
            <T size={12} color={colors.muted}>{t("ride.per_seat")}</T>
          </View>
          <T testID="trip-seats-left" weight="700">{trip.seats_available ? t("ride.seats_left", { n: trip.seats_available }) : t("trip.full")}</T>
        </Card>

        {actionErr ? <T testID="trip-action-error" color={colors.error} weight="600">{actionErr}</T> : null}

        {trip.is_driver ? (
          <>
            <Card style={{ backgroundColor: colors.brand, borderColor: colors.brand, gap: space.xs }}>
              <T color={colors.onBrand} style={{ opacity: 0.8 }}>{t("trip.expected")}</T>
              <T testID="trip-expected-earnings" size={26} weight="800" color={colors.onBrand}>{inr(expected)}</T>
              <T size={12} color={colors.onBrand} style={{ opacity: 0.8 }}>{booked}/{trip.seats_total} {t("trip.seats")} · {inr(trip.price)} × {booked}</T>
            </Card>
            <T size={18} weight="800">{t("trip.bookings")}</T>
            {trip.bookings.length === 0 ? <T color={colors.muted}>{t("trip.no_bookings")}</T> : null}
            {trip.bookings.map((b: any) => (
              <Card key={b.booking_id} testID={`trip-booking-${b.booking_id}`} style={{ gap: space.sm }}>
                <View style={{ flexDirection: "row", gap: space.md, alignItems: "center" }}>
                  <Avatar name={b.passenger?.name} uri={b.passenger?.picture} size={40} />
                  <View style={{ flex: 1 }}>
                    <T weight="700">{b.passenger?.name}</T>
                    <T size={12} color={colors.muted}>{b.seats} {t("trip.seats")} · {inr(b.fare_total)} · {b.payment_method.toUpperCase()}</T>
                  </View>
                  <Badge label={t(`status.${b.status}`)} tone={statusTone(b.status)} />
                </View>
                {b.passenger_names?.length ? <T size={12} color={colors.muted}>{b.passenger_names.join(", ")}</T> : null}
                {b.status === "pending" ? (
                  <View style={{ flexDirection: "row", gap: space.sm }}>
                    <Btn small style={{ flex: 1 }} testID={`accept-${b.booking_id}`} label={t("trip.accept")} loading={busy === `a${b.booking_id}`} onPress={() => act(`a${b.booking_id}`, `/bookings/${b.booking_id}/accept`)} />
                    <Btn small style={{ flex: 1 }} variant="outline" testID={`reject-${b.booking_id}`} label={t("trip.reject")} loading={busy === `r${b.booking_id}`} onPress={() => act(`r${b.booking_id}`, `/bookings/${b.booking_id}/reject`)} />
                  </View>
                ) : null}
                {["confirmed", "started", "completed"].includes(b.status) ? (
                  b.settlement?.status === "received" ? (
                    <Badge testID={`settled-${b.booking_id}`} icon="checkmark-circle" label={`${t("settle.received")} · ${b.settlement.method.toUpperCase()}`} tone="success" />
                  ) : (
                    <View style={{ flexDirection: "row", gap: space.sm, alignItems: "center", flexWrap: "wrap" }}>
                      <T size={12} color={colors.muted}>{t("settle.mark_received")}:</T>
                      <Chip testID={`settle-cash-${b.booking_id}`} icon="cash-outline" label={t("pay.cash")} onPress={() => act("s", `/bookings/${b.booking_id}/settle`, { method: "cash" }, t("settle.received"))} />
                      <Chip testID={`settle-upi-${b.booking_id}`} icon="phone-portrait-outline" label={t("pay.upi_m")} onPress={() => act("s", `/bookings/${b.booking_id}/settle`, { method: "upi" }, t("settle.received"))} />
                    </View>
                  )
                ) : null}
                {b.status !== "pending" && b.status !== "rejected" ? <Btn small variant="ghost" icon="open-outline" label={t("booking.confirmation")} onPress={() => router.push(`/booking/${b.booking_id}`)} testID={`open-booking-${b.booking_id}`} /> : null}
              </Card>
            ))}
            {trip.status === "scheduled" && edit ? (
              <Card style={{ gap: space.md }}>
                <Field testID="trip-edit-pickup" label={t("offer.pickup")} value={edit.pickup_point} onChangeText={(x) => setEdit({ ...edit, pickup_point: x })} />
                <Field testID="trip-edit-drop" label={t("offer.drop")} value={edit.drop_point} onChangeText={(x) => setEdit({ ...edit, drop_point: x })} />
                <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
                  <T weight="600">{t("offer.seats")}</T>
                  <Stepper testID="trip-edit-seats" value={edit.seats} min={Math.max(1, booked)} max={["hatchback", "sedan", "other"].includes(trip.vehicle?.vtype) ? 3 : 8} onChange={(x) => setEdit({ ...edit, seats: x })} />
                </View>
                <Field testID="trip-edit-notes" label={t("offer.notes")} value={edit.notes} onChangeText={(x) => setEdit({ ...edit, notes: x })} multiline />
                <Btn testID="trip-edit-save" label={t("common.save")} loading={busy === "edit"} onPress={async () => { setBusy("edit"); try { setActionErr(""); await api(`/trips/${id}`, { method: "PUT", body: edit }); setEdit(null); await load(); } catch (e: any) { setActionErr(e.message); } setBusy(""); }} />
              </Card>
            ) : null}
            {trip.status === "scheduled" ? (
              <View style={{ gap: space.sm }}>
                {!edit ? <Btn testID="trip-edit-button" variant="outline" icon="create-outline" label={t("trip.edit")} onPress={() => setEdit({ pickup_point: trip.pickup_point, drop_point: trip.drop_point, seats: trip.seats_total, notes: trip.notes })} /> : null}
                <Btn testID="trip-start-button" icon="play" label={t("trip.start")} loading={busy === "start"} onPress={() => act("start", `/trips/${id}/start`)} />
              </View>
            ) : null}
            {["scheduled", "started"].includes(trip.status) ? <Btn testID="trip-complete-button" variant="navy" icon="flag" label={t("trip.complete")} loading={busy === "complete"} onPress={() => act("complete", `/trips/${id}/complete`)} /> : null}
            {trip.status === "scheduled" ? (
              cancelOpen ? (
                <Card style={{ gap: space.md }}>
                  <Field testID="trip-cancel-reason" label={t("booking.cancel_reason")} value={reason} onChangeText={setReason} />
                  <Btn testID="trip-cancel-confirm" variant="danger" label={t("common.confirm")} loading={busy === "cancel"} onPress={() => act("cancel", `/trips/${id}/cancel`, { reason })} />
                </Card>
              ) : (
                <Btn testID="trip-cancel-button" variant="ghost" label={t("trip.cancel")} onPress={() => setCancelOpen(true)} />
              )
            ) : null}
          </>
        ) : trip.my_booking ? (
          <Btn testID="trip-view-my-booking" icon="ticket" label={`${t("booking.confirmation")} · ${t(`status.${trip.my_booking.status}`)}`} onPress={() => router.push(`/booking/${trip.my_booking.booking_id}`)} />
        ) : trip.status === "scheduled" && trip.seats_available > 0 ? (
          <Card style={{ gap: space.md }}>
            <T size={18} weight="800">{t("trip.book")}</T>
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
              <T weight="600">{t("trip.seats")}</T>
              <Stepper testID="book-seats" value={Math.min(seats, trip.seats_available)} max={trip.seats_available} onChange={setSeats} />
            </View>
            <T size={13} weight="600" color={colors.muted}>{t("trip.passenger_names")}</T>
            {Array.from({ length: Math.min(seats, trip.seats_available) }).map((_, i) => (
              <Field key={i} testID={`book-passenger-name-${i}`} placeholder={`${t("search.passengers")} ${i + 1}`} value={names[i] ?? ""} onChangeText={(x) => { const n = [...names]; n[i] = x; setNames(n); }} />
            ))}
            <T size={13} weight="600" color={colors.muted}>{t("pay.method")}</T>
            <View style={{ flexDirection: "row", gap: space.sm }}>
              <Chip testID="book-pay-cash" icon="cash-outline" label={t("pay.cash")} active={pay === "cash"} onPress={() => setPay("cash")} />
              <Chip testID="book-pay-upi" icon="phone-portrait-outline" label={t("pay.upi_m")} active={pay === "upi"} onPress={() => setPay("upi")} />
            </View>
            <View style={{ backgroundColor: colors.accentSoft, borderRadius: 12, padding: space.md, gap: 4 }}>
              <T weight="800" color={colors.brandTertiary}>{t("pay.direct")}</T>
              <T size={12} color={colors.muted}>{t("pay.note")}</T>
            </View>
            <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
              <T weight="700">{t("trip.fare")}</T>
              <T testID="book-total-fare" size={20} weight="800" color={colors.brandPrimary}>{inr(trip.price * Math.min(seats, trip.seats_available))}</T>
            </View>
            <Btn testID="book-confirm-button" icon="checkmark-circle" label={t("trip.confirm_book")} loading={busy === "book"} onPress={book} />
          </Card>
        ) : (
          <Badge label={trip.seats_available ? t(`status.${trip.status}`) : t("trip.full")} tone="error" />
        )}
        <Pressable testID="trip-report-link" onPress={() => router.push(`/support?type=report_user&user=${trip.driver_id}`)} style={{ alignItems: "center", padding: space.sm }}>
          <T size={13} color={colors.muted}>{t("booking.report")}</T>
        </Pressable>
      </KeyboardAwareScrollView>
    </View>
  );
}
