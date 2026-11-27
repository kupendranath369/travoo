import Ionicons from "@react-native-vector-icons/ionicons";
import { useRouter } from "expo-router";
import React, { useEffect, useState } from "react";
import { ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Loc } from "@/src/api";
import { HomePlacePicker } from "@/src/components/localdriver/steps";
import { Taluk } from "@/src/components/TalukPicker";
import { useToast } from "@/src/components/toast";
import { Btn, Card, ErrorBox, Header, Loading, T, radius, space } from "@/src/components/ui";
import { useTheme } from "@/src/theme";

export default function ChangeHomeLocation() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const router = useRouter();
  const toast = useToast();
  const [home, setHome] = useState<any>(null);
  const [err, setErr] = useState("");
  const [sel, setSel] = useState<{ place: Loc | null; taluk: Taluk | null }>({ place: null, taluk: null });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/pro/dashboard").then((r) => {
      if (r.profile?.status !== "approved") return setErr("You can change your home location after Travoo verifies your profile.");
      setHome(r.profile.home || {});
    }).catch((e) => setErr(e.message));
  }, []);

  const save = async () => {
    if (!sel.taluk) return toast("Choose your new village, town or city", "error");
    setBusy(true);
    try {
      const p = sel.place;
      await api("/pro/home", { method: "PUT", body: { subdistrict_code: sel.taluk.code, city: p?.name ?? "",
        place: p ? { loc_id: p.loc_id, name: p.name, lat: p.lat, lng: p.lng, district: p.district ?? "", state: p.state ?? "", type: "place" } : null } });
      toast("Home location updated");
      router.back();
    } catch (e: any) { toast(e.message, "error"); }
    setBusy(false);
  };

  if (err) return <View style={{ flex: 1 }}><Header title="Home Location" /><ErrorBox message={err} /></View>;
  if (!home) return <View style={{ flex: 1 }}><Header title="Home Location" /><Loading /></View>;
  return (
    <View style={{ flex: 1, backgroundColor: colors.surface }}>
      <Header title="Home Location" />
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: space.lg, gap: space.lg, paddingBottom: insets.bottom + space.xxl }}>
        <Card testID="home-current-card" style={{ flexDirection: "row", alignItems: "center", gap: space.md }}>
          <View style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: colors.accentSoft, alignItems: "center", justifyContent: "center" }}>
            <Ionicons name="home" size={22} color={colors.brandSecondary} />
          </View>
          <View style={{ flex: 1, gap: 2 }}>
            <T size={12} color={colors.muted}>Current home location</T>
            <T testID="home-current-text" weight="800">{[...new Set([home.place_name !== home.subdistrict_name && home.place_name, home.subdistrict_name && `${home.subdistrict_name} ${home.sub_label ?? "Taluk"}`, home.district_name, home.state_name].filter(Boolean))].join(", ")}</T>
          </View>
        </Card>
        <View style={{ gap: space.sm }}>
          <T weight="800">New home location</T>
          <HomePlacePicker testPrefix="home-new" place={sel.place} taluk={sel.taluk} onChange={setSel} />
        </View>
        <View style={{ flexDirection: "row", gap: space.sm, padding: space.md, borderRadius: radius.md, backgroundColor: colors.brandSoft }}>
          <Ionicons name="information-circle" size={18} color={colors.brandPrimary} />
          <T size={12} style={{ flex: 1 }}>The change applies right away. You'll get booking requests for your new taluk, and confirmed trips stay the same.</T>
        </View>
        <Btn testID="home-save-button" icon="checkmark" label="Save new home location" onPress={save} loading={busy} disabled={!sel.taluk} />
      </ScrollView>
    </View>
  );
}
