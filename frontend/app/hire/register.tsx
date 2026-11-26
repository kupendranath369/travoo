import Ionicons from "@react-native-vector-icons/ionicons";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { float, ITEM_LABEL, Progress, PRO_STATUS } from "@/src/components/localdriver/parts";
import { Draft, StepBasic, StepDocs, StepServices } from "@/src/components/localdriver/steps";
import { useToast } from "@/src/components/toast";
import { Badge, Btn, Card, ErrorBox, Header, Loading, T, space } from "@/src/components/ui";
import { useTheme } from "@/src/theme";

const LABELS = ["Basic Info", "Documents", "Service & Vehicle"];

function StatusView({ me, onFix }: { me: any; onFix: () => void }) {
  const { colors } = useTheme();
  const router = useRouter();
  const p = me.profile;
  const st = PRO_STATUS[p.status] ?? PRO_STATUS.under_review;
  const fix = p.status === "rejected" || p.status === "resubmit";
  return (
    <View style={{ gap: space.lg }}>
      <Card testID="pro-status-card" style={[float, { alignItems: "center", gap: space.md, paddingVertical: space.xl, borderWidth: 0 }]}>
        <View style={{ width: 72, height: 72, borderRadius: 36, backgroundColor: colors.accentSoft, alignItems: "center", justifyContent: "center" }}>
          <Ionicons name={st.icon} size={36} color={st.tone === "success" ? colors.success : st.tone === "error" ? colors.error : colors.brandTertiary} />
        </View>
        <Badge testID="pro-status-badge" label={st.label} tone={st.tone} />
        <T center size={14} color={colors.muted}>{st.text}</T>
      </Card>
      {fix && p.admin_note ? (
        <Card testID="pro-admin-reason" style={{ gap: space.xs }}>
          <T weight="800">Reason from Travoo</T>
          <T size={13}>{p.admin_note}</T>
          {(p.resubmit_items ?? []).map((k: string) => <T key={k} size={13} color={colors.error}>• {ITEM_LABEL[k] ?? k}</T>)}
        </Card>
      ) : null}
      <Card testID="pro-details-card" style={{ gap: 4 }}>
        <T weight="800">Verification details</T>
        <T size={13}>Home: {p.home?.subdistrict_name} {p.home?.sub_label}, {p.home?.district_name}</T>
        <T size={13}>Languages: {(p.languages ?? []).join(", ")}</T>
        <T size={13}>Licence: {p.licence_no} · valid until {p.licence_expiry}</T>
        <T size={13}>Services: {(p.services ?? []).map((s: string) => (s === "book" ? "Book a Car" : "Rent a Driver")).join(" + ")}</T>
      </Card>
      {fix ? <Btn testID="pro-fix-button" icon="create-outline" label="Fix and resubmit" onPress={onFix} /> : null}
      {p.status === "approved" ? <Btn testID="pro-open-dashboard" label="Open Local Driver Dashboard" onPress={() => router.replace("/hire/driver")} /> : null}
    </View>
  );
}

export default function LocalDriverRegister() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const router = useRouter();
  const toast = useToast();
  const { view, service } = useLocalSearchParams<{ view?: string; service?: string }>();
  const [me, setMe] = useState<any>(null);
  const [err, setErr] = useState("");
  const [editing, setEditing] = useState(false);
  const [step, setStep] = useState(0);
  const [stepErr, setStepErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [d, setD] = useState<Draft>({ place: null, taluk: null, languages: [], licence_no: "", licence_expiry: "", services: service === "both" ? ["rent", "book"] : service === "book" ? ["book"] : ["rent"], vehicle_ids: [] });
  const set = (p: Partial<Draft>) => { setStepErr(""); setD((x) => ({ ...x, ...p })); };

  const load = useCallback(async () => {
    try {
      const r = await api("/pro/me");
      setMe(r);
      const p = r.profile;
      if (p?.status === "approved" && view !== "details") return router.replace("/hire/driver");
      if (p) {
        setD((x) => ({ ...x, languages: x.languages.length ? x.languages : p.languages ?? [], services: p.services ?? ["rent"], vehicle_ids: x.vehicle_ids.length ? x.vehicle_ids : p.vehicle_ids ?? [],
          licence_expiry: x.licence_expiry || p.licence_expiry || "",
          taluk: x.taluk ?? (p.home ? { code: p.home.subdistrict_code, name: p.home.subdistrict_name, district_code: p.home.district_code, district_name: p.home.district_name,
            state_code: p.home.state_code, state_name: p.home.state_name, sub_label: p.home.sub_label } : null) }));
      }
    } catch (e: any) { setErr(e.message); }
  }, [router, view]);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  if (err) return <View style={{ flex: 1 }}><Header title="Local Driver" /><ErrorBox message={err} onRetry={load} /></View>;
  if (!me) return <View style={{ flex: 1 }}><Header title="Local Driver" /><Loading /></View>;
  const items: string[] = me.profile?.resubmit_items ?? [];
  const showStatus = me.profile && !editing && !(me.profile.status === "none");

  const check = () => {
    if (step === 0) {
      if (!d.taluk) return "Choose your home location (taluk)";
      if (!d.languages.length) return "Select at least one language";
    }
    if (step === 1) {
      if (me.missing.length) return "Upload your licence front, licence back and Aadhaar front";
      const since = me.profile?.reviewed_at ? new Date(me.profile.reviewed_at).getTime() : 0;
      const stale = items.filter((k) => ["licence_front", "licence_back", "id_proof"].includes(k) && !me.files.some((f: any) => f.kind === k && new Date(f.created_at).getTime() > since));
      if (since && stale.length) return "Please upload a new photo for the items marked 'Fix'";
      if (!me.licence_on_file || items.includes("licence_no")) {
        if (d.licence_no.replace(/\s/g, "").length < 8 && !me.profile?.licence_no) return "Enter your driving licence number";
        if (!/^\d{2}-\d{2}-\d{4}$/.test(d.licence_expiry)) return "Enter licence expiry as DD-MM-YYYY";
      }
    }
    if (step === 2) {
      if (!d.services.length) return "Choose at least one service";
      if (d.services.includes("book") && !d.vehicle_ids.length) return "Add or select at least one vehicle for Book a Car";
    }
    return "";
  };
  const next = async () => {
    const e = check();
    setStepErr(e);
    if (e) return;
    if (step < 2) return setStep(step + 1);
    setBusy(true);
    try {
      const r = await api("/pro/register", { body: { home: { subdistrict_code: d.taluk!.code, city: d.place?.name ?? "", place: d.place ? { loc_id: d.place.loc_id, name: d.place.name, lat: d.place.lat, lng: d.place.lng, district: d.place.district ?? "", state: d.place.state ?? "", type: "place" } : null },
        languages: d.languages, licence_no: d.licence_no.trim() || null, licence_expiry: d.licence_expiry || null, services: d.services, vehicle_ids: d.services.includes("book") ? d.vehicle_ids : [] } });
      toast(r.status === "approved" ? "Approved — welcome!" : "Submitted for verification");
      setEditing(false);
      setStep(0);
      await load();
    } catch (e: any) { setStepErr(e.message); }
    setBusy(false);
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title="Driver Registration" />
      <KeyboardAwareScrollView bottomOffset={24} contentContainerStyle={{ padding: space.lg, gap: space.lg, paddingBottom: insets.bottom + space.xxl }}>
        {showStatus ? <StatusView me={me} onFix={() => { setEditing(true); setStep(0); }} /> : (
          <>
            <Progress step={step} labels={LABELS} />
            <T testID="pro-step-title" size={22} weight="800">{["Basic Information", "Document Verification", "Select Services"][step]}</T>
            {step === 0 ? <StepBasic me={me} d={d} set={set} items={items} /> : step === 1 ? <StepDocs me={me} d={d} set={set} items={items} reload={load} /> : <StepServices me={me} d={d} set={set} items={items} reload={load} />}
            {stepErr ? <T testID="pro-error" color={colors.error}>{stepErr}</T> : null}
            <View style={{ flexDirection: "row", gap: space.sm }}>
              {step > 0 ? <Btn testID="pro-back-button" variant="outline" icon="arrow-back" label="Back" onPress={() => { setStepErr(""); setStep(step - 1); }} /> : null}
              <Btn style={{ flex: 1 }} variant={step === 2 ? "primary" : "navy"} testID={step === 2 ? "pro-submit-button" : "pro-next-button"} icon={step === 2 ? "shield-checkmark-outline" : "arrow-forward"}
                label={step === 2 ? "Submit for Verification" : "Next"} loading={busy} onPress={next} />
            </View>
          </>
        )}
      </KeyboardAwareScrollView>
    </View>
  );
}
