import * as Location from "expo-location";
import { useRouter } from "expo-router";
import React, { useState } from "react";
import { Linking, ScrollView, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import { OsmMap } from "@/src/components/OsmMap";
import { useToast } from "@/src/components/toast";
import { Btn, Card, Chip, Field, Header, T, space } from "@/src/components/ui";
import { useI18n } from "@/src/i18n";
import { useTheme } from "@/src/theme";

const TYPES = ["village", "town", "locality", "landmark", "bus_terminal", "railway_station", "other"];

export default function AddPlaceScreen() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const { t } = useI18n();
  const toast = useToast();
  const router = useRouter();
  const [f, setF] = useState({ name: "", local_name: "", district: "", state: "", pin: "" });
  const [ltype, setType] = useState("village");
  const [pos, setPos] = useState({ lat: 22.5, lng: 79.0 });
  const [picked, setPicked] = useState(false);
  const [centerKey, setCenterKey] = useState("0");
  const [err, setErr] = useState("");
  const [blocked, setBlocked] = useState(false);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (v: string) => setF({ ...f, [k]: v });

  const useCurrent = async () => {
    let p = await Location.getForegroundPermissionsAsync();
    if (!p.granted && p.canAskAgain) p = await Location.requestForegroundPermissionsAsync();
    if (!p.granted) { setBlocked(!p.canAskAgain); return setErr(t("loc.permission")); }
    const c = await Location.getCurrentPositionAsync({});
    setPos({ lat: c.coords.latitude, lng: c.coords.longitude });
    setCenterKey(String(Date.now()));
    setPicked(true);
  };

  const submit = async () => {
    setErr("");
    if (!picked) return setErr(t("v2.drop_pin"));
    setBusy(true);
    try {
      await api("/locations/missing", { body: { ...f, pin: f.pin || null, ltype, lat: pos.lat, lng: pos.lng } });
      toast(t("v2.place_sent"));
      if (router.canGoBack()) router.back();
      else router.replace("/");
    } catch (e: any) {
      setErr(e.message);
    }
    setBusy(false);
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title={t("v2.add_place")} />
      <KeyboardAwareScrollView bottomOffset={24} keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: space.lg, gap: space.md, paddingBottom: insets.bottom + space.xl }}>
        <Field testID="place-name-input" label={t("v2.place_name")} value={f.name} onChangeText={set("name")} />
        <Field testID="place-local-input" label={t("v2.local_name")} value={f.local_name} onChangeText={set("local_name")} />
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm }}>
          {TYPES.map((x) => <Chip key={x} testID={`place-type-${x}`} label={x.replace("_", " ")} active={ltype === x} onPress={() => setType(x)} />)}
        </ScrollView>
        <Field testID="place-district-input" label={t("v2.district")} value={f.district} onChangeText={set("district")} />
        <Field testID="place-state-input" label={t("v2.state")} value={f.state} onChangeText={set("state")} />
        <Field testID="place-pin-input" label={t("v2.pin")} value={f.pin} onChangeText={(v) => set("pin")(v.replace(/\D/g, ""))} keyboardType="number-pad" maxLength={6} />
        <Card style={{ gap: space.sm }}>
          <T weight="800">{t("v2.drop_pin")}</T>
          <T size={12} color={colors.muted}>{t("geo.tap_map")}</T>
          <OsmMap testID="pin-map" style={{ height: 300 }} pick={{ ...pos, color: colors.brandPrimary }} centerKey={centerKey} zoom={picked ? 15 : 5} onPick={(lat, lng) => { setPos({ lat, lng }); setPicked(true); }} />
          <Btn small variant="outline" icon="navigate" label={t("loc.current")} onPress={useCurrent} testID="place-current-location" />
          {blocked ? <Btn small variant="ghost" label={t("loc.settings")} onPress={() => Linking.openSettings()} testID="place-open-settings" /> : null}
          {picked ? <T testID="place-coords" size={12} color={colors.muted}>{t("v2.coords")}: {pos.lat.toFixed(5)}, {pos.lng.toFixed(5)}</T> : null}
        </Card>
        {err ? <T testID="place-error" color={colors.error}>{err}</T> : null}
        <Btn testID="place-submit-button" label={t("v2.submit_place")} onPress={submit} loading={busy} />
      </KeyboardAwareScrollView>
    </View>
  );
}
