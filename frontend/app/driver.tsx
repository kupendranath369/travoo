import Ionicons from "@react-native-vector-icons/ionicons";
import { useFocusEffect } from "expo-router";
import React, { useCallback, useState } from "react";
import { Pressable, Switch, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { useAuth } from "@/src/auth";
import { DOC_KINDS, DocPhotos } from "@/src/components/DocPhotos";
import { useToast } from "@/src/components/toast";
import { Badge, Btn, Card, Chip, Field, Header, Loading, Section, Stepper, T, space, statusTone } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

const VTYPES = ["hatchback", "sedan", "suv", "muv", "other"];

export default function DriverScreen() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t } = useI18n();
  const { user, refresh } = useAuth();
  const toast = useToast();
  const [p, setP] = useState<any>(null);
  const [f, setF] = useState({ legal_name: "", vehicle_name: "", phone: "", licence_no: "", licence_expiry: "", rc_no: "" });
  const [v, setV] = useState({ make: "", model: "", vtype: "sedan", color: "", reg_no: "", seats: 3, ac: true, luggage: "medium" });
  const [vOpen, setVOpen] = useState(false);
  const [err, setErr] = useState("");
  const [vErr, setVErr] = useState("");
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    const r = await api("/driver/profile");
    setP(r);
    await refresh();
  }, [refresh]);
  useFocusEffect(useCallback(() => { load().catch((e) => setErr(e.message)); }, [load]));

  if (!p || !user) return <View style={{ flex: 1 }}><Header title={t("verify.title")} /><Loading /></View>;
  const canSubmit = ["not_submitted", "rejected", "resubmit"].includes(p.status);

  const submit = async () => {
    if (f.legal_name.trim().length < 3) return setErr(`${t("verify.legal_name")} *`);
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
  const addVehicle = async () => {
    setBusy("veh");
    setVErr("");
    try {
      await api("/vehicles", { body: v });
      setVOpen(false);
      setV({ make: "", model: "", vtype: "sedan", color: "", reg_no: "", seats: 3, ac: true, luggage: "medium" });
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
            <T weight="800">{t("verify.photos")}</T>
            <DocPhotos photos={p.documents?.photos ?? {}} editable onUploaded={() => load().catch(() => {})} />
            {DOC_KINDS.some((k) => !p.documents?.photos?.[k]) ? <T testID="verify-photos-required" size={12} color={colors.brandTertiary}>{t("verify.photos_required")}</T> : null}
            <Field testID="verify-legal-name" label={t("verify.legal_name")} value={f.legal_name} onChangeText={(x) => setF({ ...f, legal_name: x })} />
            <Field testID="verify-vehicle-name" label={t("verify.vehicle_name")} value={f.vehicle_name} onChangeText={(x) => setF({ ...f, vehicle_name: x })} placeholder="Maruti Suzuki Dzire" />
            <Field testID="verify-phone" label={t("verify.phone")} value={f.phone} onChangeText={(x) => setF({ ...f, phone: x.replace(/\D/g, "") })} keyboardType="phone-pad" maxLength={10} />
            <Field testID="verify-licence" label={t("verify.licence")} value={f.licence_no} onChangeText={(x) => setF({ ...f, licence_no: x.toUpperCase() })} autoCapitalize="characters" placeholder="KA0120200001234" />
            <Field testID="verify-licence-expiry" label={t("verify.licence_exp")} value={f.licence_expiry} onChangeText={(x) => setF({ ...f, licence_expiry: x })} placeholder="31-12-2035" maxLength={10} />
            <Field testID="verify-rc" label={t("verify.rc")} value={f.rc_no} onChangeText={(x) => setF({ ...f, rc_no: x.toUpperCase() })} autoCapitalize="characters" placeholder="KA01AB1234" />
            <T size={12} color={colors.muted}>{t("verify.docs_note")}</T>
            {err ? <T testID="verify-error" color={colors.error}>{err}</T> : null}
            <Btn testID="verify-submit-button" label={t("verify.submit")} onPress={submit} loading={busy === "v"} />
          </Card>
        ) : p.documents?.licence_no ? (
          <Card style={{ gap: 4 }}>
            <DocPhotos photos={p.documents?.photos ?? {}} editable={false} onUploaded={() => {}} />
            <T size={13}>{t("verify.legal_name")}: <T weight="700" size={13}>{p.documents.legal_name}</T></T>
            {p.documents.vehicle_name ? <T size={13}>{t("verify.vehicle_name")}: {p.documents.vehicle_name}</T> : null}
            <T size={13}>{t("verify.licence")}: {p.documents.licence_no}</T>
            <T size={13}>{t("verify.rc")}: {p.documents.rc_no}</T>
          </Card>
        ) : null}

        <Section title={t("vehicle.title")} right={!vOpen ? <Btn small variant="ghost" icon="add" label={t("vehicle.add")} onPress={() => setVOpen(true)} testID="vehicle-add-button" /> : null}>
          {p.vehicles.map((x: any) => (
            <Card key={x.vehicle_id} testID={`vehicle-${x.vehicle_id}`} style={{ flexDirection: "row", alignItems: "center", gap: space.md }}>
              <Ionicons name="car-sport" size={26} color={colors.brandPrimary} />
              <View style={{ flex: 1 }}>
                <T weight="800">{x.make} {x.model}</T>
                <T size={12} color={colors.muted}>{x.reg_no} · {x.vtype} · {x.seats} seats · {x.ac ? t("ride.ac") : t("ride.nonac")}</T>
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
                {VTYPES.map((x) => <Chip key={x} testID={`vehicle-type-${x}`} label={x.toUpperCase()} active={v.vtype === x} onPress={() => setV({ ...v, vtype: x })} />)}
              </View>
              <Field testID="vehicle-color" label={t("vehicle.color")} value={v.color} onChangeText={(x) => setV({ ...v, color: x })} />
              <Field testID="vehicle-reg" label={t("vehicle.reg")} value={v.reg_no} onChangeText={(x) => setV({ ...v, reg_no: x.toUpperCase() })} autoCapitalize="characters" />
              <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
                <T weight="600">{t("vehicle.seats")}</T>
                <Stepper testID="vehicle-seats" value={v.seats} onChange={(x) => setV({ ...v, seats: x })} />
              </View>
              <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
                <T weight="600">{t("vehicle.ac")}</T>
                <Switch testID="vehicle-ac-switch" value={v.ac} onValueChange={(x) => setV({ ...v, ac: x })} trackColor={{ true: colors.brandPrimary, false: colors.border }} />
              </View>
              <T size={13} weight="600" color={colors.muted}>{t("vehicle.luggage")}</T>
              <View style={{ flexDirection: "row", gap: space.sm }}>
                {["small", "medium", "large"].map((x) => <Chip key={x} testID={`vehicle-luggage-${x}`} label={t(`vehicle.${x}`)} active={v.luggage === x} onPress={() => setV({ ...v, luggage: x })} />)}
              </View>
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
