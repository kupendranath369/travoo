import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { DocFile, DocKind, DocPhotos } from "@/src/components/DocPhotos";
import { useAuth } from "@/src/auth";
import { useToast } from "@/src/components/toast";
import { Btn, Card, Field, Header, Loading, T, space } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

const EMPTY = { licence_no: "", rc_no: "", licence_expiry: "", vehicle_name: "" };
const DMY = /^\d{2}-\d{2}-\d{4}$/;
const realDate = (s: string) => {
  if (!DMY.test(s)) return false;
  const [d, m, y] = s.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  return dt.getFullYear() === y && dt.getMonth() === m - 1 && dt.getDate() === d;
};
const dmyMask = (x: string) => {
  const d = x.replace(/\D/g, "").slice(0, 8);
  return [d.slice(0, 2), d.slice(2, 4), d.slice(4, 8)].filter(Boolean).join("-");
};

/** Manual driver verification: 4 documents (licence front/back, Aadhaar, RC) + 4 typed details. Admin approves by hand. */
export function DriverVerificationForm() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t } = useI18n();
  const router = useRouter();
  const toast = useToast();
  const { user } = useAuth();
  const [prof, setProf] = useState<{ files: DocFile[]; kinds: DocKind[]; missing: string[] } | null>(null);
  const [f, setF] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [fieldErr, setFieldErr] = useState<Partial<Record<keyof typeof EMPTY, string>>>({});

  const load = useCallback(async () => {
    const r = await api("/driver/profile");
    setProf({ files: r.files ?? [], kinds: r.kinds ?? [], missing: r.missing ?? [] });
  }, []);
  useFocusEffect(useCallback(() => { load().catch((e) => setErr(e.message)); }, [load]));

  if (!prof) return <View style={{ flex: 1, backgroundColor: colors.surface }}><Header title={t("verify.title")} /><Loading /></View>;
  const missing = prof.missing;
  const labelOf = (k: string) => prof.kinds.find((x) => x.kind === k)?.label ?? k;
  const required = prof.kinds.filter((k) => k.required).length;
  const phone = user?.phone_e164 ? `+${user.phone_e164}` : user?.phone ?? "";
  const phoneOk = /^[6-9]\d{9}$/.test((user?.phone ?? "").replace(/\D/g, "").slice(-10));

  const submit = async () => {
    const fe: typeof fieldErr = {};
    if (f.licence_no.replace(/\s/g, "").length < 8) fe.licence_no = "Enter the licence number as printed (at least 8 characters)";
    if (f.rc_no.replace(/\s/g, "").length < 6) fe.rc_no = "Enter the RC (registration) number, e.g. KA01AB1234";
    if (!realDate(f.licence_expiry)) fe.licence_expiry = "Enter a real date as DD-MM-YYYY";
    if (f.vehicle_name.trim().length < 2) fe.vehicle_name = "Enter the vehicle make and model";
    setFieldErr(fe);
    if (missing.length) return setErr(`Please upload: ${missing.map(labelOf).join(", ")}`);
    if (Object.keys(fe).length) return setErr("Please fix the highlighted fields");
    if (!phoneOk) return setErr("Verify your mobile number in Profile first");
    setBusy(true);
    setErr("");
    try {
      const r = await api("/driver/verification", { body: { ...f, licence_no: f.licence_no.replace(/\s/g, ""), rc_no: f.rc_no.replace(/\s/g, "") } });
      toast(t(`verify.status.${r.status}`));
      if (router.canGoBack()) router.back();
      else router.replace("/driver");
    } catch (e: any) {
      setErr(e.message);
    }
    setBusy(false);
  };

  const fld = (k: keyof typeof EMPTY, label: string, extra: object) => (
    <View style={{ gap: 4 }}>
      <Field testID={`verify-${k.replace("_", "-")}`} label={label} value={f[k]} onChangeText={(x) => { setF({ ...f, [k]: k === "licence_expiry" ? dmyMask(x) : k === "vehicle_name" ? x : x.toUpperCase() }); setFieldErr({ ...fieldErr, [k]: undefined }); }} {...extra} />
      {fieldErr[k] ? <T testID={`verify-${k.replace("_", "-")}-error`} size={12} color={colors.error}>{fieldErr[k]}</T> : null}
    </View>
  );

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title={t("verify.title")} />
      <KeyboardAwareScrollView bottomOffset={24} keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: space.lg, gap: space.md, paddingBottom: insets.bottom + space.xl }}>
        <Card style={{ gap: space.md }}>
          <T weight="800">1. Upload documents</T>
          <T size={12} color={colors.muted}>Driving licence (front and back), Aadhaar card and vehicle RC. JPG, PNG or PDF. Documents are stored privately and only Travoo verification staff can open them.</T>
          <DocPhotos files={prof.files} kinds={prof.kinds} editable onChanged={() => load().catch(() => {})} />
          <T testID="verify-photos-progress" size={12} weight="700" color={missing.length ? colors.muted : colors.success}>
            {required - missing.length} of {required} required documents uploaded
          </T>
        </Card>

        <Card style={{ gap: space.md }}>
          <T weight="800">2. Enter details (as printed on your documents)</T>
          {fld("licence_no", "Driving Licence Number", { autoCapitalize: "characters", placeholder: "KA0120200001234" })}
          {fld("rc_no", "Vehicle RC Number", { autoCapitalize: "characters", placeholder: "KA01AB1234" })}
          {fld("licence_expiry", "Driving Licence Expiry Date", { placeholder: "DD-MM-YYYY", keyboardType: "number-pad", maxLength: 10 })}
          {fld("vehicle_name", "Vehicle Name", { placeholder: "Maruti Suzuki Dzire" })}
          <View testID="verify-registered-phone" style={{ flexDirection: "row", alignItems: "center", gap: space.sm }}>
            <T size={13} color={colors.muted} style={{ flex: 1 }}>{phoneOk ? `Registered mobile: ${phone}${user?.phone_verified ? " (verified)" : ""}` : "No mobile number on your account. Add it in Profile (Edit profile, or verify by OTP)."}</T>
            {!phoneOk ? <Btn small variant="ghost" testID="verify-add-phone" label="Add" onPress={() => router.push("/profile")} /> : null}
          </View>
        </Card>

        {err ? <T testID="verify-error" color={colors.error} weight="700">{err}</T> : null}
        <Btn testID="verify-submit-button" label="Submit for verification" onPress={submit} loading={busy} />
        <Btn testID="verify-cancel-button" variant="ghost" label={t("common.cancel")} onPress={() => router.back()} />
      </KeyboardAwareScrollView>
    </View>
  );
}
