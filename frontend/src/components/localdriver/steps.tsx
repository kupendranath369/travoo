import Ionicons from "@react-native-vector-icons/ionicons";
import { useRouter } from "expo-router";
import React, { useState } from "react";
import { Pressable, View } from "react-native";

import { api, Loc, pictureUrl } from "@/src/api";
import { DocPhotos } from "@/src/components/DocPhotos";
import { LocationField } from "@/src/components/LocationField";
import { float, ITEM_LABEL, LanguageSelect, ServiceCard } from "@/src/components/localdriver/parts";
import { VehicleForm } from "@/src/components/localdriver/VehicleForm";
import { VehicleRow } from "@/src/components/localdriver/VehicleRow";
import { Taluk, TalukPicker } from "@/src/components/TalukPicker";
import { Avatar, Badge, Btn, Card, Field, T, radius, space } from "@/src/components/ui";
import { useTheme } from "@/src/theme";
import { useOtpEnabled } from "@/src/useOtp";

export type Draft = { place: Loc | null; taluk: Taluk | null; languages: string[]; licence_no: string; licence_expiry: string; services: string[]; vehicle_ids: string[] };

const Flag = ({ k, items }: { k: string; items: string[] }) => items.includes(k) ? <Badge testID={`pro-flag-${k}`} icon="alert-circle" label={`Fix: ${ITEM_LABEL[k]}`} tone="error" /> : null;

export function StepBasic({ me, d, set, items }: { me: any; d: Draft; set: (p: Partial<Draft>) => void; items: string[] }) {
  const { colors } = useTheme();
  const router = useRouter();
  const [finding, setFinding] = useState(false);
  const [manual, setManual] = useState(false);
  const otpOn = useOtpEnabled();
  const p = me.personal;
  const pickPlace = async (l: Loc) => {
    set({ place: l });
    setFinding(true);
    try {
      const r = await api(`/hire/identify-taluk?loc_id=${encodeURIComponent(l.loc_id)}&pickup=${encodeURIComponent(l.name)}`);
      if (r.subdistrict) { set({ place: l, taluk: r.subdistrict }); setManual(false); } else { set({ place: l, taluk: null }); setManual(true); }
    } catch { setManual(true); }
    setFinding(false);
  };
  return (
    <View style={{ gap: space.lg }}>
      <Card testID="pro-personal-card" style={[float, { flexDirection: "row", gap: space.md, alignItems: "center", borderWidth: 0 }]}>
        <Avatar name={p.name} uri={pictureUrl(p.picture)} size={56} />
        <View style={{ flex: 1, gap: 2 }}>
          <T weight="800" size={16}>{p.name}</T>
          <T size={12} color={colors.muted}>{p.phone || "No mobile number"} · {p.dob || "DOB not set"} · {p.gender ? p.gender[0].toUpperCase() + p.gender.slice(1) : "Gender not set"}</T>
          <T size={11} color={colors.muted}>From your Travoo profile</T>
        </View>
        <Pressable testID="pro-edit-profile" onPress={() => router.push("/profile")} hitSlop={10}><Ionicons name="create-outline" size={20} color={colors.brandTertiary} /></Pressable>
      </Card>
      {otpOn && !p.phone_ok ? <T testID="pro-phone-warning" size={13} color={colors.error}>Add your mobile number in Profile before submitting.</T> : null}
      <View style={{ gap: space.sm }}>
        <T weight="800">Home location</T>
        <Flag k="home" items={items} />
        <LocationField testID="pro-home-place" label="Village, town or city" value={d.place} onChange={pickPlace} />
        {finding ? <T size={12} color={colors.muted}>Finding your taluk…</T> : null}
        {d.taluk && !manual ? (
          <View testID="pro-home-taluk" style={{ flexDirection: "row", alignItems: "center", gap: space.sm, padding: space.md, borderRadius: radius.md, backgroundColor: colors.accentSoft }}>
            <Ionicons name="location" size={18} color={colors.brandTertiary} />
            <T size={13} weight="700" style={{ flex: 1 }}>{d.taluk.name} {d.taluk.sub_label ?? "Taluk"}, {d.taluk.district_name}, {d.taluk.state_name}</T>
            <Pressable testID="pro-home-taluk-change" onPress={() => setManual(true)}><T size={12} weight="700" color={colors.brandPrimary}>Change</T></Pressable>
          </View>
        ) : null}
        {manual || (!d.taluk && !d.place) ? (
          <TalukPicker testPrefix="pro-home" value={{ taluk: d.taluk, city: "", city_code: null, village_code: null, village_name: null }} onChange={(v) => set({ taluk: v.taluk })} />
        ) : null}
      </View>
      <View style={{ gap: space.sm }}>
        <T weight="800">Languages you speak</T>
        <Flag k="languages" items={items} />
        <LanguageSelect testPrefix="pro-lang" value={d.languages} onChange={(languages) => set({ languages })} />
      </View>
    </View>
  );
}

export function StepDocs({ me, d, set, items, reload }: { me: any; d: Draft; set: (p: Partial<Draft>) => void; items: string[]; reload: () => void }) {
  const { colors } = useTheme();
  const reuse = me.docs_locked && !me.missing.length;
  return (
    <View style={{ gap: space.lg }}>
      {reuse ? (
        <View testID="pro-docs-reused" style={{ flexDirection: "row", gap: space.sm, padding: space.md, borderRadius: radius.md, backgroundColor: colors.successSoft }}>
          <Ionicons name="shield-checkmark" size={20} color={colors.success} />
          <T size={13} style={{ flex: 1 }}>Using the documents you already submitted in Carpool Driver Verification. No need to upload again.</T>
        </View>
      ) : <T size={13} color={colors.muted}>Driving licence (front and back) and Aadhaar front only. Clear photos, no glare.</T>}
      {["licence_front", "licence_back", "id_proof"].map((k) => <Flag key={k} k={k} items={items} />)}
      <DocPhotos files={me.files} kinds={me.kinds} editable={!me.docs_locked || me.missing.length > 0 || items.some((k) => ["licence_front", "licence_back", "id_proof"].includes(k))} onChanged={reload} />
      {me.licence_on_file && !items.includes("licence_no") ? (
        <Card testID="pro-licence-on-file" style={{ gap: 2 }}>
          <T weight="700">Licence {me.licence_masked}</T>
          <T size={12} color={colors.muted}>Valid until {me.licence_expiry_on_file} · from Carpool Driver Verification</T>
        </Card>
      ) : (
        <>
          <Flag k="licence_no" items={items} />
          <Field testID="pro-licence-no" label="Driving licence number" placeholder="KA0120201234567" autoCapitalize="characters" value={d.licence_no} onChangeText={(x) => set({ licence_no: x })} maxLength={20} />
          <Flag k="licence_expiry" items={items} />
          <Field testID="pro-licence-expiry" label="Licence valid until (DD-MM-YYYY)" placeholder="31-12-2030" value={d.licence_expiry} onChangeText={(x) => set({ licence_expiry: x })} maxLength={10} keyboardType="numbers-and-punctuation" />
        </>
      )}
    </View>
  );
}

export function StepServices({ me, d, set, items, reload }: { me: any; d: Draft; set: (p: Partial<Draft>) => void; items: string[]; reload: () => void }) {
  const { colors } = useTheme();
  const [form, setForm] = useState<any>(null);
  const toggle = (s: string) => set({ services: d.services.includes(s) ? d.services.filter((x) => x !== s) : [...d.services, s] });
  const book = d.services.includes("book");
  return (
    <View style={{ gap: space.lg }}>
      <View style={{ flexDirection: "row", gap: space.md }}>
        <ServiceCard testID="pro-service-rent" icon="key-outline" title="Rent a Driver" desc="Drive the customer's own vehicle. No vehicle needed." active={d.services.includes("rent")} onPress={() => toggle("rent")} />
        <ServiceCard testID="pro-service-book" icon="car-sport-outline" title="Book a Car" desc="You provide the vehicle and drive." active={book} onPress={() => toggle("book")} note="Approved vehicle required" />
      </View>
      {book ? (
        <View testID="pro-book-vehicles" style={{ gap: space.sm }}>
          <T weight="800">Vehicles for Book a Car</T>
          <Flag k="vehicles" items={items} />
          {me.vehicles.length ? <T size={12} color={colors.muted}>Select from your vehicle list (shared with Carpool).</T> : null}
          {me.vehicles.map((v: any) => (
            <VehicleRow key={v.vehicle_id} v={v} selected={d.vehicle_ids.includes(v.vehicle_id)} onEdit={() => setForm(v)}
              onSelect={() => set({ vehicle_ids: d.vehicle_ids.includes(v.vehicle_id) ? d.vehicle_ids.filter((x) => x !== v.vehicle_id) : [...d.vehicle_ids, v.vehicle_id] })} />
          ))}
          {form ? (
            <VehicleForm initial={form.vehicle_id ? form : undefined} forBook onCancel={() => setForm(null)}
              onSaved={(v) => { setForm(null); set({ vehicle_ids: [...new Set([...d.vehicle_ids, v.vehicle_id])] }); reload(); }} />
          ) : <Btn testID="pro-add-vehicle" variant="outline" icon="add" label="Add vehicle" onPress={() => setForm({})} />}
        </View>
      ) : null}
    </View>
  );
}
