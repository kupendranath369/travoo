import Ionicons from "@react-native-vector-icons/ionicons";
import * as Location from "expo-location";
import { useRouter } from "expo-router";
import React, { useEffect, useRef, useState } from "react";
import { ActivityIndicator, FlatList, Linking, Modal, Pressable, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Loc } from "@/src/api";
import { MapPicker } from "@/src/components/MapPicker";
import { Btn, T, radius, space } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

const TYPE_ICON: Record<string, any> = {
  city: "business-outline", town: "home-outline", village: "leaf-outline", airport: "airplane-outline",
  railway_station: "train-outline", bus_terminal: "bus-outline", religious: "flower-outline", beach: "water-outline",
  hill_station: "triangle-outline", hospital: "medkit-outline", university: "school-outline", state: "map-outline",
  union_territory: "map-outline", industrial_area: "construct-outline", tourist_attraction: "camera-outline",
  district: "map-outline", locality: "home-outline", bus_stop: "bus-outline", road: "trail-sign-outline", landmark: "flag-outline",
  pin_area: "mail-outline", post_office: "mail-outline", pin: "pin-outline",
};

export const locSub = (l: Loc) => [...new Set([l.sub_district, l.district, l.state, l.pin].filter(Boolean))].join(", ");

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
  const { t, fmtDate } = useI18n();
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<Loc[]>([]);
  const [searching, setSearching] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [blocked, setBlocked] = useState(false);
  const [mapAt, setMapAt] = useState<{ lat: number; lng: number } | null | undefined>(undefined);
  const [synced, setSynced] = useState<string | null>(null);
  const seq = useRef(0);
  const router = useRouter();

  useEffect(() => {
    if (visible) api("/geo/status").then((s) => setSynced(s.last_success_at)).catch(() => {});
  }, [visible]);

  useEffect(() => {
    const qq = q.trim();
    setMsg("");
    if (!qq) {
      setRows([]);
      setSearching(false);
      return;
    }
    const id = ++seq.current;
    setSearching(true);
    const h = setTimeout(async () => {
      try {
        const r = await api<{ results: Loc[] }>(`/geo/search?q=${encodeURIComponent(qq)}`);
        if (id !== seq.current) return;
        setRows(r.results);
        if (!r.results.length && qq.length >= 3) setMsg(t("loc.none"));
      } catch (e: any) {
        if (id === seq.current) setMsg(e.message);
      }
      if (id === seq.current) setSearching(false);
    }, 300);
    return () => clearTimeout(h);
  }, [q, t]);

  const pick = async (item: Loc) => {
    if (!["openstreetmap", "india_post"].includes(item.source ?? "")) return onSelect(item);
    setBusy(true);
    try {
      onSelect(await api<Loc>(`/geo/place/${encodeURIComponent(item.loc_id)}`));
    } catch {
      onSelect(item);
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
      onSelect(await api<Loc>(`/geo/reverse?lat=${pos.coords.latitude}&lng=${pos.coords.longitude}&exact=true`));
    } catch (e: any) {
      setMsg(e.message);
    }
    setBusy(false);
  };

  const typeLabel = (ty: string) => {
    const s = t(`geo.type.${ty}`);
    return s.startsWith("geo.type.") ? ty.replace(/_/g, " ") : s;
  };

  const row = (testID: string, icon: any, label: string, onPress: () => void) => (
    <Pressable testID={testID} onPress={onPress} style={{ flexDirection: "row", alignItems: "center", gap: space.md, paddingHorizontal: space.lg, paddingVertical: space.md }}>
      <Ionicons name={icon} size={22} color={colors.brandPrimary} />
      <T weight="600" color={colors.brandPrimary}>{label}</T>
    </Pressable>
  );

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose} transparent>
      <Pressable style={{ flex: 1, backgroundColor: colors.scrim }} onPress={onClose} />
      <View style={{ backgroundColor: colors.surface, borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg, paddingTop: insets.top + space.sm, paddingBottom: insets.bottom + space.xl, maxHeight: "90%" }}>
        <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: space.lg, gap: space.md }}>
          <Pressable testID="location-modal-close" onPress={onClose} hitSlop={12}>
            <Ionicons name="close" size={26} color={colors.onSurface} />
          </Pressable>
          <T size={18} weight="700">{title}</T>
        </View>
        <View style={{ margin: space.lg, marginBottom: space.sm, flexDirection: "row", alignItems: "center", backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, paddingHorizontal: space.md }}>
          <Ionicons name="search" size={18} color={colors.muted} />
          <TextInput testID="location-search-input" autoFocus value={q} onChangeText={setQ} placeholder={t("loc.search")} placeholderTextColor={colors.muted} style={{ flex: 1, height: 50, paddingHorizontal: space.sm, fontSize: 15, color: colors.onSurface }} />
          {searching ? <ActivityIndicator testID="location-searching" size="small" color={colors.brandPrimary} /> : q ? (
            <Pressable testID="location-clear" onPress={() => setQ("")} hitSlop={10}><Ionicons name="close-circle" size={18} color={colors.muted} /></Pressable>
          ) : null}
        </View>
        <Pressable testID="location-map-button" onPress={() => setMapAt(rows[0] ? { lat: rows[0].lat, lng: rows[0].lng } : null)} style={{ flexDirection: "row", alignItems: "center", justifyContent: "center", gap: space.md, paddingHorizontal: space.lg, paddingVertical: space.md, backgroundColor: colors.brandPrimary, marginHorizontal: space.lg, marginTop: space.sm, borderRadius: radius.lg, minHeight: 56 }}>
          <Ionicons name="map" size={24} color={colors.onBrandPrimary} />
          <T weight="700" size={16} color={colors.onBrandPrimary}>{t("geo.choose_map")}</T>
        </Pressable>
        {row("location-current-button", "navigate-circle", t("loc.current"), current)}
        {busy ? <ActivityIndicator color={colors.brandPrimary} /> : null}
        {msg ? (
          <View style={{ paddingHorizontal: space.lg, gap: space.sm }}>
            <T testID="location-message" size={13} color={colors.muted}>{msg}</T>
            {blocked ? <Btn small variant="outline" label={t("loc.settings")} onPress={() => Linking.openSettings()} testID="open-settings-button" /> : null}
          </View>
        ) : null}
        <FlatList
          data={rows}
          keyboardShouldPersistTaps="handled"
          keyExtractor={(i) => i.loc_id}
          contentContainerStyle={{ paddingBottom: insets.bottom + space.xl }}
          renderItem={({ item }) => (
            <Pressable testID={`location-option-${item.loc_id}`} onPress={() => pick(item)} style={({ pressed }) => ({ flexDirection: "row", gap: space.md, paddingLeft: space.lg, paddingRight: space.sm, paddingVertical: space.md, backgroundColor: pressed ? colors.surfaceTertiary : "transparent", alignItems: "center" })}>
              <View style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: colors.brandSoft, alignItems: "center", justifyContent: "center" }}>
                <Ionicons name={TYPE_ICON[item.type] ?? "location-outline"} size={18} color={colors.brandPrimary} />
              </View>
              <View style={{ flex: 1 }}>
                <T weight="700">{item.name}</T>
                <T size={12} color={colors.muted} numberOfLines={1}>
                  {[typeLabel(item.type), locSub(item)].filter(Boolean).join(" · ")}
                </T>
              </View>
              <Pressable testID={`location-preview-${item.loc_id}`} hitSlop={8} onPress={() => setMapAt({ lat: item.lat, lng: item.lng })} style={{ padding: space.sm }}>
                <Ionicons name="map-outline" size={20} color={colors.muted} />
              </Pressable>
            </Pressable>
          )}
          ListFooterComponent={
            <View style={{ padding: space.lg, gap: space.sm }}>
              {q.trim().length >= 2 ? <Btn small variant="ghost" icon="add-circle-outline" label={t("v2.cant_find")} onPress={() => { onClose(); router.push("/add-place"); }} testID="location-add-missing-button" /> : null}
              <T size={10} color={colors.muted} center testID="location-attribution">
                Map data © OpenStreetMap contributors (ODbL) · PIN © India Post{synced ? ` · ${t("geo.updated")} ${fmtDate(synced.slice(0, 10))}` : ""}
              </T>
            </View>
          }
        />
      </View>
      <MapPicker visible={mapAt !== undefined} title={title} initial={mapAt ?? null} onClose={() => setMapAt(undefined)} onConfirm={(l) => { setMapAt(undefined); onSelect(l); }} />
    </Modal>
  );
}
