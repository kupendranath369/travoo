import Ionicons from "@react-native-vector-icons/ionicons";
import React, { useEffect, useState } from "react";
import { Modal, Pressable, View } from "react-native";

import { Btn, IconName, T, radius, space } from "@/src/components/ui";
import { useTheme } from "@/src/theme";

type Mode = "passenger" | "driver";

function Opt({ icon, title, desc, on, onPress, testID }: { icon: IconName; title: string; desc: string; on: boolean; onPress: () => void; testID: string }) {
  const { colors } = useTheme();
  return (
    <Pressable testID={testID} onPress={onPress} style={{ flexDirection: "row", alignItems: "center", gap: space.md, padding: space.md, borderRadius: radius.lg,
      backgroundColor: on ? colors.brandSoft : colors.surfaceSecondary, borderWidth: 2, borderColor: on ? colors.brandPrimary : colors.border }}>
      <Ionicons name={icon} size={32} color={colors.brandSecondary} />
      <View style={{ flex: 1 }}><T weight="800">{title}</T><T size={12} color={colors.muted}>{desc}</T></View>
      <Ionicons name={on ? "checkmark-circle" : "ellipse-outline"} size={24} color={on ? colors.brandPrimary : colors.borderStrong} />
    </Pressable>
  );
}

/** Bottom sheet to switch between Passenger and Driver mode. */
export function ModeSheet({ open, current, onClose, onSwitch }: { open: boolean; current: Mode; onClose: () => void; onSwitch: (m: Mode) => Promise<void> }) {
  const { colors } = useTheme();
  const [pick, setPick] = useState<Mode>(current);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) setPick(current); }, [open, current]);
  return (
    <Modal visible={open} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={{ flex: 1, backgroundColor: colors.scrim }} onPress={onClose} />
      <View testID="mode-sheet" style={{ backgroundColor: colors.surface, padding: space.lg, gap: space.md, borderTopLeftRadius: 24, borderTopRightRadius: 24 }}>
        <View style={{ flexDirection: "row", alignItems: "center" }}>
          <T size={20} weight="800" style={{ flex: 1 }} center>Change Role</T>
          <Pressable testID="mode-sheet-close" onPress={onClose} hitSlop={10}><Ionicons name="close" size={24} color={colors.onSurface} /></Pressable>
        </View>
        <Opt testID="mode-sheet-passenger" icon="people" title="Passenger" desc="Book rides, rent a driver or book a car" on={pick === "passenger"} onPress={() => setPick("passenger")} />
        <Opt testID="mode-sheet-driver" icon="person" title="Driver" desc="Offer rides, work as a driver or provide car with driver" on={pick === "driver"} onPress={() => setPick("driver")} />
        <Btn testID="mode-sheet-switch" variant="navy" label="Change Role" disabled={pick === current} loading={busy} onPress={async () => { setBusy(true); await onSwitch(pick); setBusy(false); }} />
      </View>
    </Modal>
  );
}
