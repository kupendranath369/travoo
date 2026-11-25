import Ionicons from "@react-native-vector-icons/ionicons";
import { Image } from "expo-image";
import { useRouter } from "expo-router";
import React, { useState } from "react";
import { Pressable, ScrollView, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { IMG, Wordmark } from "@/src/components/Brand";
import { float } from "@/src/components/localdriver/parts";
import { T, radius, space } from "@/src/components/ui";
import { useSetMode } from "@/src/useMode";
import { useTheme } from "@/src/theme";

function ModeCard({ img, kicker, title, points, bg, accent, onPress, testID, busy }: { img: string; kicker: string; title: string; points: string[]; bg: string; accent: string; onPress: () => void; testID: string; busy: boolean }) {
  return (
    <Pressable testID={testID} disabled={busy} onPress={onPress} style={({ pressed }) => [float, { flexDirection: "row", overflow: "hidden", borderRadius: radius.lg, backgroundColor: bg,
      minHeight: 168, opacity: busy ? 0.6 : 1, transform: [{ scale: pressed ? 0.98 : 1 }] }]}>
      <Image source={{ uri: img }} style={{ width: "42%" }} contentFit="cover" />
      <View style={{ flex: 1, padding: space.md, gap: 4 }}>
        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" }}>
          <View><T size={13} weight="700">{kicker}</T><T size={24} weight="800" color={accent}>{title}</T></View>
          <View style={{ width: 30, height: 30, borderRadius: 15, backgroundColor: accent, alignItems: "center", justifyContent: "center" }}><Ionicons name="arrow-forward" size={18} color="#fff" /></View>
        </View>
        {points.map((p) => (
          <View key={p} style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
            <Ionicons name="checkmark" size={16} color={accent} /><T size={13}>{p}</T>
          </View>
        ))}
      </View>
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
    <ScrollView style={{ flex: 1, backgroundColor: colors.surface }} contentContainerStyle={{ padding: space.lg, paddingTop: insets.top + space.xl, gap: space.lg, paddingBottom: insets.bottom + space.xl }}>
      <View style={{ alignItems: "center" }}><Wordmark size={34} /></View>
      <T testID="mode-title" size={26} weight="800" center>How would you like to use Travoo?</T>
      <ModeCard testID="mode-passenger" img={IMG.passenger} kicker="I'm a" title="Passenger" points={["Find a Ride", "Rent a Driver", "Book a Driver"]} bg={colors.brandSoft} accent={colors.brandPrimary} busy={busy} onPress={() => pick("passenger")} />
      <ModeCard testID="mode-driver" img={IMG.driver} kicker="I'm a" title="Driver" points={["Offer a Ride", "Driver Only", "Car with Driver", "Earn with Driving"]} bg={colors.accentSoft} accent={colors.brandTertiary} busy={busy} onPress={() => pick("driver")} />
      {err ? <T testID="mode-error" color={colors.error}>{err}</T> : null}
      <View style={{ flexDirection: "row", alignItems: "center", gap: space.md, padding: space.md, borderRadius: radius.lg, backgroundColor: colors.surfaceSecondary }}>
        <Ionicons name="swap-horizontal" size={24} color={colors.brandPrimary} />
        <T size={13} color={colors.muted} style={{ flex: 1 }}>You can switch between Passenger and Driver modes anytime from your profile.</T>
      </View>
    </ScrollView>
  );
}
