import Ionicons from "@react-native-vector-icons/ionicons";
import React, { useEffect, useState } from "react";
import { Modal, Pressable, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Loc, locPayload } from "@/src/api";
import { LocationField } from "@/src/components/LocationField";
import { Taluk, TalukPicker } from "@/src/components/TalukPicker";
import { useToast } from "@/src/components/toast";
import { Btn, T, radius, space } from "@/src/components/ui";
import { useTheme } from "@/src/theme";

export const homeToTaluk = (home: any): Taluk | null =>
  home?.subdistrict_code
    ? {
        code: home.subdistrict_code,
        name: home.subdistrict_name,
        district_code: home.district_code,
        district_name: home.district_name,
        state_code: home.state_code,
        state_name: home.state_name,
        sub_label: home.sub_label,
      }
    : null;

export const homeToPlace = (home: any): Loc | null =>
  home?.loc_id && home?.geo?.lat != null && home?.geo?.lng != null
    ? {
        loc_id: home.loc_id,
        name: home.place_name || home.city || home.subdistrict_name,
        type: "place",
        district: home.district_name,
        state: home.state_name,
        sub_district: home.subdistrict_name,
        lat: home.geo.lat,
        lng: home.geo.lng,
      }
    : null;

export const homePayload = (taluk: Taluk, place: Loc | null) => ({
  subdistrict_code: taluk.code,
  city: place?.name ?? "",
  place: place ? locPayload(place) : null,
});

export function formatHomeLabel(home: any): string {
  if (!home) return "";
  const taluk = [home.subdistrict_name, home.sub_label].filter(Boolean).join(" ");
  const place = home.place_name || home.city;
  const parts = [
    place && place.toLowerCase() !== (home.subdistrict_name || "").toLowerCase() ? place : null,
    taluk || null,
    home.district_name || null,
  ].filter(Boolean);
  return parts.join(", ");
}

export function HomeLocationField({
  place,
  taluk,
  onChange,
  testPrefix = "pro-home",
}: {
  place: Loc | null;
  taluk: Taluk | null;
  onChange: (p: { place?: Loc | null; taluk?: Taluk | null }) => void;
  testPrefix?: string;
}) {
  const { colors } = useTheme();
  const [finding, setFinding] = useState(false);
  const [manual, setManual] = useState(false);

  const pickPlace = async (l: Loc) => {
    onChange({ place: l });
    setFinding(true);
    try {
      const r = await api(`/hire/identify-taluk?loc_id=${encodeURIComponent(l.loc_id)}&pickup=${encodeURIComponent(l.name)}`);
      if (r.subdistrict) {
        onChange({ place: l, taluk: r.subdistrict });
        setManual(false);
      } else {
        onChange({ place: l, taluk: null });
        setManual(true);
      }
    } catch {
      setManual(true);
    }
    setFinding(false);
  };

  return (
    <View style={{ gap: space.sm }}>
      <LocationField testID={`${testPrefix}-place`} label="Village, town or city" value={place} onChange={pickPlace} />
      {finding ? <T size={12} color={colors.muted}>Finding your taluk…</T> : null}
      {taluk && !manual ? (
        <View testID={`${testPrefix}-taluk`} style={{ flexDirection: "row", alignItems: "center", gap: space.sm, padding: space.md, borderRadius: radius.md, backgroundColor: colors.accentSoft }}>
          <Ionicons name="location" size={18} color={colors.brandTertiary} />
          <T size={13} weight="700" style={{ flex: 1 }}>
            {taluk.name} {taluk.sub_label ?? "Taluk"}, {taluk.district_name}, {taluk.state_name}
          </T>
          <Pressable testID={`${testPrefix}-taluk-change`} onPress={() => setManual(true)}>
            <T size={12} weight="700" color={colors.brandPrimary}>Change</T>
          </Pressable>
        </View>
      ) : null}
      {manual || (!taluk && !place) ? (
        <TalukPicker
          testPrefix={testPrefix}
          value={{ taluk, city: "", city_code: null, village_code: null, village_name: null }}
          onChange={(v) => onChange({ taluk: v.taluk, place: null })}
        />
      ) : null}
    </View>
  );
}

/** Modal allowing a Travoo-verified local driver to update their registered home location. */
export function HomeLocationModal({
  visible,
  currentHome,
  onClose,
  onSaved,
}: {
  visible: boolean;
  currentHome: any;
  onClose: () => void;
  onSaved: (me: any) => void;
}) {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const toast = useToast();
  const [place, setPlace] = useState<Loc | null>(null);
  const [taluk, setTaluk] = useState<Taluk | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (visible) {
      setPlace(homeToPlace(currentHome));
      setTaluk(homeToTaluk(currentHome));
      setErr("");
    }
  }, [visible, currentHome]);

  const save = async () => {
    if (!taluk) {
      setErr("Choose your home location (taluk)");
      return;
    }
    setBusy(true);
    setErr("");
    try {
      const r = await api("/pro/settings", { method: "PUT", body: { home: homePayload(taluk, place) } });
      toast("Home location updated");
      onSaved(r);
      onClose();
    } catch (e: any) {
      setErr(e.message || "Could not update home location");
    }
    setBusy(false);
  };

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: space.sm, paddingHorizontal: space.md, paddingVertical: space.sm, borderBottomWidth: 1, borderBottomColor: colors.divider }}>
          <Pressable testID="home-modal-close" onPress={onClose} hitSlop={8} style={{ width: 44, height: 44, alignItems: "center", justifyContent: "center" }}>
            <Ionicons name="close" size={24} color={colors.onSurface} />
          </Pressable>
          <T size={18} weight="800" style={{ flex: 1 }}>Change Home Location</T>
        </View>
        <KeyboardAwareScrollView bottomOffset={24} contentContainerStyle={{ padding: space.lg, gap: space.lg, paddingBottom: insets.bottom + space.xxl }}>
          <T size={13} color={colors.muted}>Update the home location where passengers can find and book you.</T>
          {visible ? (
            <HomeLocationField
              testPrefix="edit-home"
              place={place}
              taluk={taluk}
              onChange={(next) => {
                setErr("");
                if ("place" in next) setPlace(next.place ?? null);
                if ("taluk" in next) setTaluk(next.taluk ?? null);
              }}
            />
          ) : null}
          {err ? <T testID="home-modal-error" color={colors.error}>{err}</T> : null}
          <View style={{ flexDirection: "row", gap: space.sm }}>
            <Btn variant="outline" testID="home-modal-cancel" label="Cancel" onPress={onClose} disabled={busy} />
            <Btn style={{ flex: 1 }} testID="home-modal-save" icon="checkmark-circle-outline" label="Save Home Location" loading={busy} onPress={save} />
          </View>
        </KeyboardAwareScrollView>
      </View>
    </Modal>
  );
}
