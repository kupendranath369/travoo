import Ionicons from "@react-native-vector-icons/ionicons";
import React, { useEffect, useState } from "react";
import { FlatList, Modal, Pressable, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { Btn, T, radius, space } from "@/src/components/ui";
import { useTheme } from "@/src/theme";

export type Taluk = { code: string; name: string; district_code: string; district_name: string; state_code: string; state_name: string; sub_label?: string };
export type HomeLoc = { taluk: Taluk | null; city: string; city_code: string | null; village_code: string | null; village_name: string | null };
type Item = { code: string; name: string; sub?: string };

/** Searchable list in a full-screen modal; `remote` re-queries the server as the user types (villages). */
function PickerModal({ visible, title, load, remote, allowCustom, onPick, onClose }: {
  visible: boolean; title: string; load: (q: string) => Promise<Item[]>; remote?: boolean; allowCustom?: boolean; onPick: (i: Item | { code: null; name: string }) => void; onClose: () => void;
}) {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const [q, setQ] = useState("");
  const [items, setItems] = useState<Item[] | null>(null);
  useEffect(() => { if (visible) { setQ(""); setItems(null); load("").then(setItems).catch(() => setItems([])); } }, [visible]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!visible || !remote) return;
    const h = setTimeout(() => load(q).then(setItems).catch(() => {}), 250);
    return () => clearTimeout(h);
  }, [q]); // eslint-disable-line react-hooks/exhaustive-deps
  const shown = remote ? items ?? [] : (items ?? []).filter((i) => i.name.toLowerCase().includes(q.trim().toLowerCase()));
  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm, padding: space.md }}>
          <Pressable testID="picker-close" onPress={onClose} hitSlop={8} style={{ width: 44, height: 44, alignItems: "center", justifyContent: "center" }}><Ionicons name="close" size={24} color={colors.onSurface} /></Pressable>
          <T size={18} weight="800" style={{ flex: 1 }}>{title}</T>
        </View>
        <View style={{ marginHorizontal: space.lg, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, flexDirection: "row", alignItems: "center", paddingHorizontal: space.md, height: 48 }}>
          <Ionicons name="search" size={18} color={colors.muted} />
          <TextInput testID="picker-search" value={q} onChangeText={setQ} placeholder="Search" placeholderTextColor={colors.muted} autoFocus style={{ flex: 1, marginLeft: space.sm, color: colors.onSurface, fontSize: 16 }} />
        </View>
        <FlatList
          data={shown}
          keyExtractor={(i) => i.code}
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={{ paddingHorizontal: space.lg, paddingTop: space.sm, paddingBottom: insets.bottom + space.xl }}
          ListHeaderComponent={allowCustom && q.trim().length >= 2 ? (
            <Pressable testID="picker-use-typed" onPress={() => onPick({ code: null, name: q.trim() })} style={{ paddingVertical: space.md, borderBottomWidth: 1, borderBottomColor: colors.divider }}>
              <T weight="700" color={colors.brandPrimary}>Use “{q.trim()}”</T>
            </Pressable>
          ) : undefined}
          ListEmptyComponent={<T color={colors.muted} style={{ paddingVertical: space.lg }}>{items === null ? "Loading…" : "No matches"}</T>}
          renderItem={({ item }) => (
            <Pressable testID={`picker-item-${item.code}`} onPress={() => onPick(item)} style={{ minHeight: 48, justifyContent: "center", paddingVertical: space.md, paddingHorizontal: space.xs, borderBottomWidth: 1, borderBottomColor: colors.divider }}>
              <T weight="600">{item.name}</T>
              {item.sub ? <T size={12} color={colors.muted}>{item.sub}</T> : null}
            </Pressable>
          )}
        />
      </View>
    </Modal>
  );
}

function Row({ testID, label, value, disabled, onPress }: { testID: string; label: string; value?: string | null; disabled?: boolean; onPress: () => void }) {
  const { colors } = useTheme();
  return (
    <Pressable testID={testID} disabled={disabled} onPress={onPress} style={{ minHeight: 52, flexDirection: "row", alignItems: "center", gap: space.sm, borderBottomWidth: 1, borderBottomColor: colors.divider, opacity: disabled ? 0.5 : 1 }}>
      <View style={{ flex: 1 }}>
        <T size={12} color={colors.muted}>{label}</T>
        <T weight="700" color={value ? colors.onSurface : colors.muted}>{value || "Select"}</T>
      </View>
      <Ionicons name="chevron-down" size={18} color={colors.muted} />
    </Pressable>
  );
}

/** State → District → Taluk/Tehsil/Mandal → (City/Town → Village) using the Govt. LGD directory. */
export function TalukPicker({ value, onChange, withCity = false, testPrefix = "taluk" }: { value: HomeLoc; onChange: (v: HomeLoc) => void; withCity?: boolean; testPrefix?: string }) {
  const [open, setOpen] = useState<"state" | "district" | "taluk" | "city" | "village" | null>(null);
  const [state, setState] = useState<{ code: string; name: string; sub_label: string } | null>(null);
  const [district, setDistrict] = useState<{ code: string; name: string } | null>(null);
  const tk = value.taluk;
  const st = state ?? (tk ? { code: tk.state_code, name: tk.state_name, sub_label: tk.sub_label ?? "Taluk" } : null);
  const ds = district ?? (tk ? { code: tk.district_code, name: tk.district_name } : null);
  const subLabel = st?.sub_label ?? "Taluk / Sub-district";
  const reset = { city: "", city_code: null, village_code: null, village_name: null };
  return (
    <View>
      <Row testID={`${testPrefix}-state`} label="State / Union Territory" value={st?.name} onPress={() => setOpen("state")} />
      <Row testID={`${testPrefix}-district`} label="District" value={ds?.name} disabled={!st} onPress={() => setOpen("district")} />
      <Row testID={`${testPrefix}-subdistrict`} label={subLabel} value={tk?.name} disabled={!ds} onPress={() => setOpen("taluk")} />
      {withCity ? (
        <>
          <Row testID={`${testPrefix}-city`} label="City / Town" value={value.city} disabled={!tk} onPress={() => setOpen("city")} />
          <Row testID={`${testPrefix}-village`} label="Village (optional)" value={value.village_name} disabled={!tk} onPress={() => setOpen("village")} />
          {value.village_name ? <Btn small variant="ghost" testID={`${testPrefix}-village-clear`} label="Clear village" onPress={() => onChange({ ...value, village_code: null, village_name: null })} /> : null}
        </>
      ) : null}
      <PickerModal visible={open === "state"} title="State / Union Territory" onClose={() => setOpen(null)}
        load={() => api("/lgd/states").then((r) => r.map((s: any) => ({ code: s.code, name: s.name, sub: `${s.is_ut ? "Union Territory" : "State"} · ${s.sub_label}s`, sub_label: s.sub_label })))}
        onPick={(i: any) => { setState({ code: i.code, name: i.name, sub_label: i.sub_label }); setDistrict(null); onChange({ taluk: null, ...reset }); setOpen(null); }} />
      <PickerModal visible={open === "district"} title="District" onClose={() => setOpen(null)}
        load={() => api(`/lgd/districts?state_code=${st?.code}`).then((r) => r.map((d: any) => ({ code: d.code, name: d.name })))}
        onPick={(i: any) => { setDistrict({ code: i.code, name: i.name }); onChange({ taluk: null, ...reset }); setOpen(null); }} />
      <PickerModal visible={open === "taluk"} title={subLabel} onClose={() => setOpen(null)}
        load={() => api(`/lgd/subdistricts?district_code=${ds?.code}`).then((r) => r.map((d: any) => ({ ...d, sub: d.district_name })))}
        onPick={(i: any) => { onChange({ taluk: { ...i, sub_label: st?.sub_label }, ...reset }); setOpen(null); }} />
      <PickerModal visible={open === "city"} title="City / Town" remote allowCustom onClose={() => setOpen(null)}
        load={(q) => api(`/lgd/villages?subdistrict_code=${tk?.code}&q=${encodeURIComponent(q)}`).then((r) => r.map((v: any) => ({ code: v.code, name: v.name, sub: v.category })))}
        onPick={(i) => { onChange({ ...value, city: i.name, city_code: i.code }); setOpen(null); }} />
      <PickerModal visible={open === "village"} title="Village" remote onClose={() => setOpen(null)}
        load={(q) => api(`/lgd/villages?subdistrict_code=${tk?.code}&q=${encodeURIComponent(q)}`).then((r) => r.map((v: any) => ({ code: v.code, name: v.name })))}
        onPick={(i) => { onChange({ ...value, village_code: i.code, village_name: i.name }); setOpen(null); }} />
    </View>
  );
}
