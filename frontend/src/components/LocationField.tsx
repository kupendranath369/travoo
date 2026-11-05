import Ionicons from "@react-native-vector-icons/ionicons";
import * as Location from "expo-location";
import React, { useEffect, useState } from "react";
import { ActivityIndicator, FlatList, Linking, Modal, Pressable, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Loc } from "@/src/api";
import { Btn, T, radius, space } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

const TYPE_ICON: Record<string, any> = {
  city: "business-outline", town: "home-outline", village: "leaf-outline", airport: "airplane-outline",
  railway_station: "train-outline", bus_terminal: "bus-outline", religious: "flower-outline", beach: "water-outline",
  hill_station: "triangle-outline", hospital: "medkit-outline", university: "school-outline", state: "map-outline",
  union_territory: "map-outline", industrial_area: "construct-outline", tourist_attraction: "camera-outline",
};

export const locSub = (l: Loc) => [l.district, l.state, l.pin].filter(Boolean).join(", ");

export function LocationField({ label, value, onChange, icon = "location-outline", testID }: { label: string; value: Loc | null; onChange: (l: Loc) => void; icon?: any; testID: string }) {
  const [open, setOpen] = useState(false);
  const { colors } = useTheme();
  return (
    <>
      <Pressable testID={testID} onPress={() => setOpen(true)} style={{ flexDirection: "row", alignItems: "center", gap: space.md, minHeight: 56, paddingVertical: space.sm }}>
        <Ionicons name={icon} size={20} color={colors.brandPrimary} />
        <View style={{ flex: 1 }}>
          <T size={12} color={colors.muted}>{label}</T>
          <T size={15} weight="700" numberOfLines={1} color={value ? colors.onSurface : colors.muted}>
            {value ? value.name : "—"}
          </T>
          {value ? <T size={11} color={colors.muted} numberOfLines={1}>{locSub(value)}</T> : null}
        </View>
      </Pressable>
      <LocationSearchModal visible={open} title={label} onClose={() => setOpen(false)} onSelect={(l) => { onChange(l); setOpen(false); }} />
    </>
  );
}

export function LocationSearchModal({ visible, title, onClose, onSelect }: { visible: boolean; title: string; onClose: () => void; onSelect: (l: Loc) => void }) {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t } = useI18n();
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<Loc[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [blocked, setBlocked] = useState(false);

  useEffect(() => {
    if (!q.trim()) {
      setRows([]);
      return;
    }
    const h = setTimeout(async () => {
      try {
        setRows(await api<Loc[]>(`/locations/search?q=${encodeURIComponent(q.trim())}`));
      } catch {
        setRows([]);
      }
    }, 220);
    return () => clearTimeout(h);
  }, [q]);

  const osm = async () => {
    setBusy(true);
    setMsg("");
    try {
      const r = await api<Loc[]>(`/locations/osm?q=${encodeURIComponent(q.trim())}`);
      setRows((prev) => [...prev, ...r.filter((x) => !prev.some((p) => p.loc_id === x.loc_id))]);
      if (!r.length) setMsg(t("loc.none"));
    } catch (e: any) {
      setMsg(e.message);
    }
    setBusy(false);
  };

  const current = async () => {
    setMsg("");
    let perm = await Location.getForegroundPermissionsAsync();
    if (perm.status !== "granted" && perm.canAskAgain) perm = await Location.requestForegroundPermissionsAsync();
    if (perm.status !== "granted") {
      setBlocked(!perm.canAskAgain);
      setMsg(t("loc.permission"));
      return;
    }
    setBusy(true);
    try {
      const pos = await Location.getCurrentPositionAsync({});
      onSelect(await api<Loc>(`/locations/reverse?lat=${pos.coords.latitude}&lng=${pos.coords.longitude}`));
    } catch (e: any) {
      setMsg(e.message);
    }
    setBusy(false);
  };

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top + space.sm }}>
        <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: space.lg, gap: space.md }}>
          <Pressable testID="location-modal-close" onPress={onClose} hitSlop={12}>
            <Ionicons name="close" size={26} color={colors.onSurface} />
          </Pressable>
          <T size={18} weight="700">{title}</T>
        </View>
        <View style={{ margin: space.lg, flexDirection: "row", alignItems: "center", backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, paddingHorizontal: space.md }}>
          <Ionicons name="search" size={18} color={colors.muted} />
          <TextInput testID="location-search-input" autoFocus value={q} onChangeText={setQ} placeholder={t("loc.search")} placeholderTextColor={colors.muted} style={{ flex: 1, height: 50, paddingHorizontal: space.sm, fontSize: 15, color: colors.onSurface }} />
        </View>
        <Pressable testID="location-current-button" onPress={current} style={{ flexDirection: "row", alignItems: "center", gap: space.md, paddingHorizontal: space.lg, paddingVertical: space.md }}>
          <Ionicons name="navigate-circle" size={24} color={colors.brandPrimary} />
          <T weight="600" color={colors.brandPrimary}>{t("loc.current")}</T>
        </Pressable>
        {msg ? (
          <View style={{ paddingHorizontal: space.lg, gap: space.sm }}>
            <T size={13} color={colors.muted}>{msg}</T>
            {blocked ? <Btn small variant="outline" label={t("loc.settings")} onPress={() => Linking.openSettings()} testID="open-settings-button" /> : null}
          </View>
        ) : null}
        <FlatList
          data={rows}
          keyboardShouldPersistTaps="handled"
          keyExtractor={(i) => i.loc_id}
          contentContainerStyle={{ paddingBottom: insets.bottom + space.xl }}
          renderItem={({ item }) => (
            <Pressable testID={`location-option-${item.loc_id}`} onPress={() => onSelect(item)} style={({ pressed }) => ({ flexDirection: "row", gap: space.md, paddingHorizontal: space.lg, paddingVertical: space.md, backgroundColor: pressed ? colors.surfaceTertiary : "transparent", alignItems: "center" })}>
              <View style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: colors.brandSoft, alignItems: "center", justifyContent: "center" }}>
                <Ionicons name={TYPE_ICON[item.type] ?? "location-outline"} size={18} color={colors.brandPrimary} />
              </View>
              <View style={{ flex: 1 }}>
                <T weight="700">{item.name}</T>
                <T size={12} color={colors.muted} numberOfLines={1}>
                  {[item.type.replace(/_/g, " "), locSub(item)].filter(Boolean).join(" · ")}
                </T>
              </View>
            </Pressable>
          )}
          ListFooterComponent={
            q.trim().length >= 2 ? (
              <View style={{ padding: space.lg, gap: space.sm }}>
                {busy ? <ActivityIndicator color={colors.brandPrimary} /> : <Btn small variant="outline" icon="globe-outline" label={t("loc.osm")} onPress={osm} testID="location-osm-button" />}
                <T size={10} color={colors.muted} center>Map data © OpenStreetMap contributors (ODbL)</T>
              </View>
            ) : undefined
          }
        />
      </View>
    </Modal>
  );
}
