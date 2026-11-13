import React, { useState } from "react";
import { Alert, Platform, View } from "react-native";

import { HomeLoc, Taluk, TalukPicker } from "@/src/components/TalukPicker";
import { Badge, Btn, Card, Chip, Field, Stepper, T, space } from "@/src/components/ui";
import { useTheme } from "@/src/theme";

export const SERVICE_LABEL: Record<string, string> = { rent: "Rent a Driver", book: "Book a Driver" };
export const RENT_OPTIONS = [["hourly", "Hourly"], ["half_day", "Half-day"], ["full_day", "Full-day"], ["multi_day", "Multiple days"], ["outstation", "Outstation"]] as const;
export const BOOK_OPTIONS = [["one_way", "One-way"], ["round_trip", "Round trip"], ["multi_day", "Multiple days"], ["outstation", "Outstation"]] as const;
export const VEHICLE_CATS = ["hatchback", "sedan", "suv", "muv", "van", "luxury", "other"];
export const TYPE_LABEL: Record<string, string> = Object.fromEntries([...RENT_OPTIONS, ...BOOK_OPTIONS, ["airport", "Airport"], ["custom", "Custom"]]);
export const STATUS_LABEL: Record<string, string> = { available: "Available", busy: "Busy", offline: "Offline" };

export const feeNote = (service?: string) => service === "book"
  ? "Driver fee plus vehicle charge for the driver's vehicle. Pay the driver directly."
  : "Driver's service fee for driving your car. Pay the driver directly.";

/** Ask before a destructive action (works on native and web). */
export function confirmAction(title: string, message: string, onYes: () => void) {
  if (Platform.OS === "web") {
    if (globalThis.confirm?.(`${title}\n\n${message}`)) onYes();
    return;
  }
  Alert.alert(title, message, [{ text: "No", style: "cancel" }, { text: "Yes", style: "destructive", onPress: onYes }]);
}

export type Area = Taluk & { sub_label?: string };
export type Vehicle = { vehicle_id?: string; name: string; reg_no: string; category: string; seats: number; day_rate: number; available: boolean };

/** Rent / Book service toggles; at least one stays on. */
export function ServicesPicker({ value, onChange, testPrefix = "svc" }: { value: string[]; onChange: (v: string[]) => void; testPrefix?: string }) {
  const { colors } = useTheme();
  const toggle = (s: string) => {
    const next = value.includes(s) ? value.filter((x) => x !== s) : [...value, s];
    if (next.length) onChange(next);
  };
  return (
    <View style={{ gap: space.sm }}>
      {(["rent", "book"] as const).map((s) => (
        <Card key={s} testID={`${testPrefix}-${s}`} onPress={() => toggle(s)} style={{ flexDirection: "row", alignItems: "center", gap: space.md, borderWidth: 2, borderColor: value.includes(s) ? colors.brandPrimary : colors.border }}>
          <View style={{ flex: 1 }}>
            <T weight="800">{SERVICE_LABEL[s].toUpperCase()}</T>
            <T size={12} color={colors.muted}>{s === "rent" ? "Drive the customer's own car" : "Provide your vehicle and drive it"}</T>
          </View>
          <Badge label={value.includes(s) ? "ON" : "OFF"} tone={value.includes(s) ? "success" : "muted"} />
        </Card>
      ))}
    </View>
  );
}

/** Extra taluks a driver serves (home taluk is always served). */
export function ServiceAreasEditor({ areas, onChange, homeCode, testPrefix = "areas" }: { areas: Area[]; onChange: (a: Area[]) => void; homeCode?: string | null; testPrefix?: string }) {
  const { colors } = useTheme();
  const [pick, setPick] = useState<HomeLoc>({ taluk: null, city: "", city_code: null, village_code: null, village_name: null });
  const add = () => {
    const tk = pick.taluk;
    if (!tk || tk.code === homeCode || areas.some((a) => a.code === tk.code)) return;
    onChange([...areas, tk]);
    setPick({ ...pick, taluk: null });
  };
  return (
    <View style={{ gap: space.sm }}>
      <T size={12} color={colors.muted}>You get requests for trips whose DESTINATION is your home taluk or any taluk below.</T>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
        {areas.length === 0 ? <T size={12} color={colors.muted}>No extra service areas yet</T> : null}
        {areas.map((a) => <Chip key={a.code} testID={`${testPrefix}-chip-${a.code}`} icon="close" label={`${a.name} · ${a.district_name}`} onPress={() => onChange(areas.filter((x) => x.code !== a.code))} />)}
      </View>
      <TalukPicker testPrefix={`${testPrefix}-pick`} value={pick} onChange={setPick} />
      <Btn small variant="outline" icon="add" testID={`${testPrefix}-add`} label="Add this taluk" disabled={!pick.taluk} onPress={add} style={{ alignSelf: "flex-start" }} />
    </View>
  );
}

const blank: Vehicle = { name: "", reg_no: "", category: "sedan", seats: 4, day_rate: 0, available: true };

/** Vehicles provided for Book a Driver. */
export function VehiclesEditor({ vehicles, onChange, testPrefix = "veh" }: { vehicles: Vehicle[]; onChange: (v: Vehicle[]) => void; testPrefix?: string }) {
  const { colors } = useTheme();
  const [v, setV] = useState<Vehicle>(blank);
  const [err, setErr] = useState("");
  const add = () => {
    if (v.name.trim().length < 2) return setErr("Vehicle name required");
    if (!/^[A-Z0-9]{6,12}$/.test(v.reg_no.replace(/[\s-]/g, "").toUpperCase())) return setErr("Enter a valid registration number");
    setErr("");
    onChange([...vehicles, { ...v, name: v.name.trim(), reg_no: v.reg_no.toUpperCase() }]);
    setV(blank);
  };
  return (
    <View style={{ gap: space.sm }}>
      {vehicles.map((x, i) => (
        <Card key={x.vehicle_id ?? `${x.reg_no}${i}`} testID={`${testPrefix}-item-${i}`} style={{ gap: space.xs }}>
          <T weight="800">{x.name} · {x.reg_no}</T>
          <T size={12} color={colors.muted}>{x.category.toUpperCase()} · {x.seats} passenger seats · ₹{x.day_rate}/day vehicle charge</T>
          <View style={{ flexDirection: "row", gap: space.sm }}>
            <Btn small variant={x.available ? "outline" : "primary"} testID={`${testPrefix}-avail-${i}`} label={x.available ? "Mark unavailable" : "Mark available"} onPress={() => onChange(vehicles.map((y, j) => (j === i ? { ...y, available: !y.available } : y)))} />
            <Btn small variant="ghost" testID={`${testPrefix}-remove-${i}`} label="Remove" onPress={() => onChange(vehicles.filter((_, j) => j !== i))} />
          </View>
          {!x.available ? <Badge label="Unavailable" tone="muted" /> : null}
        </Card>
      ))}
      {vehicles.length < 5 ? (
        <Card style={{ gap: space.sm }}>
          <T weight="700">Add a vehicle</T>
          <Field testID={`${testPrefix}-name`} label="Vehicle name" value={v.name} onChangeText={(name) => setV({ ...v, name })} placeholder="Toyota Innova Crysta" />
          <Field testID={`${testPrefix}-reg`} label="Registration number" value={v.reg_no} onChangeText={(reg_no) => setV({ ...v, reg_no: reg_no.toUpperCase() })} autoCapitalize="characters" placeholder="KA01AB1234" />
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space.sm }}>
            {VEHICLE_CATS.map((c) => <Chip key={c} testID={`${testPrefix}-cat-${c}`} label={c.toUpperCase()} active={v.category === c} onPress={() => setV({ ...v, category: c })} />)}
          </View>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
            <T weight="600">Passenger seats</T>
            <Stepper testID={`${testPrefix}-seats`} value={v.seats} max={20} onChange={(seats) => setV({ ...v, seats })} />
          </View>
          <Field testID={`${testPrefix}-rate`} label="Vehicle charge per day (₹, added to your driver fee)" value={v.day_rate ? String(v.day_rate) : ""} onChangeText={(s) => setV({ ...v, day_rate: Number(s.replace(/\D/g, "") || 0) })} keyboardType="number-pad" />
          {err ? <T color={colors.error} testID={`${testPrefix}-error`}>{err}</T> : null}
          <Btn small icon="add" testID={`${testPrefix}-add`} label="Add vehicle" onPress={add} />
        </Card>
      ) : null}
    </View>
  );
}

/** Yes/No preference row. */
export function Toggle({ label, value, onChange, testID }: { label: string; value: boolean; onChange: (v: boolean) => void; testID: string }) {
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm }}>
      <T weight="600" style={{ flex: 1 }}>{label}</T>
      <Chip testID={`${testID}-yes`} label="Yes" active={value} onPress={() => onChange(true)} />
      <Chip testID={`${testID}-no`} label="No" active={!value} onPress={() => onChange(false)} />
    </View>
  );
}
