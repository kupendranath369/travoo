import Ionicons from "@react-native-vector-icons/ionicons";
import * as Location from "expo-location";
import React, { useEffect, useState } from "react";
import { ActivityIndicator, Linking, Modal, Pressable, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Loc } from "@/src/api";
import { OsmMap } from "@/src/components/OsmMap";
import { Btn, T, space } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

const INDIA = { lat: 22.5, lng: 79.0 };

/** Full-screen map: drop/drag a pin anywhere in India; the exact point is kept and labelled with the nearest named place. */
export function MapPicker({ visible, title, initial, onClose, onConfirm }: { visible: boolean; title: string; initial?: { lat: number; lng: number } | null; onClose: () => void; onConfirm: (l: Loc) => void }) {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t } = useI18n();
  const [pos, setPos] = useState(initial ?? INDIA);
  const [key, setKey] = useState("0");
  const [place, setPlace] = useState<Loc | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [blocked, setBlocked] = useState(false);

  useEffect(() => {
    if (visible) {
      setPos(initial ?? INDIA);
      setKey(String(Date.now()));
      setPlace(null);
      setMsg("");
    }
  }, [visible, initial]);

  useEffect(() => {
    if (!visible || (pos.lat === INDIA.lat && pos.lng === INDIA.lng)) return;
    setBusy(true);
    const h = setTimeout(async () => {
      try {
        setPlace(await api<Loc>(`/geo/reverse?lat=${pos.lat}&lng=${pos.lng}&exact=true`));
        setMsg("");
      } catch (e: any) {
        setPlace(null);
        setMsg(e.message);
      }
      setBusy(false);
    }, 600);
    return () => clearTimeout(h);
  }, [pos, visible]);

  const current = async () => {
    let p = await Location.getForegroundPermissionsAsync();
    if (!p.granted && p.canAskAgain) p = await Location.requestForegroundPermissionsAsync();
    if (!p.granted) {
      setBlocked(!p.canAskAgain);
      return setMsg(t("loc.permission"));
    }
    const c = await Location.getCurrentPositionAsync({});
    setPos({ lat: c.coords.latitude, lng: c.coords.longitude });
    setKey(String(Date.now()));
  };

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top + space.sm }}>
        <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: space.lg, paddingBottom: space.sm, gap: space.md }}>
          <Pressable testID="map-picker-close" onPress={onClose} hitSlop={12}>
            <Ionicons name="close" size={26} color={colors.onSurface} />
          </Pressable>
          <T size={18} weight="700" style={{ flex: 1 }} numberOfLines={1}>{title}</T>
        </View>
        <OsmMap testID="map-picker-map" style={{ flex: 1, height: undefined, borderRadius: 0 }} pick={{ ...pos, color: colors.brandPrimary }} centerKey={key}
          zoom={initial ? 15 : 5} onPick={(lat, lng) => setPos({ lat, lng })} />
        <View style={{ padding: space.lg, paddingBottom: insets.bottom + space.lg, gap: space.sm, backgroundColor: colors.surfaceSecondary, borderTopWidth: 1, borderTopColor: colors.border }}>
          <T size={12} color={colors.muted}>{t("geo.tap_map")}</T>
          {busy ? <ActivityIndicator color={colors.brandPrimary} /> : place ? (
            <View testID="map-picker-place">
              <T weight="800">{place.name}</T>
              <T size={12} color={colors.muted} numberOfLines={2}>{place.address || [place.district, place.state].filter(Boolean).join(", ")}</T>
              <T size={11} color={colors.muted}>{pos.lat.toFixed(5)}, {pos.lng.toFixed(5)}</T>
            </View>
          ) : null}
          {msg ? <T size={12} color={colors.error}>{msg}</T> : null}
          {blocked ? <Btn small variant="ghost" label={t("loc.settings")} onPress={() => Linking.openSettings()} testID="map-picker-settings" /> : null}
          <Btn small variant="outline" icon="navigate" label={t("loc.current")} onPress={current} testID="map-picker-current" />
          <Btn icon="checkmark" label={t("common.confirm")} disabled={!place || busy} onPress={() => place && onConfirm(place)} testID="map-picker-confirm" />
        </View>
      </View>
    </Modal>
  );
}
