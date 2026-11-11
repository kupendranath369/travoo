import Ionicons from "@react-native-vector-icons/ionicons";
import { router, useFocusEffect } from "expo-router";
import React, { useCallback, useState } from "react";
import { Image, Pressable, Switch, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, fileUrl } from "@/src/api";
import { useAuth } from "@/src/auth";
import { DocPhotos } from "@/src/components/DocPhotos";
import { useToast } from "@/src/components/toast";
import { Badge, Btn, Card, Chip, Field, Header, Loading, Section, Stepper, T, radius, space, statusTone } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

const VTYPES = ["hatchback", "sedan", "suv", "muv"];
const SEAT_CAP: Record<string, number> = { hatchback: 3, sedan: 3, suv: 8, muv: 8 };

export default function DriverScreen() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t } = useI18n();
  const { user, refresh } = useAuth();
  const toast = useToast();
  const [p, setP] = useState<any>(null);
  const [f, setF] = useState({ vehicle_name: "", phone: "", licence_no: "", licence_expiry: "", rc_no: "" });
  const [v, setV] = useState({ make: "", model: "", vtype: "sedan", color: "", reg_no: "", seats: 3, ac: true, luggage: "medium", fuel_type: "petrol", mileage: "" });
  const [vOpen, setVOpen] = useState(false);
  const [err, setErr] = useState("");
  const [vErr, setVErr] = useState("");
  const [busy, setBusy] = useState("");
  const [licenceFront, setLicenceFront] = useState<string | null>(null);
  const [licenceBack, setLicenceBack] = useState<string | null>(null);
  const [licenceVerification, setLicenceVerification] = useState<any>(null);

  const load = useCallback(async () => {
    const r = await api("/driver/profile");
    setP(r);
    // Load licence verification status
    try {
      const lv = await api("/driver/licence-verification");
      setLicenceVerification(lv);
    } catch (e) {
      // Verification not submitted yet
      setLicenceVerification({ status: "not_submitted" });
    }
    await refresh();
  }, [refresh]);
  useFocusEffect(useCallback(() => { load().catch((e) => setErr(e.message)); }, [load]));

  if (!p || !user) return <View style={{ flex: 1 }}><Header title={t("verify.title")} /><Loading /></View>;
  const canSubmit = ["not_submitted", "rejected", "resubmit"].includes(p.status);

  const submit = async () => {
    if (f.vehicle_name.trim().length < 2) return setErr(`${t("verify.vehicle_name")} *`);
    if (!/^[6-9]\d{9}$/.test(f.phone)) return setErr(`${t("verify.phone")} *`);
    if (f.licence_no.replace(/\s/g, "").length < 8) return setErr(`${t("verify.licence")} *`);
    if (!/^\d{2}-\d{2}-\d{4}$/.test(f.licence_expiry)) return setErr(`${t("verify.licence_exp")} *`);
    if (f.rc_no.replace(/\s/g, "").length < 6) return setErr(`${t("verify.rc")} *`);
    setBusy("v");
    setErr("");
    try {
      const r = await api("/driver/verification", { body: { ...f, licence_no: f.licence_no.replace(/\s/g, ""), rc_no: f.rc_no.replace(/\s/g, "") } });
      toast(t(`verify.status.${r.status}`));
      await load();
    } catch (e: any) {
      setErr(e.message);
    }
    setBusy("");
  };

  const submitLicenceVerification = async () => {
    if (!licenceFront || !licenceBack) return setErr("Please upload both front and back of licence");
    if (f.licence_no.replace(/\s/g, "").length < 8) return setErr(`${t("verify.licence")} *`);
    if (!/^\d{2}-\d{2}-\d{4}$/.test(f.licence_expiry)) return setErr(`${t("verify.licence_exp")} *`);
    setBusy("licence");
    setErr("");
    try {
      const r = await api("/driver/licence-verification", {
        body: {
          licence_front: licenceFront,
          licence_back: licenceBack,
          manual_licence_no: f.licence_no,
          manual_expiry: f.licence_expiry,
        }
      });
      toast("Licence verification submitted");
      await load();
    } catch (e: any) {
      setErr(e.message);
    }
    setBusy("");
  };
  const addVehicle = async () => {
    setBusy("veh");
    setVErr("");
    try {
      await api("/vehicles", { body: { ...v, mileage: Number(v.mileage) || null } });
      setVOpen(false);
      setV({ make: "", model: "", vtype: "sedan", color: "", reg_no: "", seats: 3, ac: true, luggage: "medium", fuel_type: "petrol", mileage: "" });
      await load();
    } catch (e: any) {
      setVErr(e.message);
    }
    setBusy("");
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title={t("verify.title")} />
      <KeyboardAwareScrollView bottomOffset={24} keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: space.lg, gap: space.lg, paddingBottom: insets.bottom + space.xl }}>
        <Card style={{ flexDirection: "row", alignItems: "center", gap: space.md }}>
          <Ionicons name="shield-checkmark" size={32} color={p.status === "approved" ? colors.success : colors.brandTertiary} />
          <View style={{ flex: 1, gap: 4 }}>
            <T weight="800">{t("verify.title")}</T>
            <Badge testID="driver-verification-status" label={t(`verify.status.${p.status}`)} tone={statusTone(p.status)} />
            {p.documents?.admin_note ? <T size={12} color={colors.muted}>{t("verify.admin_note")}: {p.documents.admin_note}</T> : null}
          </View>
        </Card>

        {canSubmit ? (
          <Card style={{ gap: space.md }}>
            <T weight="800">Verify your documents</T>
            <T size={12} color={colors.muted}>Upload your driving licence (front and back), Aadhaar card and vehicle RC, then type four details. Our team checks everything by hand.</T>
            <Btn testID="driver-manual-verification-button" icon="cloud-upload-outline" label="Upload documents" onPress={() => router.push("/driver/manual-verification")} />
            {err ? <T testID="verify-error" color={colors.error}>{err}</T> : null}
          </Card>
        ) : p.documents?.licence_no ? (
          <Card style={{ gap: 4 }}>
            <DocPhotos files={p.files ?? []} kinds={p.kinds ?? []} editable={false} onChanged={() => {}} />
            {p.documents.vehicle_name ? (
              <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
                <T size={13} color={colors.muted}>{t("verify.vehicle_name")}:</T>
                <T size={13}>{p.documents.vehicle_name}</T>
              </View>
            ) : null}
            <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
              <T size={13} color={colors.muted}>{t("verify.licence")}:</T>
              <T size={13}>{p.documents.licence_no}</T>
            </View>
            <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
              <T size={13} color={colors.muted}>{t("verify.rc")}:</T>
              <T size={13}>{p.documents.rc_no}</T>
            </View>
          </Card>
        ) : null}

        <Section title={t("vehicle.title")} right={!vOpen ? <Btn small variant="ghost" icon="add" label={t("vehicle.add")} onPress={() => setVOpen(true)} testID="vehicle-add-button" /> : null}>
          {p.vehicles.map((x: any) => (
            <Card key={x.vehicle_id} testID={`vehicle-${x.vehicle_id}`} style={{ flexDirection: "row", alignItems: "center", gap: space.md }}>
              <Ionicons name="car-sport" size={26} color={colors.brandPrimary} />
              <View style={{ flex: 1 }}>
                <T weight="800">{x.make} {x.model}</T>
                <T size={12} color={colors.muted}>{x.reg_no} · {(x.vtype ?? "").toUpperCase()} · {Math.min(x.seats, SEAT_CAP[x.vtype] ?? 3)} {t("vehicle.passenger_seats").toLowerCase()} · {x.ac ? t("ride.ac") : t("ride.nonac")}</T>
              </View>
              {x.verified ? <Badge label={t("ride.verified")} tone="success" /> : null}
              <Pressable testID={`vehicle-delete-${x.vehicle_id}`} hitSlop={10} onPress={() => api(`/vehicles/${x.vehicle_id}`, { method: "DELETE" }).then(load)}>
                <Ionicons name="trash-outline" size={20} color={colors.error} />
              </Pressable>
            </Card>
          ))}
          {vOpen ? (
            <Card style={{ gap: space.md }}>
              <Field testID="vehicle-make" label={t("vehicle.make")} value={v.make} onChangeText={(x) => setV({ ...v, make: x })} placeholder="Maruti Suzuki" />
              <Field testID="vehicle-model" label={t("vehicle.model")} value={v.model} onChangeText={(x) => setV({ ...v, model: x })} placeholder="Dzire" />
              <T size={13} weight="600" color={colors.muted}>{t("vehicle.type")}</T>
              <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
                {VTYPES.map((x) => <Chip key={x} testID={`vehicle-type-${x}`} label={x.toUpperCase()} active={v.vtype === x} onPress={() => setV({ ...v, vtype: x, seats: SEAT_CAP[x] === 3 ? Math.min(v.seats, 3) : Math.max(v.seats, 4) })} />)}
              </View>
              <Field testID="vehicle-color" label={t("vehicle.color")} value={v.color} onChangeText={(x) => setV({ ...v, color: x })} />
              <Field testID="vehicle-reg" label={t("vehicle.reg")} value={v.reg_no} onChangeText={(x) => setV({ ...v, reg_no: x.toUpperCase() })} autoCapitalize="characters" />
              <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: space.sm }}>
                <T weight="600" style={{ flex: 1 }}>{t("vehicle.passenger_seats")}</T>
                <Stepper testID="vehicle-seats" value={v.seats} max={SEAT_CAP[v.vtype] ?? 3} onChange={(x) => setV({ ...v, seats: x })} />
              </View>
              <T testID="vehicle-seats-hint" size={12} color={colors.muted}>{SEAT_CAP[v.vtype] === 3 ? t("vehicle.seats_hint_small") : t("vehicle.seats_hint_big")}</T>
              <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
                <T weight="600">{t("vehicle.ac")}</T>
                <Switch testID="vehicle-ac-switch" value={v.ac} onValueChange={(x) => setV({ ...v, ac: x })} trackColor={{ true: colors.brandPrimary, false: colors.border }} />
              </View>
              <T size={13} weight="600" color={colors.muted}>{t("vehicle.luggage")}</T>
              <View style={{ flexDirection: "row", gap: space.sm }}>
                {["small", "medium", "large"].map((x) => <Chip key={x} testID={`vehicle-luggage-${x}`} label={t(`vehicle.${x}`)} active={v.luggage === x} onPress={() => setV({ ...v, luggage: x })} />)}
              </View>
              <T size={13} weight="600" color={colors.muted}>{t("v2.fuel_type")}</T>
              <View style={{ flexDirection: "row", gap: space.sm, flexWrap: "wrap" }}>
                {["petrol", "diesel", "cng", "electric"].map((x) => <Chip key={x} testID={`vehicle-fuel-${x}`} label={x.toUpperCase()} active={v.fuel_type === x} onPress={() => setV({ ...v, fuel_type: x })} />)}
              </View>
              <Field testID="vehicle-mileage" label={`${t("v2.mileage")} (${v.fuel_type === "electric" ? "km/kWh" : v.fuel_type === "cng" ? "km/kg" : "km/l"})`} value={v.mileage} onChangeText={(x) => setV({ ...v, mileage: x.replace(/[^\d.]/g, "") })} keyboardType="decimal-pad" />
              {vErr ? <T testID="vehicle-error" color={colors.error}>{vErr}</T> : null}
              <Btn testID="vehicle-save-button" label={t("vehicle.save")} onPress={addVehicle} loading={busy === "veh"} />
              <Btn variant="ghost" label={t("common.cancel")} onPress={() => setVOpen(false)} testID="vehicle-cancel-button" />
            </Card>
          ) : null}
        </Section>
      </KeyboardAwareScrollView>
    </View>
  );
}
