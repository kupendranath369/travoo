import Ionicons from "@react-native-vector-icons/ionicons";
import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useMemo, useState } from "react";
import { Pressable, Switch, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Loc, locPayload } from "@/src/api";
import { useAuth } from "@/src/auth";
import { DateChips, TimeChips, isoDate } from "@/src/components/DateChips";
import { LocationField, LocationSearchModal } from "@/src/components/LocationField";
import { fmtDur } from "@/src/components/RideCard";
import { useToast } from "@/src/components/toast";
import { Badge, Btn, Card, Chip, Empty, Field, Loading, Stepper, T, space } from "@/src/components/ui";
import { inr, useI18n } from "@/src/i18n";
import { usesNativeTabs } from "@/src/navigation";
import { useTheme } from "@/src/theme";

const km = (a: Loc, b: Loc) => {
  const r = Math.PI / 180;
  const h = Math.sin(((b.lat - a.lat) * r) / 2) ** 2 + Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin(((b.lng - a.lng) * r) / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(h));
};

export default function OfferScreen() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t } = useI18n();
  const { user, refresh } = useAuth();
  const router = useRouter();
  const toast = useToast();
  const [vehicles, setVehicles] = useState<any[] | null>(null);
  const [o, setO] = useState<Loc | null>(null);
  const [d, setD] = useState<Loc | null>(null);
  const [stops, setStops] = useState<Loc[]>([]);
  const [stopOpen, setStopOpen] = useState(false);
  const [pickup, setPickup] = useState("");
  const [drop, setDrop] = useState("");
  const [date, setDate] = useState<string | null>(isoDate(new Date(Date.now() + 86400000)));
  const [time, setTime] = useState("08:00");
  const [seats, setSeats] = useState(3);
  const [price, setPrice] = useState("");
  const [vid, setVid] = useState<string | null>(null);
  const [instant, setInstant] = useState(true);
  const [notes, setNotes] = useState("");
  const [preview, setPreview] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useFocusEffect(
    useCallback(() => {
      refresh();
      api("/driver/profile").then((r) => {
        setVehicles(r.vehicles);
        if (r.vehicles[0]) setVid((v) => v ?? r.vehicles[0].vehicle_id);
      }).catch(() => setVehicles([]));
    }, [refresh]),
  );

  const est = useMemo(() => {
    if (!o || !d) return null;
    const pts = [o, ...stops, d];
    let dist = 0;
    for (let i = 0; i < pts.length - 1; i++) dist += km(pts[i], pts[i + 1]);
    const road = Math.round(dist * 1.3);
    const mins = Math.round((road / 55) * 60) + stops.length * 10;
    const [h, m] = time.split(":").map(Number);
    const tot = h * 60 + m + mins;
    return { road, mins, arrival: `${String(Math.floor(tot / 60) % 24).padStart(2, "0")}:${String(tot % 60).padStart(2, "0")}` };
  }, [o, d, stops, time]);

  const bottom = (usesNativeTabs ? insets.bottom : 0) + space.xl;
  if (!user || vehicles === null) return <Loading />;

  if (user.driver_status !== "approved") {
    const review = user.driver_status === "under_review";
    return (
      <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top + space.xl, padding: space.lg, justifyContent: "center" }}>
        <Empty
          icon={review ? "hourglass-outline" : "shield-checkmark-outline"}
          title={review ? t("offer.under_review") : t("offer.need_verify")}
          body={review ? t(`verify.status.${user.driver_status}`) : t("offer.need_verify_d")}
          action={<Btn testID="offer-verify-button" label={review ? t("profile.verification") : t("offer.verify_btn")} onPress={() => router.push("/driver")} style={{ marginTop: space.md, alignSelf: "stretch" }} />}
        />
      </View>
    );
  }
  if (!vehicles.length)
    return (
      <View style={{ flex: 1, backgroundColor: colors.surface, padding: space.lg, justifyContent: "center" }}>
        <Empty icon="car-outline" title={t("offer.need_vehicle")} action={<Btn testID="offer-add-vehicle-button" label={t("vehicle.add")} onPress={() => router.push("/driver")} style={{ marginTop: space.md, alignSelf: "stretch" }} />} />
      </View>
    );

  const validate = () => {
    if (!o || !d) return t("search.pick_both");
    if (!pickup.trim()) return `${t("offer.pickup")} *`;
    if (!drop.trim()) return `${t("offer.drop")} *`;
    if (!date) return `${t("offer.date")} *`;
    if (!Number(price) || Number(price) < 50) return `${t("offer.price")} * (min ₹50)`;
    return "";
  };

  const publish = async () => {
    setBusy(true);
    setErr("");
    try {
      const trip = await api("/trips", {
        body: { origin: locPayload(o!), destination: locPayload(d!), stops: stops.map(locPayload), pickup_point: pickup.trim(), drop_point: drop.trim(), date, time, seats, price: Number(price), vehicle_id: vid, instant_booking: instant, notes: notes.trim() },
      });
      toast(t("offer.published"));
      setPreview(false);
      setO(null); setD(null); setStops([]); setPickup(""); setDrop(""); setPrice(""); setNotes("");
      router.push(`/trip/${trip.trip_id}`);
    } catch (e: any) {
      setErr(e.message);
    }
    setBusy(false);
  };

  const veh = vehicles.find((v) => v.vehicle_id === vid);

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <View style={{ paddingTop: insets.top + space.sm, paddingHorizontal: space.lg, paddingBottom: space.md, backgroundColor: colors.surfaceSecondary, borderBottomWidth: 1, borderBottomColor: colors.border }}>
        <T size={22} weight="800">{t("offer.title")}</T>
      </View>
      <KeyboardAwareScrollView bottomOffset={24} keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: space.lg, gap: space.lg, paddingBottom: bottom }}>
        {preview && est ? (
          <Card testID="offer-preview-card" style={{ gap: space.md }}>
            <Badge label={t("offer.preview")} tone="warning" />
            <T size={18} weight="800">{o!.name} → {d!.name}</T>
            <T color={colors.muted}>{date} · {time} → {est.arrival} ({t("ride.est")})</T>
            <T color={colors.muted}>{t("trip.pickup")}: {pickup}</T>
            <T color={colors.muted}>{t("trip.drop")}: {drop}</T>
            {stops.length ? <T color={colors.muted}>{t("trip.stops")}: {stops.map((s) => s.name).join(", ")}</T> : null}
            <T color={colors.muted}>{veh?.make} {veh?.model} · {veh?.ac ? t("ride.ac") : t("ride.nonac")}</T>
            <T color={colors.muted}>~{est.road} km · {fmtDur(est.mins)}</T>
            <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
              <T weight="700">{seats} × {inr(Number(price))}</T>
              <T testID="offer-max-earnings" weight="800" color={colors.brandPrimary}>{inr(seats * Number(price))}</T>
            </View>
            <T size={12} color={colors.muted}>{t("offer.max_earn")} · {t("earn.no_commission")}</T>
            {err ? <T testID="offer-error" color={colors.error}>{err}</T> : null}
            <Btn testID="offer-publish-button" label={t("offer.publish")} icon="checkmark-circle" onPress={publish} loading={busy} />
            <Btn testID="offer-edit-button" variant="ghost" label={t("common.back")} onPress={() => setPreview(false)} />
          </Card>
        ) : (
          <>
            <Card style={{ paddingVertical: space.sm, gap: 0 }}>
              <LocationField testID="offer-origin-field" label={t("offer.origin")} value={o} onChange={setO} icon="radio-button-on" />
              <View style={{ height: 1, backgroundColor: colors.divider }} />
              <LocationField testID="offer-dest-field" label={t("offer.dest")} value={d} onChange={setD} icon="location" />
            </Card>
            <Field testID="offer-pickup-input" label={t("offer.pickup")} value={pickup} onChangeText={setPickup} placeholder="e.g. Silk Board Junction, Gate 2" />
            <Field testID="offer-drop-input" label={t("offer.drop")} value={drop} onChangeText={setDrop} placeholder="e.g. Koyambedu Bus Terminus" />
            <View style={{ gap: space.sm }}>
              <T size={13} weight="600" color={colors.muted}>{t("offer.stops")}</T>
              <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
                {stops.map((s, i) => (
                  <Chip key={s.loc_id} testID={`offer-stop-${i}`} icon="close" label={s.name} active onPress={() => setStops(stops.filter((_, j) => j !== i))} />
                ))}
                {stops.length < 6 ? <Chip testID="offer-add-stop-button" icon="add" label={t("offer.add_stop")} onPress={() => setStopOpen(true)} /> : null}
              </View>
            </View>
            <View style={{ gap: space.xs }}>
              <T size={13} weight="600" color={colors.muted}>{t("offer.date")}</T>
              <DateChips value={date} onChange={setDate} testID="offer-date" days={60} />
            </View>
            <View style={{ gap: space.xs }}>
              <T size={13} weight="600" color={colors.muted}>{t("offer.time")}: <T weight="800">{time}</T>{est ? `  ·  ${t("offer.est_arrival")}: ${est.arrival}` : ""}</T>
              <TimeChips value={time} onChange={setTime} />
            </View>
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
              <T weight="600">{t("offer.seats")}</T>
              <Stepper testID="offer-seats" value={seats} max={veh?.seats ?? 8} onChange={setSeats} />
            </View>
            <Field testID="offer-price-input" label={t("offer.price")} value={price} onChangeText={(v) => setPrice(v.replace(/\D/g, ""))} keyboardType="number-pad" placeholder="700" />
            {Number(price) ? <T size={13} color={colors.brandPrimary} weight="700">{t("offer.max_earn")}: {inr(seats * Number(price))}</T> : null}
            <View style={{ gap: space.sm }}>
              <T size={13} weight="600" color={colors.muted}>{t("offer.vehicle")}</T>
              {vehicles.map((v) => (
                <Pressable key={v.vehicle_id} testID={`offer-vehicle-${v.vehicle_id}`} onPress={() => setVid(v.vehicle_id)} style={{ flexDirection: "row", alignItems: "center", gap: space.md, padding: space.md, borderRadius: 12, borderWidth: vid === v.vehicle_id ? 2 : 1, borderColor: vid === v.vehicle_id ? colors.brandPrimary : colors.border, backgroundColor: colors.surfaceSecondary }}>
                  <Ionicons name="car-sport" size={22} color={colors.brandPrimary} />
                  <View style={{ flex: 1 }}>
                    <T weight="700">{v.make} {v.model}</T>
                    <T size={12} color={colors.muted}>{v.reg_no} · {v.seats} seats · {v.ac ? t("ride.ac") : t("ride.nonac")}</T>
                  </View>
                </Pressable>
              ))}
            </View>
            <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: space.md }}>
              <T weight="600" style={{ flex: 1 }}>{t("offer.instant")}</T>
              <Switch testID="offer-instant-switch" value={instant} onValueChange={setInstant} trackColor={{ true: colors.brandPrimary, false: colors.border }} />
            </View>
            <Field testID="offer-notes-input" label={t("offer.notes")} value={notes} onChangeText={setNotes} multiline maxLength={500} />
            {err ? <T testID="offer-error" color={colors.error}>{err}</T> : null}
            <Btn testID="offer-preview-button" label={t("offer.preview")} icon="eye-outline" onPress={() => { const v = validate(); if (v) setErr(v); else { setErr(""); setPreview(true); } }} />
          </>
        )}
      </KeyboardAwareScrollView>
      <LocationSearchModal visible={stopOpen} title={t("offer.add_stop")} onClose={() => setStopOpen(false)} onSelect={(l) => { setStops([...stops, l]); setStopOpen(false); }} />
    </View>
  );
}
