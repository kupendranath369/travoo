import * as DocumentPicker from "expo-document-picker";
import * as ImagePicker from "expo-image-picker";
import React, { useState } from "react";
import { Platform, View } from "react-native";

import { API_BASE, api, getApiToken } from "@/src/api";
import { Btn, Card, Chip, Field, Stepper, T, space } from "@/src/components/ui";
import { useTheme } from "@/src/theme";
import { uploadWithProgress } from "@/src/utils/upload";

const TYPES = ["hatchback", "sedan", "suv", "muv"] as const;
const CAP: Record<string, number> = { hatchback: 3, sedan: 3, suv: 8, muv: 8 };

/** RC upload: images or PDF. On web the picker opens directly from the tap (Android Chrome blocks pickers opened after an await). */
function RcUpload({ fileId, onDone, testID }: { fileId?: string | null; onDone: (id: string) => void; testID: string }) {
  const { colors } = useTheme();
  const [pct, setPct] = useState<number | null>(null);
  const [err, setErr] = useState("");
  const send = async (f: { uri: string; name: string; mimeType: string }) => {
    setErr(""); setPct(0);
    try {
      const r = await uploadWithProgress(`${API_BASE}/driver/documents/vehicle_rc`, f, { headers: { Authorization: `Bearer ${getApiToken()}` }, onProgress: setPct });
      const body = JSON.parse(r.body || "{}");
      if (r.status >= 300) throw new Error(body.detail || `Upload failed (${r.status})`);
      onDone(body.file_id);
    } catch (e: any) { setErr(e.message); }
    setPct(null);
  };
  const photo = async () => {
    const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ["images"], quality: 0.7 });
    const a = r.assets?.[0];
    if (!r.canceled && a) send({ uri: a.uri, name: a.fileName || `rc_${Date.now()}.jpg`, mimeType: a.mimeType || "image/jpeg" });
  };
  const pdf = async () => {
    const r = await DocumentPicker.getDocumentAsync({ type: ["application/pdf", "image/*"], copyToCacheDirectory: Platform.OS !== "web" });
    const a = r.assets?.[0];
    if (!r.canceled && a) send({ uri: a.uri, name: a.name, mimeType: a.mimeType || "application/pdf" });
  };
  return (
    <View style={{ gap: space.xs }}>
      <T size={13} weight="600" color={colors.muted}>RC document</T>
      <View style={{ flexDirection: "row", gap: space.sm }}>
        <Btn small style={{ flex: 1 }} variant={fileId ? "outline" : "primary"} icon="image-outline" label={fileId ? "Replace photo" : "RC photo"} loading={pct !== null} onPress={photo} testID={`${testID}-photo`} />
        <Btn small style={{ flex: 1 }} variant="outline" icon="document-outline" label="PDF / file" onPress={pdf} testID={`${testID}-file`} />
      </View>
      {pct !== null ? <T size={12} color={colors.muted}>Uploading {Math.round(pct * 100)}%</T> : null}
      {fileId ? <T testID={`${testID}-ok`} size={12} weight="700" color={colors.success}>RC uploaded</T> : null}
      {err ? <T testID={`${testID}-error`} size={12} color={colors.error}>{err}</T> : null}
    </View>
  );
}

/** Add / edit a vehicle in the ONE shared vehicle list (carpool + local driver). forBook adds the commercial details. */
export function VehicleForm({ initial, forBook, onSaved, onCancel }: { initial?: any; forBook: boolean; onSaved: (v: any) => void; onCancel: () => void }) {
  const { colors } = useTheme();
  const [v, setV] = useState({ name: "", make: "", model: "", vtype: "sedan", reg_no: "", seats: 3, rc_file_id: null as string | null, permit_no: "",
    insurance_expiry: "", day_rate: 0, ...Object.fromEntries(Object.entries(initial ?? {}).filter(([, x]) => x != null)) });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: string, val: any) => setV((x: any) => ({ ...x, [k]: val }));
  const save = async () => {
    setErr("");
    if (forBook && (!v.rc_file_id || !v.permit_no.trim() || !/^\d{2}-\d{2}-\d{4}$/.test(v.insurance_expiry))) return setErr("Book a Car needs the RC, permit number and insurance expiry (DD-MM-YYYY)");
    setBusy(true);
    try {
      const body = { name: v.name.trim(), make: v.make.trim(), model: v.model.trim() || "-", vtype: v.vtype, reg_no: v.reg_no.trim(), seats: v.seats, rc_file_id: v.rc_file_id,
        permit_no: v.permit_no.trim(), insurance_expiry: v.insurance_expiry || null, day_rate: Number(v.day_rate) || 0 };
      const saved = initial?.vehicle_id ? await api(`/vehicles/${initial.vehicle_id}`, { method: "PUT", body }) : await api("/vehicles", { body });
      onSaved(saved);
    } catch (e: any) { setErr(e.message); }
    setBusy(false);
  };
  return (
    <Card testID="vehicle-form" style={{ gap: space.md }}>
      <T weight="800" size={16}>{initial?.vehicle_id ? "Edit vehicle" : "Add vehicle"}</T>
      <Field testID="vehicle-name" label="Vehicle name" placeholder="e.g. My white Ertiga" value={v.name} onChangeText={(x) => set("name", x)} maxLength={60} />
      <View style={{ flexDirection: "row", gap: space.sm }}>
        <View style={{ flex: 1, minWidth: 0 }}><Field testID="vehicle-make" label="Manufacturer" placeholder="Maruti" value={v.make} onChangeText={(x) => set("make", x)} /></View>
        <View style={{ flex: 1, minWidth: 0 }}><Field testID="vehicle-model" label="Model" placeholder="Ertiga" value={v.model === "-" ? "" : v.model} onChangeText={(x) => set("model", x)} /></View>
      </View>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
        {TYPES.map((t) => <Chip key={t} testID={`vehicle-type-${t}`} label={t.toUpperCase()} active={v.vtype === t} onPress={() => { set("vtype", t); set("seats", Math.min(v.seats, CAP[t])); }} />)}
      </View>
      <Field testID="vehicle-reg" label="Registration number" placeholder="KA01AB1234" autoCapitalize="characters" value={v.reg_no} onChangeText={(x) => set("reg_no", x)} maxLength={15} />
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
        <View><T weight="600">Passenger seats</T><T size={11} color={colors.muted}>Max {CAP[v.vtype]} for {v.vtype}, driver not counted</T></View>
        <Stepper testID="vehicle-seats" value={v.seats} max={CAP[v.vtype]} onChange={(n) => set("seats", n)} />
      </View>
      <RcUpload testID="vehicle-rc" fileId={v.rc_file_id} onDone={(id) => set("rc_file_id", id)} />
      {forBook ? (
        <>
          <Field testID="vehicle-permit" label="Commercial / tourist permit number" value={v.permit_no} onChangeText={(x) => set("permit_no", x)} maxLength={30} />
          <Field testID="vehicle-insurance" label="Insurance valid until (DD-MM-YYYY)" placeholder="31-12-2027" value={v.insurance_expiry ?? ""} onChangeText={(x) => set("insurance_expiry", x)} maxLength={10} keyboardType="numbers-and-punctuation" />
          <Field testID="vehicle-day-rate" label="Vehicle charge per day (₹)" value={String(v.day_rate || "")} onChangeText={(x) => set("day_rate", x.replace(/\D/g, ""))} keyboardType="number-pad" maxLength={5} />
          <T size={11} color={colors.muted}>Travoo checks the RC, permit and insurance before this vehicle can be used for Book a Car.</T>
        </>
      ) : null}
      {err ? <T testID="vehicle-form-error" size={13} color={colors.error}>{err}</T> : null}
      <View style={{ flexDirection: "row", gap: space.sm }}>
        <Btn style={{ flex: 1 }} testID="vehicle-save" label="Save vehicle" loading={busy} onPress={save} />
        <Btn variant="ghost" testID="vehicle-cancel" label="Cancel" onPress={onCancel} />
      </View>
    </Card>
  );
}
