import Ionicons from "@react-native-vector-icons/ionicons";
import React, { useState } from "react";
import { Modal, Pressable, ScrollView, View } from "react-native";
import Animated, { FadeInDown, ZoomIn } from "react-native-reanimated";

import { IMG } from "@/src/components/Brand";
import { FloatingImage } from "@/src/components/FloatingImage";
import { float } from "@/src/components/localdriver/parts";
import { T, radius, space } from "@/src/components/ui";
import { useSetMode } from "@/src/useMode";
import { useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";

function RoleCard({ img, title, points, bg, accent, onPress, testID, busy, delay }: { img: string; title: string; points: string[]; bg: string; accent: string; onPress: () => void; testID: string; busy: boolean; delay: number }) {
  const { colors } = useTheme();
  return (
    <Animated.View entering={FadeInDown.delay(delay).duration(450)}>
      <Pressable testID={testID} disabled={busy} onPress={onPress} style={({ pressed }) => [float, { flexDirection: "row", alignItems: "center", overflow: "hidden", borderRadius: radius.lg,
        backgroundColor: bg, minHeight: 150, borderWidth: 1, borderColor: accent, opacity: busy ? 0.6 : 1, transform: [{ scale: pressed ? 0.985 : 1 }] }]}>
        <FloatingImage uri={img} delay={delay} style={{ width: "40%", height: 150 }} />
        <View style={{ flex: 1, padding: space.md, gap: 4 }}>
          <T size={22} weight="800" color={colors.onSurface}>{title}</T>
          {points.map((p) => (
            <View key={p} style={{ flexDirection: "row", alignItems: "center", gap: 6 }}><Ionicons name="checkmark-circle" size={16} color={accent} /><T size={13}>{p}</T></View>
          ))}
        </View>
      </Pressable>
    </Animated.View>
  );
}

/** Floating window shown once after registration: pick Passenger or Driver (changeable later in Profile → Change Role). */
export function RoleChooser({ visible }: { visible: boolean }) {
  const { colors } = useTheme();
  const { t } = useI18n();
  const setMode = useSetMode();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const pick = async (m: "passenger" | "driver") => {
    setBusy(true); setErr("");
    try { await setMode(m); } catch (e: any) { setErr(e.message); }
    setBusy(false);
  };
  return (
    <Modal visible={visible} transparent animationType="fade" statusBarTranslucent onRequestClose={() => {}}>
      <View style={{ flex: 1, backgroundColor: colors.scrim, justifyContent: "center", padding: space.lg }}>
        <Animated.View entering={ZoomIn.duration(350)} testID="role-chooser" style={{ backgroundColor: colors.surface, borderRadius: radius.lg, maxHeight: "92%", borderWidth: 1, borderColor: colors.border }}>
          <ScrollView contentContainerStyle={{ padding: space.xl, gap: space.md }}>
            <T testID="mode-title" size={22} weight="800" center>How would you like to use Travoo?</T>
            <T size={13} color={colors.muted} center>Choose your role. You can change it anytime in Profile.</T>
            <RoleCard testID="mode-passenger" img={IMG.passenger} title="I am a Passenger" points={["Find a Ride", "Rent a Driver", t("svc.book_car")]} bg={colors.brandSoft} accent={colors.brandTertiary} busy={busy} delay={100} onPress={() => pick("passenger")} />
            <RoleCard testID="mode-driver" img={IMG.driver} title="I am a Driver" points={["Offer a Ride", "Driver Only", "Car with Driver"]} bg={colors.accentSoft} accent={colors.brandTertiary} busy={busy} delay={250} onPress={() => pick("driver")} />
            {err ? <T testID="mode-error" color={colors.error} center>{err}</T> : null}
          </ScrollView>
        </Animated.View>
      </View>
    </Modal>
  );
}
