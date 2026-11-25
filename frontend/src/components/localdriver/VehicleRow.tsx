import Ionicons from "@react-native-vector-icons/ionicons";
import React from "react";
import { Pressable, View } from "react-native";

import { COMMERCIAL, float } from "@/src/components/localdriver/parts";
import { Badge, T, radius, space } from "@/src/components/ui";
import { useTheme } from "@/src/theme";

export function VehicleRow({ v, selected, onSelect, onEdit, right }: { v: any; selected?: boolean; onSelect?: () => void; onEdit?: () => void; right?: React.ReactNode }) {
  const { colors } = useTheme();
  const c = COMMERCIAL[v.commercial_status ?? "none"] ?? COMMERCIAL.none;
  return (
    <Pressable testID={`vehicle-row-${v.vehicle_id}`} onPress={onSelect ?? onEdit} style={[float, { flexDirection: "row", alignItems: "center", gap: space.md, padding: space.md,
      borderRadius: radius.lg, backgroundColor: colors.surfaceSecondary, borderWidth: 2, borderColor: selected ? colors.brandTertiary : "transparent" }]}>
      {onSelect ? <Ionicons testID={`vehicle-select-${v.vehicle_id}`} name={selected ? "checkbox" : "square-outline"} size={24} color={selected ? colors.brandTertiary : colors.borderStrong} /> : null}
      <View style={{ width: 42, height: 42, borderRadius: 12, backgroundColor: colors.accentSoft, alignItems: "center", justifyContent: "center" }}>
        <Ionicons name="car-sport" size={20} color={colors.brandTertiary} />
      </View>
      <View style={{ flex: 1, gap: 2 }}>
        <T weight="800">{v.name || `${v.make} ${v.model === "-" ? "" : v.model}`}</T>
        <T size={12} color={colors.muted}>{v.reg_no} · {String(v.vtype).toUpperCase()} · {v.seats} seats</T>
        <Badge testID={`vehicle-status-${v.vehicle_id}`} label={c.label} tone={c.tone} />
        {v.commercial_status === "rejected" && v.commercial_note ? <T size={11} color={colors.error}>{v.commercial_note}</T> : null}
      </View>
      {right ?? (onEdit ? <Pressable testID={`vehicle-edit-${v.vehicle_id}`} onPress={onEdit} hitSlop={10}><Ionicons name="create-outline" size={20} color={colors.muted} /></Pressable> : null)}
    </Pressable>
  );
}
