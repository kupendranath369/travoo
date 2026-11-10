import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { DocFile, DocKind, DocPhotos } from "@/src/components/DocPhotos";
import { useAuth } from "@/src/auth";
import { useToast } from "@/src/components/toast";
import { Btn, Card, Field, Header, Loading, T, radius, space } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

const EMPTY = { vehicle_name: "", licence_no: "", licence_name: "", licence_dob: "", licence_issue: "", licence_expiry: "", vehicle_class: "", rc_no: "" };
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
const FIELD_LABEL: Record<string, string> = { licence_no: "Licence number", licence_name: "Name", licence_dob: "Date of birth", licence_issue: "Issue date", licence_expiry: "Expiry date", vehicle_class: "Vehicle class" };

/** Upload the verification documents; the licence photo is scanned to pre-fill details, the driver reviews them, admin approves. */
export function DriverVerificationForm({ ai }: { ai: boolean }) {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t } = useI18n();
  const router = useRouter();
  const toast = useToast();
  const { user } = useAuth();
  const [prof, setProf] = useState<{ files: DocFile[]; kinds: DocKind[]; missing: string[] } | null>(null);
  const [f, setF] = useState(EMPTY);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const [aiDone, setAiDone] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [scanMsg, setScanMsg] = useState<{ tone: "ok" | "warn"; text: string } | null>(null);
  const [scannedId, setScannedId] = useState<string | null>(null);

  const load = useCallback(async () => {
    const r = await api("/driver/profile");
    setProf({ files: r.files ?? [], kinds: r.kinds ?? [], missing: r.missing ?? [] });
  }, []);
  useFocusEffect(useCallback(() => { load().catch((e) => setErr(e.message)); }, [load]));

  const licFile = prof?.files.find((x) => x.kind === "licence_front") ?? prof?.files.find((x) => x.kind === "licence");

  const scan = useCallback(async () => {
    setExtracting(true);
    setErr("");
    setScanMsg(null);
    try {
      const r = await api("/driver/ai-extract", { method: "POST" });
      // fill only what was read; never invent missing values
      setF((cur) => {
        const next = { ...cur };
        (Object.keys(EMPTY) as (keyof typeof EMPTY)[]).forEach((k) => { if (r[k]) next[k] = r[k]; });
        return next;
      });
      setAiDone(true);
      if (r.unclear) setScanMsg({ tone: "warn", text: "We couldn't read your licence clearly. Upload a sharper, well-lit photo of the front, or type the details below." });
      else if (r.missing?.length) setScanMsg({ tone: "warn", text: `Details filled from your licence. Not found: ${r.missing.map((k: string) => FIELD_LABEL[k]).join(", ")} — please add them if printed on your licence.` });
      else setScanMsg({ tone: "ok", text: "Details filled from your licence. Please check every field before submitting." });
    } catch (e: any) {
      setScanMsg({ tone: "warn", text: e.message || "We couldn't scan the licence. Upload another photo or type the details." });
    }
    setExtracting(false);
  }, []);

  // Scan automatically only when a NEW licence (front) photo is uploaded on this screen
  useEffect(() => {
    if (!prof) return;
    if (scannedId === null) {
      setScannedId(licFile?.file_id ?? "");
      return;
    }
    if (!ai || !licFile || licFile.file_id === scannedId || extracting) return;
    setScannedId(licFile.file_id);
    if (licFile.content_type?.startsWith("image/")) scan();
  }, [ai, prof, licFile, scannedId, extracting, scan]);

  if (!prof) return <View style={{ flex: 1, backgroundColor: colors.surface }}><Header title={ai ? "AI Verification" : "Manual Verification"} /><Loading /></View>;
  const missing = prof.missing;
  const labelOf = (k: string) => prof.kinds.find((x) => x.kind === k)?.label ?? k;
  const required = prof.kinds.filter((k) => k.required).length;
  const phoneOk = /^[6-9]\d{9}$/.test((user?.phone ?? "").replace(/\D/g, "").slice(-10));

  const submit = async () => {
    if (missing.length) return setErr(`Please upload: ${missing.map(labelOf).join(", ")}`);
    if (!phoneOk) return setErr("Add your 10-digit mobile number in Profile → Edit profile first");
    if (f.vehicle_name.trim().length < 2) return setErr("Vehicle name required");
    if (f.licence_no.replace(/\s/g, "").length < 8) return setErr("Licence number required");
    if (f.licence_name.trim().length < 2) return setErr("Name on licence required");
    if (!realDate(f.licence_expiry)) return setErr("Valid expiry date required (DD-MM-YYYY)");
    if (f.licence_dob && !realDate(f.licence_dob)) return setErr("Date of birth must be a real date (DD-MM-YYYY)");
    if (f.licence_issue && !realDate(f.licence_issue)) return setErr("Issue date must be a real date (DD-MM-YYYY)");
    if (f.vehicle_class.trim().length < 2) return setErr("Vehicle class required (e.g. LMV)");
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
            {ai ? "Add clear photos. Your licence is scanned automatically to fill in the details — you can correct them before submitting. Our team still checks everything before approval." : "Add clear photos. Our team reviews them before approving you."}
          </T>
          <DocPhotos files={prof.files} kinds={prof.kinds} editable onChanged={() => load().catch(() => {})} />
          <T testID="verify-photos-progress" size={12} weight="700" color={missing.length ? colors.muted : colors.success}>
            {required - missing.length} of {required} required documents uploaded
          </T>
          {extracting ? (
            <View testID="verify-scanning" style={{ flexDirection: "row", alignItems: "center", gap: space.sm, paddingVertical: space.sm }}>
              <ActivityIndicator size="small" color={colors.brandPrimary} />
              <T size={13} color={colors.muted}>Scanning your licence…</T>
            </View>
          ) : null}
          {ai && !extracting && licFile ? (
            <Btn testID="verify-ai-read-button" variant="outline" icon="scan-outline" label={aiDone ? "Scan licence again" : "Scan licence"} onPress={scan} disabled={!!busy} />
          ) : null}
        </Card>

        {scanMsg ? (
          <View testID="verify-scan-message" style={{ backgroundColor: scanMsg.tone === "ok" ? colors.surfaceTertiary : colors.accentSoft, padding: space.md, borderRadius: radius.md }}>
            <T size={13} weight="600" color={scanMsg.tone === "ok" ? colors.onSurface : colors.brandTertiary}>{scanMsg.text}</T>
          </View>
        ) : null}

        <Card style={{ gap: space.md }}>
          <T weight="800">Licence details</T>
          <Field testID="verify-licence-no" label="Licence Number" value={f.licence_no} onChangeText={(x) => setF({ ...f, licence_no: x.toUpperCase() })} autoCapitalize="characters" placeholder="KA0120200001234" />
          <Field testID="verify-licence-name" label="Name on licence" value={f.licence_name} onChangeText={(x) => setF({ ...f, licence_name: x })} autoCapitalize="words" />
          <View style={{ flexDirection: "row", gap: space.sm }}>
            <View style={{ flex: 1 }}><Field testID="verify-licence-dob" label="Date of birth" value={f.licence_dob} onChangeText={(x) => setF({ ...f, licence_dob: dmyMask(x) })} placeholder="DD-MM-YYYY" keyboardType="number-pad" maxLength={10} /></View>
            <View style={{ flex: 1 }}><Field testID="verify-licence-issue" label="Issue date" value={f.licence_issue} onChangeText={(x) => setF({ ...f, licence_issue: dmyMask(x) })} placeholder="DD-MM-YYYY" keyboardType="number-pad" maxLength={10} /></View>
          </View>
          <Field testID="verify-licence-expiry" label="Licence Expiry" value={f.licence_expiry} onChangeText={(x) => setF({ ...f, licence_expiry: dmyMask(x) })} placeholder="DD-MM-YYYY" keyboardType="number-pad" maxLength={10} />
          <Field testID="verify-vehicle-class" label="Vehicle class" value={f.vehicle_class} onChangeText={(x) => setF({ ...f, vehicle_class: x.toUpperCase() })} autoCapitalize="characters" placeholder="LMV, MCWG" />
        </Card>

        <Card style={{ gap: space.md }}>
          <T weight="800">Vehicle details</T>
          <Field testID="verify-vehicle-name" label="Vehicle Name" value={f.vehicle_name} onChangeText={(x) => setF({ ...f, vehicle_name: x })} placeholder="Maruti Suzuki Dzire" />
          <Field testID="verify-rc-no" label="RC Number" value={f.rc_no} onChangeText={(x) => setF({ ...f, rc_no: x.toUpperCase() })} autoCapitalize="characters" placeholder="KA01AB1234" />
          <View testID="verify-registered-phone" style={{ flexDirection: "row", alignItems: "center", gap: space.sm }}>
            <T size={13} color={colors.muted} style={{ flex: 1 }}>{phoneOk ? `Registered mobile: ${user?.phone} (used for verification)` : "No mobile number on your account. Add it in Profile → Edit profile."}</T>
            {!phoneOk ? <Btn small variant="ghost" testID="verify-add-phone" label="Add" onPress={() => router.push("/profile")} /> : null}
          </View>
        </Card>

        {err ? <T testID="verify-error" color={colors.error} weight="700">{err}</T> : null}
        <Btn testID="verify-submit-button" label="Submit for verification" onPress={submit} loading={busy === "submit"} disabled={!!busy && busy !== "submit"} />
        <Btn testID="verify-cancel-button" variant="ghost" label={t("common.cancel")} onPress={() => router.back()} />
      </KeyboardAwareScrollView>
    </View>
  );
}
