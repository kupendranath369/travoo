import Ionicons from "@react-native-vector-icons/ionicons";
import { useRouter } from "expo-router";
import React, { useState } from "react";
import { Pressable, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useSetMode } from "@/src/useMode";
import { float } from "@/src/components/localdriver/parts";
import { IconName, T, radius, space } from "@/src/components/ui";
import { useTheme } from "@/src/theme";

function ModeCard({ icon, title, desc, onPress, testID, busy }: { icon: IconName; title: string; desc: string; onPress: () => void; testID: string; busy: boolean }) {
  const { colors } = useTheme();
  return (
    <Pressable testID={testID} disabled={busy} onPress={onPress} style={({ pressed }) => [float, { flexDirection: "row", alignItems: "center", gap: space.md, padding: space.lg,
      borderRadius: radius.lg, backgroundColor: colors.surfaceSecondary, opacity: busy ? 0.6 : 1, transform: [{ scale: pressed ? 0.98 : 1 }] }]}>
      <View style={{ width: 60, height: 60, borderRadius: 30, backgroundColor: colors.accentSoft, alignItems: "center", justifyContent: "center" }}>
        <Ionicons name={icon} size={30} color={colors.brandTertiary} />
      </View>
      <View style={{ flex: 1, gap: 4 }}>
        <T size={18} weight="800">{title}</T>
        <T size={13} color={colors.muted}>{desc}</T>
      </View>
      <Ionicons name="chevron-forward" size={22} color={colors.muted} />
    </Pressable>
  );
}

export default function ChooseMode() {
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  const router = useRouter();
  const setMode = useSetMode();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const pick = async (m: "passenger" | "driver") => {
    setBusy(true); setErr("");
    try { await setMode(m); router.replace("/"); } catch (e: any) { setErr(e.message); }
    setBusy(false);
  };
  return (
    <View style={{ flex: 1, backgroundColor: colors.surface, padding: space.lg, paddingTop: insets.top + space.xxl, gap: space.lg }}>
      <T testID="mode-title" size={28} weight="800">How will you use Travoo?</T>
      <T color={colors.muted}>You can change this any time in Profile.</T>
      <ModeCard testID="mode-passenger" icon="person-outline" title="I'm a Passenger" desc="Find rides, rent a driver for your car, or book a car with driver" busy={busy} onPress={() => pick("passenger")} />
      <ModeCard testID="mode-driver" icon="car-sport-outline" title="I'm a Driver" desc="Earn as a local driver (Rent a Driver or Book a Driver) and offer carpool rides" busy={busy} onPress={() => pick("driver")} />
      {err ? <T testID="mode-error" color={colors.error}>{err}</T> : null}
    </View>
  );
}
