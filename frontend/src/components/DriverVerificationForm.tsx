import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { DOC_KINDS, DocPhotos } from "@/src/components/DocPhotos";
import { useToast } from "@/src/components/toast";
import { Btn, Card, Field, Header, Loading, T, radius, space } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

const EMPTY = { legal_name: "", vehicle_name: "", phone: "", licence_no: "", licence_expiry: "", rc_no: "" };

/** Upload the 4 verification photos, fill details (optionally AI pre-filled) and submit for review. */
export function DriverVerificationForm({ ai }: { ai: boolean }) {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t } = useI18n();
  const router = useRouter();
  const toast = useToast();
  const [photos, setPhotos] = useState<Record<string, string> | null>(null);
  const [f, setF] = useState(EMPTY);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const [aiDone, setAiDone] = useState(false);

  const load = useCallback(async () => {
    const r = await api("/driver/profile");
    setPhotos(r.documents?.photos ?? {});
  }, []);
  useFocusEffect(useCallback(() => { load().catch((e) => setErr(e.message)); }, [load]));

  if (!photos) return <View style={{ flex: 1, backgroundColor: colors.surface }}><Header title={ai ? "AI Verification" : "Manual Verification"} /><Loading /></View>;
  const missing = DOC_KINDS.filter((k) => !photos[k]);
  const canRead = !!photos.licence && !!photos.rc;

  const readWithAi = async () => {
    setBusy("ai");
    setErr("");
    try {
      const r = await api("/driver/ai-extract", { method: "POST" });
      setF((cur) => ({
        ...cur,
        legal_name: r.legal_name || cur.legal_name,
        vehicle_name: r.vehicle_name || cur.vehicle_name,
        licence_no: r.licence_no || cur.licence_no,
        licence_expiry: r.licence_expiry || cur.licence_expiry,
        rc_no: r.rc_no || cur.rc_no,
      }));
      setAiDone(true);
      toast("Details filled from your photos");
    } catch (e: any) {
      setErr(e.message);
    }
    setBusy("");
  };

  const submit = async () => {
    if (missing.length) return setErr(`Please upload: ${missing.map((k) => t(`verify.photo.${k}`)).join(", ")}`);
    if (f.legal_name.trim().length < 3) return setErr("Legal name required");
    if (f.vehicle_name.trim().length < 2) return setErr("Vehicle name required");
    if (!/^[6-9]\d{9}$/.test(f.phone)) return setErr("Valid 10-digit phone number required");
    if (f.licence_no.replace(/\s/g, "").length < 8) return setErr("Licence number required");
    if (!/^\d{2}-\d{2}-\d{4}$/.test(f.licence_expiry)) return setErr("Valid expiry date required (DD-MM-YYYY)");
    if (f.rc_no.replace(/\s/g, "").length < 6) return setErr("RC number required");
    setBusy("submit");
    setErr("");
    try {
      const r = await api("/driver/verification", { body: { ...f, licence_no: f.licence_no.replace(/\s/g, ""), rc_no: f.rc_no.replace(/\s/g, "") } });
      toast(t(`verify.status.${r.status}`));
      if (router.canGoBack()) router.back();
      else router.replace("/driver");
    } catch (e: any) {
      setErr(e.message);
    }
    setBusy("");
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title={ai ? "AI Verification" : "Manual Verification"} />
      <KeyboardAwareScrollView bottomOffset={24} keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: space.lg, gap: space.md, paddingBottom: insets.bottom + space.xl }}>
        <Card style={{ gap: space.md }}>
          <T weight="800">Upload your documents</T>
          <T size={12} color={colors.muted}>
            {ai ? "Add clear photos. AI then reads your licence and RC to fill the details for you." : "Add clear photos. Our team reviews them before approving you."}
          </T>
          <DocPhotos photos={photos} editable onUploaded={() => load().catch(() => {})} />
          <T testID="verify-photos-progress" size={12} weight="700" color={missing.length ? colors.muted : colors.success}>
            {DOC_KINDS.length - missing.length} of {DOC_KINDS.length} photos uploaded
          </T>
          {ai ? (
            <Btn testID="verify-ai-read-button" icon="sparkles" label={aiDone ? "Read again with AI" : "Fill details with AI"} onPress={readWithAi} loading={busy === "ai"} disabled={!canRead || !!busy} />
          ) : null}
        </Card>

        {ai && aiDone ? (
          <View testID="verify-ai-note" style={{ backgroundColor: colors.surfaceTertiary, padding: space.md, borderRadius: radius.md }}>
            <T size={12} color={colors.muted}>Please check the details below and correct anything AI got wrong before submitting.</T>
          </View>
        ) : null}

        <Card style={{ gap: space.md }}>
          <T weight="800">Document details</T>
          <Field testID="verify-legal-name" label="Legal Name" value={f.legal_name} onChangeText={(x) => setF({ ...f, legal_name: x })} />
          <Field testID="verify-vehicle-name" label="Vehicle Name" value={f.vehicle_name} onChangeText={(x) => setF({ ...f, vehicle_name: x })} placeholder="Maruti Suzuki Dzire" />
          <Field testID="verify-phone" label="Phone" value={f.phone} onChangeText={(x) => setF({ ...f, phone: x.replace(/\D/g, "") })} keyboardType="phone-pad" maxLength={10} />
          <Field testID="verify-licence-no" label="Licence Number" value={f.licence_no} onChangeText={(x) => setF({ ...f, licence_no: x.toUpperCase() })} autoCapitalize="characters" placeholder="KA0120200001234" />
          <Field testID="verify-licence-expiry" label="Licence Expiry" value={f.licence_expiry} onChangeText={(x) => setF({ ...f, licence_expiry: x })} placeholder="31-12-2035" maxLength={10} />
          <Field testID="verify-rc-no" label="RC Number" value={f.rc_no} onChangeText={(x) => setF({ ...f, rc_no: x.toUpperCase() })} autoCapitalize="characters" placeholder="KA01AB1234" />
        </Card>

        {err ? <T testID="verify-error" color={colors.error} weight="700">{err}</T> : null}
        <Btn testID="verify-submit-button" label="Submit for verification" onPress={submit} loading={busy === "submit"} disabled={!!busy && busy !== "submit"} />
        <Btn testID="verify-cancel-button" variant="ghost" label={t("common.cancel")} onPress={() => router.back()} />
      </KeyboardAwareScrollView>
    </View>
  );
}
